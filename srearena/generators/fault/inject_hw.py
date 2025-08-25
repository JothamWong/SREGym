import json
import shlex
import subprocess
from typing import List, Tuple

from srearena.generators.fault.base import FaultInjector
from srearena.service.kubectl import KubeCtl


class HWFaultInjector(FaultInjector):
    """
    Fault injector that calls the Khaos DaemonSet to inject syscall-level faults
    against *host* PIDs corresponding to workload pods.
    """

    def __init__(self, khaos_namespace: str = "khaos", khaos_label: str = "app=khaos"):
        self.kubectl = KubeCtl()
        self.khaos_ns = khaos_namespace
        self.khaos_daemonset_label = khaos_label

    # ---------- Public entry points ----------

    def inject(self, microservices: List[str], fault_type: str):
        """
        microservices: list of pod identifiers.
          Accepts either "pod" (default ns) or "ns/pod".
        """
        for pod_ref in microservices:
            ns, pod = self._split_ns_pod(pod_ref)
            node = self._get_pod_node(ns, pod)
            container_id = self._get_container_id(ns, pod)
            host_pid = self._get_host_pid_on_node(node, container_id)
            self._exec_khaos_fault_on_node(node, fault_type, host_pid)

    def recover(self, microservices: List[str], fault_type: str):
        """
        Undo an injected fault on each node touched by these pods.
        """
        touched = set()
        for pod_ref in microservices:
            ns, pod = self._split_ns_pod(pod_ref)
            node = self._get_pod_node(ns, pod)
            if node in touched:
                continue
            self._exec_khaos_recover_on_node(node, fault_type)
            touched.add(node)

    # ---------- Helpers: Kubernetes lookups ----------

    def _split_ns_pod(self, ref: str) -> Tuple[str, str]:
        if "/" in ref:
            ns, pod = ref.split("/", 1)
        else:
            # default namespace if your KubeCtl defaults to one; otherwise pass explicit ns/pod everywhere
            ns, pod = "default", ref
        return ns, pod

    def _jsonpath(self, ns: str, pod: str, path: str) -> str:
        cmd = f"kubectl -n {shlex.quote(ns)} get pod {shlex.quote(pod)} -o jsonpath='{path}'"
        out = self.kubectl.exec_command(cmd)
        if isinstance(out, tuple):
            out = out[0]
        return (out or "").strip()

    def _get_pod_node(self, ns: str, pod: str) -> str:
        node = self._jsonpath(ns, pod, "{.spec.nodeName}")
        if not node:
            raise RuntimeError(f"Pod {ns}/{pod} has no nodeName")
        return node

    def _get_container_id(self, ns: str, pod: str) -> str:
        # First try running container
        cid = self._jsonpath(ns, pod, "{.status.containerStatuses[0].containerID}")
        if not cid:
            # fall back to init container if needed
            cid = self._jsonpath(ns, pod, "{.status.initContainerStatuses[0].containerID}")
        if not cid:
            raise RuntimeError(f"Pod {ns}/{pod} has no containerID yet (not running?)")
        # cid looks like "containerd://<ID>" or "docker://<ID>"
        if "://" in cid:
            cid = cid.split("://", 1)[1]
        return cid

    def _get_khaos_pod_on_node(self, node: str) -> str:
        cmd = f"kubectl -n {shlex.quote(self.khaos_ns)} get pods -l {shlex.quote(self.khaos_daemonset_label)} -o json"
        out = self.kubectl.exec_command(cmd)
        if isinstance(out, tuple):
            out = out[0]
        data = json.loads(out)
        for item in data.get("items", []):
            if item.get("spec", {}).get("nodeName") == node and item.get("status", {}).get("phase") == "Running":
                return item["metadata"]["name"]
        raise RuntimeError(f"No running Khaos DS pod found on node {node}")

    # ---------- Host PID resolution (inside Khaos pod on that node) ----------

    def _get_host_pid_on_node(self, node: str, container_id: str) -> int:
        """
        Uses `crictl inspect <id>` inside the Khaos pod on that node.
        Falls back to a jq-less parse if jq isn't present.
        """
        pod_name = self._get_khaos_pod_on_node(node)

        # Try with jq first
        cmd = [
            "kubectl",
            "-n",
            self.khaos_ns,
            "exec",
            pod_name,
            "--",
            "sh",
            "-c",
            f"crictl inspect {shlex.quote(container_id)} | jq -r .info.pid",
        ]
        try:
            pid_txt = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
            if pid_txt.isdigit():
                return int(pid_txt)
        except subprocess.CalledProcessError:
            pass

        # Fallback: grep for "pid" field without jq
        cmd = [
            "kubectl",
            "-n",
            self.khaos_ns,
            "exec",
            pod_name,
            "--",
            "sh",
            "-c",
            f"crictl inspect {shlex.quote(container_id)} | sed -n 's/.*\"pid\"\\s*:\\s*\\([0-9][0-9]*\\).*/\\1/p' | head -n1",
        ]
        pid_txt = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
        if not pid_txt.isdigit():
            raise RuntimeError(f"Failed to resolve host PID for container {container_id} on node {node}: '{pid_txt}'")
        return int(pid_txt)

    # ---------- Khaos execution ----------

    def _exec_khaos_fault_on_node(self, node: str, fault_type: str, host_pid: int):
        pod_name = self._get_khaos_pod_on_node(node)
        cmd = ["kubectl", "-n", self.khaos_ns, "exec", pod_name, "--", "/khaos/khaos", fault_type, str(host_pid)]
        subprocess.run(cmd, check=True)

    def _exec_khaos_recover_on_node(self, node: str, fault_type: str):
        pod_name = self._get_khaos_pod_on_node(node)
        cmd = ["kubectl", "-n", self.khaos_ns, "exec", pod_name, "--", "/khaos/khaos", "--recover", fault_type]
        subprocess.run(cmd, check=True)
