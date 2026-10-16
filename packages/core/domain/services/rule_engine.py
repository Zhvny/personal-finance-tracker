from typing import List

from packages.core.domain.models.rule import Operator, Rule
from packages.core.domain.models.transaction import Transaction


class RuleEngine:
    def __init__(self, rules: List[Rule]):
        self.rules = sorted([r for r in rules if r.enabled], key=lambda x: x.priority, reverse=True)

    def process(self, transaction: Transaction) -> Transaction:
        # Work on a copy to maintain immutability of input if desired,
        # but here we return a modified or new object.
        result = transaction.model_copy()

        for rule in self.rules:
            if self._matches(rule, result):
                self._apply_action(rule, result)

        return result

    def _matches(self, rule: Rule, tx: Transaction) -> bool:
        for criterion in rule.criteria:
            val = getattr(tx, criterion.field, None)
            if val is None:
                return False

            if criterion.operator == Operator.CONTAINS:
                if criterion.value.lower() not in str(val).lower():
                    return False
            elif criterion.operator == Operator.EQUALS:
                if str(val).lower() != str(criterion.value).lower():
                    return False
            # Add other operators as needed...
        return True

    def _apply_action(self, rule: Rule, tx: Transaction):
        if rule.action.set_category:
            tx.category = rule.action.set_category
        if rule.action.add_tags:
            tx.tags = list(set(tx.tags + rule.action.add_tags))
