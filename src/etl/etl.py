"""ETL pipeline: CSV ingestion -> database."""

from typing import List, Tuple
import pandas as pd
from sqlalchemy.orm import Session

from src.logging_config import get_logger
from src.metrics import measure_duration, etl_duration_seconds
from src.db.session import SessionLocal
from src.db.models import Supplier, Creditor

logger = get_logger(__name__)


def get_or_create_supplier(db: Session, name: str) -> Supplier:
    """Get or create a Supplier in the database by name.

    Args:
        db (Session): SQLAlchemy Session object.
        name (str): Name of the supplier.

    Returns:
        Supplier: The existing or newly created Supplier instance.
    """
    supplier = db.query(Supplier).filter_by(name=name).first()
    if not supplier:
        supplier = Supplier(name=name, type="core", max_delay_days=0)
        db.add(supplier)
        db.flush()
        logger.info(f"Created supplier: {name}")
    return supplier


def ingest_bank_statements(db: Session, bank_csv_paths: List[str]) -> int:
    """Ingest bank statement CSVs and load credit/payment transactions into creditors table.

    Args:
        db (Session): SQLAlchemy Session object.
        bank_csv_paths (List[str]): List of file paths to bank statement CSVs.

    Returns:
        int: Number of new records inserted.
    """
    inserted = 0
    for path in bank_csv_paths:
        df = pd.read_csv(path)
        # Standardize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        # Normalize date columns to datetime.date
        for col in df.columns:
            if "date" in col:
                df[col] = pd.to_datetime(df[col]).dt.date
        # Determine key columns
        date_col = next((c for c in df.columns if "date" in c), None)
        amount_col = next((c for c in df.columns if "amount" in c), None)
        supplier_col = next(
            (c for c in df.columns if "supplier" in c or "description" in c), None
        )
        if not (date_col and amount_col and supplier_col):
            logger.warning(f"Skipping {path}: required columns missing")
            continue
        for _, row in df.iterrows():
            date = row[date_col]
            amount = row[amount_col]
            if pd.isna(amount) or amount == 0:
                continue
            status = "credit" if amount > 0 else "payment"
            supplier_name = str(row[supplier_col]).strip()
            if not supplier_name:
                continue
            supplier = get_or_create_supplier(db, supplier_name)
            # Idempotency: skip existing record
            existing = (
                db.query(Creditor)
                .filter_by(supplier_id=supplier.id, invoice_date=date, amount=amount)
                .first()
            )
            if existing:
                continue
            creditor = Creditor(
                supplier_id=supplier.id,
                invoice_date=date,
                due_date=date,
                amount=amount,
                aging_days=(pd.Timestamp.now().date() - date).days,
                status=status,
            )
            db.add(creditor)
            inserted += 1
    db.commit()
    return inserted


def ingest_creditors_aging(db: Session, aging_csv_path: str) -> Tuple[int, int]:
    """Ingest creditors-aging CSV and insert or update creditors.

    Args:
        db (Session): SQLAlchemy Session object.
        aging_csv_path (str): File path to the creditors-aging CSV.

    Returns:
        Tuple[int, int]: Tuple of (inserted_count, updated_count).
    """
    inserted = 0
    updated = 0
    df = pd.read_csv(aging_csv_path)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    for col in df.columns:
        if "date" in col:
            df[col] = pd.to_datetime(df[col]).dt.date
    for _, row in df.iterrows():
        invoice_date = row.get("invoice_date")
        if pd.isna(invoice_date):
            continue
        due_date = row.get("due_date") or invoice_date
        amount = row.get("amount", 0)
        aging_days = int(row.get("aging_days", 0))
        status = str(row.get("status", "")).strip()
        supplier_name = str(row.get("supplier") or row.get("description") or "").strip()
        if not supplier_name:
            continue
        supplier = get_or_create_supplier(db, supplier_name)
        existing = (
            db.query(Creditor)
            .filter_by(supplier_id=supplier.id, invoice_date=invoice_date)
            .first()
        )
        if existing:
            existing.due_date = due_date
            existing.amount = amount
            existing.aging_days = aging_days
            existing.status = status
            updated += 1
        else:
            creditor = Creditor(
                supplier_id=supplier.id,
                invoice_date=invoice_date,
                due_date=due_date,
                amount=amount,
                aging_days=aging_days,
                status=status,
            )
            db.add(creditor)
            inserted += 1
    db.commit()
    return inserted, updated


@measure_duration(etl_duration_seconds)
def run_etl(bank_csv_paths: List[str], aging_csv_path: str) -> None:
    """Execute full ETL: bank statements and creditors-aging ingestion.

    Args:
        bank_csv_paths (List[str]): List of file paths to bank statement CSVs.
        aging_csv_path (str): File path to the creditors-aging CSV.

    Returns:
        None
    """
    db = SessionLocal()
    try:
        count_bank = ingest_bank_statements(db, bank_csv_paths)
        count_insert, count_update = ingest_creditors_aging(db, aging_csv_path)
        logger.info(f"Bank statements inserted: {count_bank}")
        logger.info(
            f"Creditors-aging inserted: {count_insert}, updated: {count_update}"
        )
    except Exception as e:
        logger.exception(f"ETL pipeline failed: {e}")
        raise
    finally:
        db.close()
