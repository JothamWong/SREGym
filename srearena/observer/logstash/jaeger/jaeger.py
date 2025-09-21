

import subprocess


class JaegerTiDB:
    def __init__(self):
        self.namespace= "observe"
        self.config_file = "jaeger.yaml"
    def run_cmd(self, cmd: str) -> str:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Command failed: {cmd}\nError: {result.stderr}")
        return result.stdout.strip()    

    def deploy(self):
        """Deploy Jaeger with TiDB as the storage backend."""
        self.run_cmd(f"kubectl apply -f {self.config_file} -n {self.namespace}")
        print("Jaeger deployed successfully.")


    def port_forward(self):
            """Block and port forward Jaeger UI to localhost:16686."""
            print("Starting port-forwarding for Jaeger UI on http://localhost:16686 (Ctrl+C to stop)")
            subprocess.run(
                ["kubectl", "port-forward", "svc/jaeger-out", "16686:16686", "-n", self.namespace],
                check=True
            )


if __name__ == "__main__":
    jaeger = JaegerTiDB()
    jaeger.deploy()
    jaeger.port_forward()



        






