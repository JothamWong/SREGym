"""Mitigation Oracle — calls standard eval logic (can be extended for alerts later)."""

from aiopslab.orchestrator.oracles.base import Oracle


class MitigationOracle(Oracle):
    def evaluate(self, solution, trace, duration) -> dict:
        print("== Mitigation Evaluation ==")
        return self.problem.eval(solution, trace, duration)
