"""Natural-language rules engine."""

import re
import logging

import pandas as pd
from sqlalchemy.orm import Session

from src.logging_config import get_logger
from src.db.session import get_db_session
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


@measure_duration(rules_duration_seconds)
def run_rules():
    """Query data from the database, apply rules, and persist RuleChange records.

    Returns:
        None
    """
    with get_db_session() as db:
        try:
            # Get all suppliers
            suppliers = db.query(Supplier).all()
            if not suppliers:
                logger.warning("No suppliers found in database")
                return

            # Get all pending rule changes
            pending_rules = db.query(RuleChange).filter(RuleChange.applied == False).all()

            logger.info(f"Found {len(suppliers)} suppliers and {len(pending_rules)} pending rules")

            # Apply all pending rules
            applied, failed = apply_pending_rules()

            logger.info(f"Applied {applied} rules, {failed} rules failed")

        except Exception as e:
            logger.exception(f"Error running rules: {e}")
            raise


@measure_duration(rules_duration_seconds)
def parse_and_apply_rule(nl_text: str) -> bool:
    """Parse and apply a natural-language rule.

    Logs the rule change, parses supplier details, updates the supplier, and marks the change as applied.

    Args:
        nl_text (str): Natural-language rule text to parse and apply.

    Returns:
        bool: True if applied successfully, False otherwise.
    """
    if not nl_text or not nl_text.strip():
        logger.warning("Empty rule text provided")
        return False

    with get_db_session() as db:
        try:
            # Log the rule change record
            rc = RuleChange(nl_text=nl_text, applied=False)
            db.add(rc)
            db.flush()  # Get ID without committing transaction
            db.refresh(rc)

            # Parse the rule text
            pattern = r"^(?P<supplier>[^:]+):\s*(?P<rule_type>(?:flex|core))\s+delay\s+(?P<days>\d+)\s+days$"
            match = re.match(pattern, nl_text.strip(), flags=re.IGNORECASE)
            if not match:
                logger.warning(f"Rule text not in expected format: '{nl_text}'")
                return False

            # Extract rule components
            supplier_name = match.group("supplier").strip()
            rule_type = match.group("rule_type").lower()

            # Validate rule type
            if rule_type not in ["flex", "core"]:
                logger.warning(f"Invalid rule type: '{rule_type}'. Must be 'flex' or 'core'")
                return False

            # Parse and validate max_delay_days
            try:
                max_delay_days = int(match.group("days"))
                if max_delay_days < 0:
                    logger.warning(f"Invalid delay days: {max_delay_days}. Must be non-negative")
                    return False
            except ValueError:
                logger.warning(f"Invalid delay days format: '{match.group('days')}'")
                return False

            # Lookup the Supplier
            supplier = db.query(Supplier).filter(Supplier.name == supplier_name).first()
            if not supplier:
                logger.warning(f"Supplier '{supplier_name}' not found")
                return False

            # Update supplier fields
            supplier.type = rule_type
            supplier.max_delay_days = max_delay_days

            # Mark the rule change as applied
            rc.applied = True

            logger.info(
                f"Applied rule for supplier '{supplier_name}': {rule_type} delay {max_delay_days} days"
            )
            return True

        except Exception as e:
            logger.exception(f"Failed to apply rule '{nl_text}': {e}")
            return False


@measure_duration(rules_duration_seconds)
def apply_pending_rules() -> tuple[int, int]:
    """Query all pending RuleChange entries, apply each rule, and return counts of applied and failed rules.

    Returns:
        Tuple[int, int]: A tuple containing (applied_count, failed_count).
    """
    applied_count = 0
    failed_count = 0

    # Fetch pending rules
    with get_db_session() as db:
        try:
            pending = db.query(RuleChange).filter(RuleChange.applied == False).all()

            if not pending:
                logger.info("No pending rules to apply")
                return 0, 0

            logger.info(f"Found {len(pending)} pending rules to apply")

            # Store rule texts to process after closing this session
            rule_texts = [rc.nl_text for rc in pending]

        except Exception as e:
            logger.exception(f"Error fetching pending rules: {e}")
            return 0, 0

    # Apply each pending rule (each with its own session)
    for rule_text in rule_texts:
        try:
            success = parse_and_apply_rule(rule_text)
            if success:
                applied_count += 1
                logger.info(f"Successfully applied rule: '{rule_text}'")
            else:
                failed_count += 1
                logger.warning(f"Failed to apply rule: '{rule_text}'")
        except Exception as e:
            logger.exception(f"Unexpected error applying rule '{rule_text}': {e}")
            failed_count += 1

    logger.info(f"Rule application complete: {applied_count} applied, {failed_count} failed")
    return applied_count, failed_count
