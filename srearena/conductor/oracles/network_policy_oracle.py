from kubernetes import client
from srearena.conductor.oracles.detection import DetectionOracle
from typing import Dict, Any, Optional
import logging

class NetworkPolicyDetectionOracle(DetectionOracle):
    
    def __init__(self, problem, expected_blocked_services=None):
        super().__init__(problem=problem)
        self.networking_v1 = client.NetworkingV1Api()
        self.expected_blocked_services = expected_blocked_services or []
        self.logger = logging.getLogger(__name__)
    
    def detect(self) -> Dict[str, Any]:
        try:
            policies = self.networking_v1.list_namespaced_network_policy(
                namespace=self.problem.namespace
            )
            
            blocked_services = []
            policy_details = []
            
            for policy in policies.items:
                if self._is_deny_all_policy(policy):
                    affected_services = self._get_affected_services(policy)
                    blocked_services.extend(affected_services)
                    policy_details.append({
                        'name': policy.metadata.name,
                        'affected_services': affected_services,
                        'namespace': policy.metadata.namespace
                    })
            
            expected_blocked = [
                service for service in self.expected_blocked_services 
                if service in blocked_services
            ]
            
            return {
                'detected': len(expected_blocked) > 0,
                'blocked_services': blocked_services,
                'expected_blocked_found': expected_blocked,
                'policy_details': policy_details
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting NetworkPolicies: {e}")
            return {'detected': False, 'error': str(e)}
    
    def _is_deny_all_policy(self, policy) -> bool:
        spec = policy.spec
        policy_types = spec.policy_types or []
        
        if 'Ingress' in policy_types and (not spec.ingress or len(spec.ingress) == 0):
            return True
        
        if 'Egress' in policy_types and (not spec.egress or len(spec.egress) == 0):
            return True
        
        return False
    
    def _get_affected_services(self, policy) -> list:
        affected_services = []
        
        if policy.spec.pod_selector and policy.spec.pod_selector.match_labels:
            if 'app' in policy.spec.pod_selector.match_labels:
                affected_services.append(policy.spec.pod_selector.match_labels['app'])
        
        return affected_services
