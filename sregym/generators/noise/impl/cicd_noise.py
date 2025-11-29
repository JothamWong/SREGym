from sregym.generators.noise.base import BaseNoise
from sregym.generators.noise.impl import register_noise
from sregym.service.kubectl import KubeCtl
import logging
import time
import random

logger = logging.getLogger(__name__)

@register_noise("cicd_noise")
class CicdNoise(BaseNoise):
    def __init__(self, config):
        super().__init__(config)
        self.kubectl = KubeCtl()
        self.interval = config.get("interval", 60) # Update every 60 seconds
        self.last_update_time = 0
        self.target_deployments = config.get("deployments", []) # List of deployment names, or empty for random
        self.namespace = config.get("namespace", "default")
        self.context = {}

    def inject(self, context=None):
        trigger = context.get("trigger", "background")
        if trigger != "background":
            return

        now = time.time()
        if now - self.last_update_time < self.interval:
            return

        # Get target namespace from context if available
        target_ns = self.context.get("namespace", self.namespace)

        try:
            # If no specific deployments configured, pick one randomly
            if not self.target_deployments:
                deployments_json = self.kubectl.exec_command(f"kubectl get deployments -n {target_ns} -o jsonpath='{{.items[*].metadata.name}}'")
                all_deployments = deployments_json.split()
                if not all_deployments:
                    return
                target = random.choice(all_deployments)
            else:
                target = random.choice(self.target_deployments)

            logger.info(f"Simulating CI/CD update on {target} in {target_ns}")
            print(f"🔄 Simulating CI/CD rolling update on {target}")
            
            # Trigger rollout
            self.kubectl.trigger_rollout(target, target_ns)
            
            self.last_update_time = now
            
        except Exception as e:
            logger.error(f"Failed to inject CI/CD noise: {e}")

    def clean(self):
        pass
