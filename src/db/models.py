"""Database ORM models for the cashflow forecast application.

This module defines the SQLAlchemy models:
Supplier, Creditor, RuleChange, PaymentPlan, and Forecast.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    Date,
    DateTime,
    Numeric,
    Boolean,
    Text,
    JSON,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Supplier(Base):
    """ORM model for suppliers table.

    Attributes:
        id (int): Primary key.
        name (str): Name of the supplier.
        type (str): Supplier type, either 'core' or 'flex'.
        max_delay_days (int): Maximum allowed payment delay in days.
    """

    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(Enum("core", "flex", name="supplier_type"), nullable=False)
    max_delay_days = Column(Integer, nullable=False)


class Creditor(Base):
    """ORM model for creditors table.

    Attributes:
        id (int): Primary key.
        supplier_id (int): Foreign key referencing suppliers.id.
        invoice_date (date): Date of the invoice.
        due_date (date): Due date of the invoice.
        amount (Decimal): Amount due or credited.
        aging_days (int): Days past due.
        status (str): 'credit' or 'payment'.
    """

    __tablename__ = "creditors"
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(
        Integer, ForeignKey("suppliers.id"), nullable=False, index=True
    )
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    amount = Column(Numeric, nullable=False)
    aging_days = Column(Integer, nullable=False)
    status = Column(String, nullable=False)


class RuleChange(Base):
    """ORM model for rule_changes table, representing natural-language rule commands.

    Attributes:
        id (int): Primary key.
        nl_text (str): Natural-language rule text.
        applied (bool): Whether the rule has been applied.
        created_at (datetime): Timestamp when rule change was created.
    """

    __tablename__ = "rule_changes"
    id = Column(Integer, primary_key=True, index=True)
    nl_text = Column(Text, nullable=False)
    applied = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PaymentPlan(Base):
    """ORM model for payment_plans table.

    Attributes:
        id (int): Primary key.
        creditor_id (int): Foreign key referencing creditors.id.
        scheduled_date (date): Scheduled payment date.
        amount (Decimal): Payment amount.
        note (str): Notes on the payment plan.
    """

    __tablename__ = "payment_plans"
    id = Column(Integer, primary_key=True, index=True)
    creditor_id = Column(
        Integer, ForeignKey("creditors.id"), nullable=False, index=True
    )
    scheduled_date = Column(Date, nullable=False)
    amount = Column(Numeric, nullable=False)
    note = Column(Text)


class Forecast(Base):
    """ORM model for forecasts table.

    Attributes:
        id (int): Primary key.
        run_date (datetime): Timestamp of when forecast was generated.
        horizon_days (int): Forecast horizon in days.
        forecast_json (JSON): JSON payload of forecast results.
    """

    __tablename__ = "forecasts"
    id = Column(Integer, primary_key=True, index=True)
    run_date = Column(DateTime, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    forecast_json = Column(JSON, nullable=False)
