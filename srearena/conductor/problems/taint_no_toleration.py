from srearena.conductor.problems.base import Problem
from srearena.conductor.oracles.localization import LocalizationOracle
from srearena.conductor.oracles.compound import CompoundedOracle
from srearena.conductor.oracles.workload import WorkloadOracle
from srearena.conductor.oracles.pod_scheduled_mitigation import PodScheduledMitigationOracle
from srearena.generators.fault.inject_virtual import VirtualizationFaultInjector
from srearena.service.apps.socialnet import SocialNetwork
from srearena.utils.decorators import mark_fault_injected
from srearena.service.kubectl import KubeCtl

class TaintNoToleration(Problem):
    def __init__(self):
        self.app = SocialNetwork()
        self.namespace = self.app.namespace
        self.kubectl = KubeCtl()

        # ── pick a real worker node dynamically ─────────────────────────
        self.faulty_node = self._pick_worker_node()
        self.faulty_service = "frontend"

        super().__init__(app=self.app, namespace=self.namespace)

        self.localization_oracle = LocalizationOracle(
            problem=self, expected=[self.faulty_service]
        )

        self.app.create_workload()
        self.mitigation_oracle = CompoundedOracle(
            self,
            PodScheduledMitigationOracle(problem=self),
            WorkloadOracle(problem=self, wrk_manager=self.app.wrk),
        )

        self.injector = VirtualizationFaultInjector(namespace=self.namespace)

    def _pick_worker_node(self) -> str:
        """Return the name of the first node that is *not* control-plane."""
        nodes = self.kubectl.core_v1_api.list_node().items
        for n in nodes:
            name = n.metadata.name
            if "control-plane" not in name and "master" not in name:
                return name
        return nodes[0].metadata.name

    @mark_fault_injected
    def inject_fault(self):
        print("Fault Injection")
        self.kubectl.exec_command(
            f"kubectl taint node {self.faulty_node} sre-fault=blocked:NoSchedule --overwrite"
        )

        patch = """[{"op": "add", "path": "/spec/template/spec/tolerations",
                     "value": [{"key": "dummy-key", "operator": "Exists", "effect": "NoSchedule"}]}]"""
        self.kubectl.exec_command(
            f"kubectl patch deployment {self.faulty_service} -n {self.namespace} "
            f"--type='json' -p='{patch}'"
        )
        self.kubectl.exec_command(
            f"kubectl delete pod -l app={self.faulty_service} -n {self.namespace}"
        )

    @mark_fault_injected
    def recover_fault(self):
        print("Fault Recovery")
        self.injector.recover_toleration_without_matching_taint(
            [self.faulty_service], node_name=self.faulty_node
        )
