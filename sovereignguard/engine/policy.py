"""
Granular Policy Engine — Role-Based Access Control for PII Masking

Allows organizations to define per-role masking policies:
- "Mask names for customer_service role, but not for department_managers"
- "Mask financial amounts only above 10,000"
- "Allow emails through for marketing role"

Architecture:
┌───────────────────────────────────────────────────────────┐
│  Policy Engine                                            │
│                                                           │
│  ┌──────────┐   ┌────────────────┐   ┌────────────────┐  │
│  │ API Key  │──▶│ Role Resolver  │──▶│ Policy Matcher │  │
│  │ → Role   │   │ → Policies     │   │ → Mask/Pass    │  │
│  └──────────┘   └────────────────┘   └────────────────┘  │
└───────────────────────────────────────────────────────────┘

Policy conditions allow:
- entity_type: which PII types to mask/pass
- action: "mask" or "pass" (pass = don't mask this entity)
- condition: optional predicate (e.g., value threshold)
"""

import re
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from sovereignguard.recognizers.base import RecognizerResult

logger = logging.getLogger(__name__)


class PolicyAction(str, Enum):
    MASK = "mask"         # Default: mask this entity type
    PASS = "pass"         # Let this entity type through unmasked
    REDACT = "redact"     # Replace with [REDACTED] (no reversible token)


@dataclass
class PolicyCondition:
    """Conditional masking rule — e.g., only mask if value > threshold."""
    field: str            # "value_length", "numeric_value", "pattern"
    operator: str         # "gt", "lt", "eq", "contains", "matches"
    value: Any            # comparison target


@dataclass
class PolicyRule:
    """A single masking rule within a policy."""
    entity_types: List[str]              # ["EMAIL", "PHONE"] or ["*"] for all
    action: PolicyAction = PolicyAction.MASK
    condition: Optional[PolicyCondition] = None

    def matches_entity(self, entity_type: str) -> bool:
        """Check if this rule applies to the given entity type."""
        if "*" in self.entity_types:
            return True
        return entity_type.upper() in [e.upper() for e in self.entity_types]

    def evaluate_condition(self, text: str) -> bool:
        """Evaluate the conditional predicate against the matched text."""
        if self.condition is None:
            return True

        cond = self.condition
        if cond.field == "value_length":
            actual = len(text)
        elif cond.field == "numeric_value":
            # Extract numeric value from text (e.g., "10,000 TND" → 10000)
            digits = re.sub(r'[^\d.]', '', text)
            try:
                actual = float(digits) if digits else 0
            except ValueError:
                return True  # Can't parse → apply default action
        elif cond.field == "pattern":
            if cond.operator == "matches":
                return bool(re.search(str(cond.value), text, re.IGNORECASE))
            return True
        else:
            return True

        # Compare
        if cond.operator == "gt":
            return actual > float(cond.value)
        elif cond.operator == "lt":
            return actual < float(cond.value)
        elif cond.operator == "eq":
            return actual == float(cond.value)
        elif cond.operator == "gte":
            return actual >= float(cond.value)
        elif cond.operator == "lte":
            return actual <= float(cond.value)

        return True


@dataclass
class MaskingPolicy:
    """A complete masking policy assigned to a role."""
    name: str
    description: str = ""
    rules: List[PolicyRule] = field(default_factory=list)
    # Default action when no rule matches
    default_action: PolicyAction = PolicyAction.MASK

    def get_action(self, result: RecognizerResult) -> PolicyAction:
        """Determine the action for a recognized entity based on policy rules."""
        for rule in self.rules:
            if rule.matches_entity(result.entity_type):
                if rule.evaluate_condition(result.text):
                    return rule.action
        return self.default_action


# ─── Role → Key Mapping ──────────────────────────────────────────────────────

@dataclass
class RoleBinding:
    """Maps an API key to a role and its associated policy."""
    api_key: str
    role: str
    policy_name: str


class PolicyEngine:
    """
    Central policy engine.

    Manages policies, role bindings, and applies per-request masking rules.
    """

    def __init__(self):
        self._policies: Dict[str, MaskingPolicy] = {}
        self._role_bindings: Dict[str, RoleBinding] = {}  # api_key → binding
        self._default_policy = MaskingPolicy(
            name="default",
            description="Mask all PII (default policy)",
            default_action=PolicyAction.MASK,
        )

    def load_policies_from_file(self, path: str):
        """Load policies and role bindings from a JSON configuration file."""
        config_path = Path(path)
        if not config_path.exists():
            logger.info(f"No policy file at {path}, using default mask-all policy")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Load policies
        for policy_data in config.get("policies", []):
            policy = self._parse_policy(policy_data)
            self._policies[policy.name] = policy
            logger.info(f"Loaded policy: {policy.name} ({len(policy.rules)} rules)")

        # Load role bindings
        for binding_data in config.get("role_bindings", []):
            binding = RoleBinding(
                api_key=binding_data["api_key"],
                role=binding_data["role"],
                policy_name=binding_data["policy"],
            )
            self._role_bindings[binding.api_key] = binding
            logger.info(f"Bound role '{binding.role}' → policy '{binding.policy_name}'")

    def _parse_policy(self, data: Dict) -> MaskingPolicy:
        """Parse a policy definition from JSON."""
        rules = []
        for rule_data in data.get("rules", []):
            condition = None
            if "condition" in rule_data:
                cond = rule_data["condition"]
                condition = PolicyCondition(
                    field=cond["field"],
                    operator=cond["operator"],
                    value=cond["value"],
                )

            rules.append(PolicyRule(
                entity_types=rule_data["entity_types"],
                action=PolicyAction(rule_data.get("action", "mask")),
                condition=condition,
            ))

        return MaskingPolicy(
            name=data["name"],
            description=data.get("description", ""),
            rules=rules,
            default_action=PolicyAction(data.get("default_action", "mask")),
        )

    def get_policy_for_key(self, api_key: str) -> MaskingPolicy:
        """Resolve the masking policy for a given API key."""
        binding = self._role_bindings.get(api_key)
        if not binding:
            return self._default_policy

        policy = self._policies.get(binding.policy_name)
        if not policy:
            logger.warning(
                f"Role '{binding.role}' references unknown policy "
                f"'{binding.policy_name}', using default"
            )
            return self._default_policy

        return policy

    def get_role_for_key(self, api_key: str) -> Optional[str]:
        """Get the role associated with an API key."""
        binding = self._role_bindings.get(api_key)
        return binding.role if binding else None

    def filter_results(
        self,
        results: List[RecognizerResult],
        policy: MaskingPolicy,
    ) -> List[RecognizerResult]:
        """
        Apply policy rules to filter/modify recognition results.

        Returns only entities that should be masked (removes those with PASS action).
        """
        filtered = []
        for result in results:
            action = policy.get_action(result)
            if action == PolicyAction.MASK:
                filtered.append(result)
            elif action == PolicyAction.REDACT:
                # Redact replaces with [REDACTED] — handled in masker
                result.entity_type = f"REDACTED_{result.entity_type}"
                filtered.append(result)
            # PASS → skip (don't mask this entity)

        return filtered

    def add_policy(self, policy: MaskingPolicy):
        """Register a policy programmatically."""
        self._policies[policy.name] = policy

    def add_role_binding(self, binding: RoleBinding):
        """Register a role binding programmatically."""
        self._role_bindings[binding.api_key] = binding
