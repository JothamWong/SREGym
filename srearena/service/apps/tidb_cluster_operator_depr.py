import json
import time
import subprocess
import os

class TiDBClusterDeployer:
    def __init__(self, metadata_path):
        with open(metadata_path, "r") as f:
            self.metadata = json.load(f)

        self.name = self.metadata["Name"]
        self.namespace_tidb_cluster = self.metadata["K8S Config"]["namespace"]
        self.cluster_config_url = self.metadata["K8S Config"]["config_url"]

        # Helm Operator config details
        self.operator_namespace = self.metadata["Helm Operator Config"]["namespace"]
        self.operator_release_name = self.metadata["Helm Operator Config"]["release_name"]
        self.operator_chart = self.metadata["Helm Operator Config"]["chart_path"]
        self.operator_version = self.metadata["Helm Operator Config"]["version"]

        # **IMPORTANT: local values.yaml path**
        # Adjust this path as needed (path to your local values.yaml)
        self.operator_values_path = os.path.join(os.path.dirname(__file__), "tidb-operator", "values.yaml")

    def run_cmd(self, cmd):
        print(f"Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)

    def create_namespace(self, ns):
        self.run_cmd(f"kubectl create ns {ns} --dry-run=client -o yaml | kubectl apply -f -")

    def install_operator_with_values(self):
        print(f"Installing/upgrading TiDB Operator via Helm in namespace '{self.operator_namespace}'...")
        self.create_namespace(self.operator_namespace)

        # Add pingcap repo if needed (ignore error)
        subprocess.run("helm repo add pingcap https://charts.pingcap.org", shell=True)

        self.run_cmd("helm repo update")

        # Helm install/upgrade command using local values.yaml
        self.run_cmd(
            f"helm upgrade --install {self.operator_release_name} {self.operator_chart} "
            f"--version {self.operator_version} -n {self.operator_namespace} "
            f"--create-namespace -f {self.operator_values_path}"
        )

    def wait_for_operator_ready(self):
        print("Waiting for tidb-controller-manager pod to be running...")
        label = "app.kubernetes.io/component=controller-manager"
        for _ in range(24):
            try:
                status = subprocess.check_output(
                    f"kubectl get pods -n {self.operator_namespace} -l {label} -o jsonpath='{{.items[0].status.phase}}'",
                    shell=True,
                ).decode().strip()
                if status == "Running":
                    print("tidb-controller-manager pod is running.")
                    return
            except subprocess.CalledProcessError:
                pass
            print("Pod not ready yet, retrying in 5 seconds...")
            time.sleep(5)
        raise RuntimeError("Timeout waiting for tidb-controller-manager pod")

    def wait_for_tidb_cluster_ready(self):
        print("Waiting for TiDB cluster pods to be ready...")
        label = "app.kubernetes.io/name=tidb"
        expected_ready_pods = 2  # Adjust this if you expect more TiDB pods
        for _ in range(30):  # Retry for up to 5 minutes (30 retries)
            ready_pods = subprocess.check_output(
                f"kubectl get pods -l {label} -n {self.namespace_tidb_cluster} --field-selector=status.phase=Running -o custom-columns='COUNT:.status.containerStatuses[?(@.ready==true)].name'",
                shell=True
            ).decode().strip().splitlines()
            if len(ready_pods) == expected_ready_pods:
                print("All TiDB pods are ready.")
                return
            print(f"{len(ready_pods)}/{expected_ready_pods} TiDB pods are ready. Waiting...")
            time.sleep(10)
        raise RuntimeError("Timeout waiting for TiDB cluster pods to be ready.")

    def wait_for_tidb_service_ready(self):
        print("Waiting for TiDB service to be ready...")
        # Check if the TiDB service is accessible
        for _ in range(30):  # Retry for up to 5 minutes (30 retries)
            try:
                # Check if the service is available on port 4000 (MySQL)
                subprocess.check_output(
                    f"kubectl run -n {self.namespace_tidb_cluster} --rm -it --restart=Never --image=mysql:8 --command -- mysql -h basic-tidb.tidb-cluster.svc -P 4000 -uroot -e 'SHOW DATABASES;'",
                    shell=True,
                )
                print("TiDB service is accessible and ready.")
                return
            except subprocess.CalledProcessError:
                print("TiDB service not yet ready, retrying...")
                time.sleep(10)

        raise RuntimeError("Timeout waiting for TiDB service to be ready.")

    def deploy_tidb_cluster(self):
        print(f"Creating TiDB cluster namespace '{self.namespace_tidb_cluster}'...")
        self.create_namespace(self.namespace_tidb_cluster)
        print(f"Deploying TiDB cluster manifest from {self.cluster_config_url}...")
        self.run_cmd(f"kubectl apply -f {self.cluster_config_url} -n {self.namespace_tidb_cluster}")
        # Wait for the TiDB service to be ready
        self.wait_for_tidb_service_ready()
        # Wait for the TiDB pods to be fully ready
        self.wait_for_tidb_cluster_ready()

    def deploy_all(self):
        print(f"Starting deployment: {self.name}")
        self.create_namespace(self.namespace_tidb_cluster)
        self.install_operator_with_values()
        self.wait_for_operator_ready()
        self.deploy_tidb_cluster()
        print("Deployment complete.")

if __name__ == "__main__":
    deployer = TiDBClusterDeployer("../metadata/tidb_metadata.json")
    deployer.deploy_all()
