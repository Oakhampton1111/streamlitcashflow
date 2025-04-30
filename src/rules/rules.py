"""Natural-language rules engine."""

import re
import logging

import pandas as pd
from sqlalchemy.orm import Session

from src.logging_config import get_logger
from src.db.session import SessionLocal
from src.db.models import RuleChange, Supplier
from src.metrics import measure_duration, rules_duration_seconds

logger = get_logger(__name__)


def evaluate_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Apply defined rules to the DataFrame and return the enriched DataFrame.

    Args:
        df (pd.DataFrame): Input DataFrame to apply rules on.

    Returns:
        pd.DataFrame: Enriched DataFrame after rule application.
    """
    # TODO: load rule definitions, instantiate Engine, apply to each row
    return df


def run_rules():
    """Query data from the database, apply rules, and persist RuleChange records.

    Returns:
        None
    """
    db: Session = SessionLocal()
    try:
        # TODO: load data into pandas DataFrame
        df = pd.DataFrame()
        # TODO: map df_out rows to RuleChange ORM and save
        db.commit()
    finally:
        db.close()


@measure_duration(rules_duration_seconds)
def parse_and_apply_rule(nl_text: str) -> bool:
    """Parse and apply a natural-language rule.

    Logs the rule change, parses supplier details, updates the supplier, and marks the change as applied.

    Args:
        nl_text (str): Natural-language rule text to parse and apply.

    Returns:
        bool: True if applied successfully, False otherwise.
    """
    db = SessionLocal()
    try:
        # Log the rule change record
        rc = RuleChange(nl_text=nl_text, applied=False)
        db.add(rc)
        db.commit()
        db.refresh(rc)
        # Parse the rule text
        pattern = r"^(?P<supplier>[^:]+):\s*(?P<rule_type>(?:flex|core))\s+delay\s+(?P<days>\d+)\s+days$"
        match = re.match(pattern, nl_text.strip(), flags=re.IGNORECASE)
        if not match:
            raise ValueError(f"Rule text not in expected format: '{nl_text}'")
        supplier_name = match.group("supplier").strip()
        rule_type = match.group("rule_type").lower()
        max_delay_days = int(match.group("days"))
        # Lookup the Supplier
        supplier = db.query(Supplier).filter(Supplier.name == supplier_name).first()
        if not supplier:
            raise ValueError(f"Supplier '{supplier_name}' not found")
        # Update supplier fields
        supplier.type = rule_type
        supplier.max_delay_days = max_delay_days
        db.commit()
        # Mark the rule change as applied
        rc.applied = True
        db.commit()
        logger.info(
            f"Applied rule for supplier '{supplier_name}': {rule_type} delay {max_delay_days} days"
        )
        return True
    except Exception as e:
        logger.exception(f"Failed to apply rule '{nl_text}': {e}")
        db.rollback()
        return False
    finally:
        db.close()


@measure_duration(rules_duration_seconds)
def apply_pending_rules() -> tuple[int, int]:
    """Query all pending RuleChange entries, apply each rule, and return counts of applied and failed rules.

    Returns:
        Tuple[int, int]: A tuple containing (applied_count, failed_count).
    """
    applied_count = 0
    failed_count = 0
    # Fetch pending rules
    db = SessionLocal()
    try:
        pending = db.query(RuleChange).filter(RuleChange.applied == False).all()
    finally:
        db.close()

    # Apply each pending rule
    for rc in pending:
        success = parse_and_apply_rule(rc.nl_text)
        if success:
            applied_count += 1
        else:
            failed_count += 1

    return applied_count, failed_count
