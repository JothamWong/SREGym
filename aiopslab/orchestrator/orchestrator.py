# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Orchestrator class that interfaces with the agent and the environment."""

import asyncio
import atexit
import inspect
import os
import time

from aiopslab.orchestrator.parser import ResponseParser
from aiopslab.orchestrator.problems.registry import ProblemRegistry
from aiopslab.service.kubectl import KubeCtl
from aiopslab.service.telemetry.prometheus import Prometheus
from aiopslab.session import Session
from aiopslab.utils.critical_section import CriticalSection
from aiopslab.utils.status import SessionPrint, SubmissionStatus


class Orchestrator:
    def __init__(self):
        self.agent = None
        self.session = None
        self.parser = ResponseParser()
        self.probs = ProblemRegistry()
        self.sprint = SessionPrint()
        self.kubectl = KubeCtl()
        self.prometheus = Prometheus()
        self.execution_start_time = None
        self.execution_end_time = None
        self.use_wandb = os.getenv("USE_WANDB", "false").lower() == "true"
        self.stage = "detection"  # could be: detection → localization → mitigation

    def register_agent(self, agent, name="agent"):
        self.agent = agent
        self.agent_name = name

    def init_problem(self, problem_id: str):
        self.execution_start_time = time.time()

        self.session = Session()
        print(f"Session ID: {self.session.session_id}")
        prob = self.probs.get_problem_instance(problem_id)
        self.session.set_problem(prob, pid=problem_id)
        self.session.set_agent(self.agent_name)

        print("Setting up OpenEBS...")
        self.kubectl.exec_command(
            "kubectl apply -f https://openebs.github.io/charts/openebs-operator.yaml"
        )
        self.kubectl.exec_command(
            'kubectl patch storageclass openebs-hostpath -p \'{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}\''
        )
        self.kubectl.wait_for_ready("openebs")
        print("OpenEBS setup completed.")

        self.prometheus.deploy()
        prob.app.delete()
        prob.app.deploy()

        with CriticalSection():
            prob.inject_fault()
            atexit.register(exit_cleanup_fault, prob=prob)

        if inspect.iscoroutinefunction(prob.start_workload):
            asyncio.create_task(prob.start_workload())
        else:
            prob.start_workload()

        return (
            "Problem loaded.",
            "Use submit(...) when ready.",
            {"submit(...)": "Submit your solution"},
        )

    async def ask_agent(self, input):
        agent_response = await self.agent.get_action(input)
        self.session.add({"role": "assistant", "content": agent_response})
        return agent_response

    async def ask_env(self, input):
        try:
            parsed = self.parser.parse(input)
        except Exception as e:
            self.session.add({"role": "env", "content": str(e)})
            return str(e)

        if parsed["api_name"] != "submit":
            return "[❌] Only `submit(...)` is supported in this interface."

        solution = parsed["args"][0] if parsed["args"] else None
        self.session.set_solution(solution)

        # Evaluate based on current stage
        duration = self.session.get_duration()
        trace = self.session.history
        prob = self.session.problem

        if self.stage == "detection":
            results = prob.detection_oracle.eval(solution, trace, duration)
            self.session.add_result("Detection Results", results)
            self.stage = "localization" if results.get("success") else "mitigation"
            return SubmissionStatus.VALID_SUBMISSION

        elif self.stage == "localization":
            results = prob.localization_oracle.eval(solution, trace, duration)
            self.session.add_result("Localization Results", results)
            self.stage = "mitigation"
            return SubmissionStatus.VALID_SUBMISSION

        elif self.stage == "mitigation":
            results = prob.mitigation_oracle.eval(solution, trace, duration)
            self.session.add_result("Mitigation Results", results)
            return SubmissionStatus.VALID_SUBMISSION

    async def start_problem(self, max_steps: int = 50):
        assert self.session is not None
        self.session.start()
        instr = "Please take the next action"
        action, env_response = "", ""

        try:
            while True:
                action = await self.ask_agent(instr)
                self.sprint.agent(action)
                env_response = await self.ask_env(action)
                self.sprint.service(env_response)

                if (
                    env_response == SubmissionStatus.VALID_SUBMISSION
                    and self.stage == "done"
                ):
                    break
        except Exception as e:
            with CriticalSection():
                self.session.problem.recover_fault()
                atexit.unregister(exit_cleanup_fault)
            raise e

        self.session.end()
        self.session.to_json()
        if self.use_wandb:
            self.session.to_wandb()

        with CriticalSection():
            self.session.problem.recover_fault()
            atexit.unregister(exit_cleanup_fault)
        self.session.problem.app.cleanup()
        self.prometheus.teardown()

        self.kubectl.exec_command(
            "kubectl delete sc openebs-hostpath openebs-device --ignore-not-found"
        )
        self.kubectl.exec_command(
            "kubectl delete -f https://openebs.github.io/charts/openebs-operator.yaml"
        )
        self.kubectl.wait_for_namespace_deletion("openebs")

        self.execution_end_time = time.time()
        elapsed = self.execution_end_time - self.execution_start_time
        time_keys = ["TTD", "TTL", "TTA", "TTM"]
        results = self.session.results
        key = next((k for k in time_keys if k in results), None)
        overhead = elapsed - results.get(key, 0) if key else elapsed
        print(f"Framework overhead: {overhead:.2f}s")

        return {
            "history": self.session.history,
            "final_state": "done",
            "results": results,
            "framework_overhead": overhead,
        }


def exit_cleanup_fault(prob):
    print("Recovering fault before exit...")
    prob.recover_fault()
