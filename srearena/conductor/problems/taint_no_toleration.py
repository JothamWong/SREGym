from srearena.conductor.problems.base import Problem
from srearena.conductor.oracles.localization import LocalizationOracle
from srearena.conductor.oracles.compound import CompoundedOracle
from srearena.conductor.oracles.workload import WorkloadOracle
from srearena.conductor.oracles.pod_scheduled_mitigation import PodScheduledMitigationOracle
from srearena.generators.fault.inject_virtual import VirtualizationFaultInjector
from srearena.service.apps.socialnet import SocialNetwork        
from srearena.utils.decorators import mark_fault_injected

class TaintNoToleration(Problem):
    def __init__(self):
        self.app = SocialNetwork()
        self.namespace = self.app.namespace
        self.faulty_service = "frontend"
        self.faulty_node = "worker1"

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

    @mark_fault_injected
    def inject_fault(self):
        print("Fault Injection")
        self.injector.inject_toleration_without_matching_taint(
            [self.faulty_service], node_name=self.faulty_node
        )

    @mark_fault_injected
    def recover_fault(self):
        print("Fault Recovery")
        self.injector.recover_toleration_without_matching_taint(
            [self.faulty_service], node_name=self.faulty_node
        )
