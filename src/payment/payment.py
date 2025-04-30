"""Payment-plan algorithm."""

import logging
from datetime import date, timedelta
from typing import List

import pandas as pd
from sqlalchemy.orm import Session

from src.logging_config import get_logger
from src.metrics import measure_duration, payment_plan_duration_seconds
from src.db.session import SessionLocal
from src.db.models import PaymentPlan, Forecast

logger = get_logger(__name__)


@measure_duration(payment_plan_duration_seconds)
def generate_payment_plan(horizon_days: int = 91) -> List[dict]:
    """Generate a payment plan over a given horizon based on the latest forecast.

    Args:
        horizon_days (int): Number of days for the forecast horizon (default: 91).

    Returns:
        List[dict]: List of dictionaries, each containing:
            scheduled_date (date): Date of the Monday of the week.
            amount (float): Payment amount for the week.
            note (str): Note for the payment plan entry.
    """
    db: Session = SessionLocal()
    try:
        # fetch latest forecast record
        record = db.query(Forecast).order_by(Forecast.run_date.desc()).first()
        if not record:
            return []
        forecast_json = record.forecast_json

        # collect weekly deficits
        weekly_deficits: dict[date, float] = {}
        for entry in forecast_json:
            ds = entry.get("ds")
            yhat = float(entry.get("yhat", 0))
            dt = date.fromisoformat(ds) if isinstance(ds, str) else ds
            if yhat < 0:
                week_start = dt - timedelta(days=dt.weekday())
                weekly_deficits[week_start] = (
                    weekly_deficits.get(week_start, 0.0) + yhat
                )

        # determine number of weeks in horizon
        horizon_weeks = (horizon_days + 6) // 7
        # find first week start from first forecast date
        first_ds = forecast_json[0].get("ds")
        first_date = (
            date.fromisoformat(first_ds) if isinstance(first_ds, str) else first_ds
        )
        first_week_start = first_date - timedelta(days=first_date.weekday())

        # compute total shortfall
        total_shortfall = -sum(weekly_deficits.values())
        if total_shortfall <= 0:
            return []

        # equal distribution of shortfall across all weeks
        weekly_amount = float(total_shortfall) / horizon_weeks

        # build and return payment plan entries
        plan: List[dict] = []
        for i in range(horizon_weeks):
            wk = first_week_start + timedelta(weeks=i)
            plan.append(
                {
                    "scheduled_date": wk,
                    "amount": weekly_amount,
                    "note": "Auto-generated draft",
                }
            )
        return plan
    except Exception:
        logger.exception("Error generating payment plan")
        db.rollback()
        raise
    finally:
        db.close()


def calculate_payment_plan(
    forecast_df: pd.DataFrame, rules_df: pd.DataFrame
) -> pd.DataFrame:
    """Compute payment plan from forecast and rule outputs.

    Args:
        forecast_df (pd.DataFrame): DataFrame containing forecast data.
        rules_df (pd.DataFrame): DataFrame containing rule changes.

    Returns:
        pd.DataFrame: DataFrame with payment plan details.
    """
    # TODO: implement algorithm
    return pd.DataFrame()


def save_payment_plan(df_plans: pd.DataFrame) -> None:
    """Persist payment plans into payment_plans table.

    Args:
        df_plans (pd.DataFrame): DataFrame with plan details.

    Returns:
        None
    """
    db: Session = SessionLocal()
    try:
        for row in df_plans.itertuples(index=False):
            plan = PaymentPlan(
                forecast_id=row.forecast_id, plan_details=row.plan_details
            )
            db.add(plan)
        db.commit()
    finally:
        db.close()


def save_draft_payment_plans(db: Session, plans: List[dict]) -> int:
    """Persist draft payment plans.

    Args:
        db (Session): SQLAlchemy Session object.
        plans (List[dict]): List of plan dictionaries each containing:
            creditor_id (Optional[int]), scheduled_date, amount, and note.

    Returns:
        int: Count of inserted draft PaymentPlan records.
    """
    inserted = 0
    try:
        # Delete existing draft plans (case-insensitive match on note)
        db.query(PaymentPlan).filter(PaymentPlan.note.ilike("%draft%")).delete(
            synchronize_session=False
        )
        # Insert new draft plans
        for plan in plans:
            creditor_id = plan.get("creditor_id")
            scheduled_date = plan["scheduled_date"]
            amount = plan["amount"]
            note = plan["note"]
            new_plan = PaymentPlan(
                creditor_id=creditor_id,
                scheduled_date=scheduled_date,
                amount=amount,
                note=note,
            )
            db.add(new_plan)
            inserted += 1
        db.commit()
        return inserted
    except Exception:
        logger.exception("Error saving draft payment plans")
        db.rollback()
        raise


def run_payment():
    """Load forecasts and rule changes, compute plans, and persist payment plans.

    Returns:
        None
    """
    # TODO: query forecast and rule_changes
    df_forecast = pd.DataFrame()
    df_rules = pd.DataFrame()
    df_plans = calculate_payment_plan(df_forecast, df_rules)
    save_payment_plan(df_plans)
