from srearena.conductor.oracles.base import Oracle
import time

class PodScheduledMitigationOracle(Oracle):

    importance = 1.0

    def evaluate(self) -> dict:
        svc = self.problem.faulty_service
        ns  = self.problem.namespace
        kubectl = self.problem.kubectl
        timeout = 90
        deadline = time.time() + timeout

        selector = f"app={svc}"
        while time.time() < deadline:
            pods = kubectl.core_v1_api.list_namespaced_pod(ns, label_selector=selector)
            if pods.items and all(p.status.phase == "Running" for p in pods.items):
                print(" All pods Running again. Yay")
                return {"success": True}
            time.sleep(4)

        print(f" Pods for {svc} not Running within {timeout}s")
        return {"success": False}
