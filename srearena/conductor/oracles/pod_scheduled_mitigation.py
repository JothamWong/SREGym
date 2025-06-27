from srearena.conductor.oracles.base import Oracle
import time
from kubernetes.client.exceptions import ApiException


class PodScheduledMitigationOracle(Oracle):

    importance = 1.0

    def evaluate(self) -> dict:
        svc = self.problem.faulty_service
        ns = self.problem.namespace
        kubectl = self.problem.kubectl
        node_name = self.problem.faulty_node

        timeout = 180
        deadline = time.time() + timeout

        selector = f"app={svc}"
        while time.time() < deadline:
            pods = kubectl.core_v1_api.list_namespaced_pod(
                ns, label_selector=selector
            )

            pod_phases = [p.status.phase for p in pods.items] if pods.items else []
            pods_running = pod_phases and all(p == "Running" for p in pod_phases)
            pods_pending = pod_phases and all(p == "Pending" for p in pod_phases)

            taint_present = True
            try:
                node = kubectl.core_v1_api.read_node(node_name)
                taint_present = any(
                    t.key == "sre-fault"
                    and t.value == "blocked"
                    and t.effect == "NoSchedule"
                    for t in (node.spec.taints or [])
                )
            except ApiException as e:
                if e.status == 404:
                    taint_present = False
                else:
                    raise

            if pods_running and not taint_present:
                print("All pods Running and taint cleared. Mitigation successful")
                return {"success": True}

            if pods_pending and taint_present:
                print("Pods stuck Pending ➜ auto-removing taint so they can schedule …")
                kubectl.exec_command(
                    f"kubectl taint node {node_name} sre-fault=blocked:NoSchedule-"
                )

            time.sleep(4)

        print(f"Pods for {svc} not Running or taint still present after {timeout}s")
        return {"success": False}
