import time
from pathlib import Path

from kubernetes import client, config
from kubernetes.client import V1JobStatus

from aiopslab.generators.workload.base import TaskedWorkloadGenerator, WorkloadEntry


class Wrk2WorkloadGenerator(TaskedWorkloadGenerator):
    """
    Wrk2 workload generator for Kubernetes.
    """

    def __init__(self, wrk, payload_script: Path, url, job_name="wrk2-job"):
        super().__init__()
        self.wrk = wrk
        self.payload_script = payload_script
        self.url = url
        self.job_name = job_name

        config.load_kube_config()
        self.core_v1_api = client.CoreV1Api()
        self.batch_v1_api = client.BatchV1Api()

    def get_job_logs(self, job_name, namespace):
        """Retrieve the logs of a specified job within a namespace."""

        pods = self.core_v1_api.list_namespaced_pod(namespace, label_selector=f"job-name={job_name}")
        # print(
        #     pods.items[0].metadata.name,
        #     self.core_v1_api.read_namespaced_pod_log(pods.items[0].metadata.name, namespace),
        # )
        if len(pods.items) == 0:
            raise Exception(f"No pods found for job {job_name} in namespace {namespace}")
        return self.core_v1_api.read_namespaced_pod_log(pods.items[0].metadata.name, namespace)

    @staticmethod
    def is_job_completed(job_status: V1JobStatus) -> bool:
        if hasattr(job_status, "conditions") and job_status.conditions is not None:
            for condition in job_status.conditions:
                if condition.type == "Complete" and condition.status == "True":
                    return True
        return False

    def create_task(self):
        namespace = "default"
        configmap_name = "wrk2-payload-script"

        if not hasattr(self, "configmap_created") or not self.configmap_created:
            self.wrk.create_configmap(
                name=configmap_name,
                namespace=namespace,
                payload_script_path=self.payload_script,
            )
            self.configmap_created = True

        self.wrk.create_wrk_job(
            job_name=self.job_name,
            namespace=namespace,
            payload_script=self.payload_script.name,
            url=self.url,
        )

    def wait_until_complete(self):
        namespace = "default"

        print(f"--- Waiting for the job {self.job_name} ---")

        try:
            while True:
                job_status = self.batch_v1_api.read_namespaced_job_status(
                    name=self.job_name, namespace=namespace
                ).status
                if Wrk2WorkloadGenerator.is_job_completed(job_status):
                    print("Job completed successfully.", flush=True)
                    break
                time.sleep(5)
        except client.exceptions.ApiException as e:
            print(f"Error monitoring job: {e}")
            return False

        return True

    def retrievelog(self) -> WorkloadEntry:
        namespace = "default"

        if not self.wait_until_complete():
            raise RuntimeError("Unable to check job status.")

        logs = None
        try:
            logs = self.get_job_logs(
                job_name=self.job_name,
                namespace=namespace,
            )
            logs = logs.split("\n")
        except Exception as e:
            return f"Workload Generator Error: {e}"

        # -----------------------------------------------------------------------
        #   10 requests in 10.00s, 2.62KB read
        #   Non-2xx or 3xx responses: 10

        number = -1
        ok = True
        try:
            for i, log in enumerate(logs):
                if "-" * 35 in log and "requests" in logs[i + 1]:
                    parts = logs[i + 1].split(" ")
                    for j, part in enumerate(parts):
                        if part is not "":
                            number = parts[j]
                            assert parts[j + 1] == "requests"
                            break
                if "Non-2xx or 3xx responses" in log:
                    ok = False

            number = int(number)
        except ValueError:
            print(f"Error parsing number from log: {number}")
            number = 0

        return WorkloadEntry(
            time=time.time(),
            number=number,
            log="\n".join(logs),
            ok=ok,
        )
