"""Otel demo kafkaQueueProblems feature flag fault."""

from typing import Any

from sregym.conductor.oracles.detection import DetectionOracle
from sregym.conductor.oracles.otel_localization_oracle import OtelLocalizationOracle
from sregym.conductor.problems.base import Problem
from sregym.generators.fault.inject_otel import OtelFaultInjector
from sregym.service.apps.astronomy_shop import AstronomyShop
from sregym.service.kubectl import KubeCtl
from sregym.utils.decorators import mark_fault_injected


class KafkaQueueProblems(Problem):
    def __init__(self):
        self.app = AstronomyShop()
        self.kubectl = KubeCtl()
        self.namespace = self.app.namespace
        self.injector = OtelFaultInjector(namespace=self.namespace)
        self.faulty_service = "kafka"
        super().__init__(app=self.app, namespace=self.app.namespace)
        # === Attach evaluation oracles ===
        self.localization_oracle = OtelLocalizationOracle(
            problem=self, namespace=self.namespace, expected_deployment_name=self.faulty_service
        )

    @mark_fault_injected
    def inject_fault(self):
        print("== Fault Injection ==")
        self.injector.inject_fault("kafkaQueueProblems")
        print(f"Fault: kafkaQueueProblems | Namespace: {self.namespace}\n")

    @mark_fault_injected
    def recover_fault(self):
        print("== Fault Recovery ==")
        self.injector.recover_fault("kafkaQueueProblems")
