from datetime import datetime

from packages.core.domain.models.rule import Criterion, Operator, Rule, RuleAction
from packages.core.domain.models.transaction import Transaction
from packages.core.domain.services.rule_engine import RuleEngine


def test_rule_engine_applies_category():
    tx = Transaction(date=datetime.now(), description="Netflix Subscription", amount=-15.99)
    rule = Rule(
        id="1",
        name="Netflix Rule",
        criteria=[Criterion(field="description", operator=Operator.CONTAINS, value="Netflix")],
        action=RuleAction(set_category="Entertainment", add_tags=["subs"])
    )

    engine = RuleEngine(rules=[rule])
    processed_tx = engine.process(tx)

    assert processed_tx.category == "Entertainment"
    assert "subs" in processed_tx.tags
