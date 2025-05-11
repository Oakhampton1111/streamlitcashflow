"""ETL pipeline: CSV ingestion -> database."""

from typing import List, Tuple
import pandas as pd
from sqlalchemy.orm import Session

from src.logging_config import get_logger
from src.metrics import measure_duration, etl_duration_seconds
from src.db.session import get_db_session
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

    if not bank_csv_paths:
        logger.warning("No bank statement CSV paths provided")
        return inserted

    for path in bank_csv_paths:
        try:
            # Read CSV file
            df = pd.read_csv(path)
            if df.empty:
                logger.warning(f"Empty CSV file: {path}")
                continue

            # Standardize column names
            df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

            # Determine key columns
            date_col = next((c for c in df.columns if "date" in c), None)
            amount_col = next((c for c in df.columns if "amount" in c), None)
            supplier_col = next(
                (c for c in df.columns if "supplier" in c or "description" in c), None
            )

            if not (date_col and amount_col and supplier_col):
                logger.warning(f"Skipping {path}: required columns missing. Found columns: {df.columns.tolist()}")
                continue

            # Normalize date columns to datetime.date
            try:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.date
                # Drop rows with invalid dates
                df = df.dropna(subset=[date_col])
            except Exception as e:
                logger.error(f"Error converting dates in {path}: {e}")
                continue

            # Process each row
            for _, row in df.iterrows():
                try:
                    date = row[date_col]

                    # Skip rows with missing dates
                    if pd.isna(date):
                        continue

                    # Validate and convert amount
                    try:
                        amount = float(row[amount_col])
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid amount value: {row[amount_col]}")
                        continue

                    if pd.isna(amount) or amount == 0:
                        continue

                    status = "credit" if amount > 0 else "payment"

                    # Validate supplier name
                    supplier_name = str(row[supplier_col]).strip()
                    if not supplier_name:
                        continue

                    # Get or create supplier
                    supplier = get_or_create_supplier(db, supplier_name)

                    # Idempotency: skip existing record
                    existing = (
                        db.query(Creditor)
                        .filter_by(supplier_id=supplier.id, invoice_date=date, amount=amount)
                        .first()
                    )
                    if existing:
                        continue

                    # Calculate aging days
                    try:
                        aging_days = (pd.Timestamp.now().date() - date).days
                    except Exception:
                        aging_days = 0

                    # Create new creditor record
                    creditor = Creditor(
                        supplier_id=supplier.id,
                        invoice_date=date,
                        due_date=date,  # Default due date to invoice date
                        amount=amount,
                        aging_days=aging_days,
                        status=status,
                    )
                    db.add(creditor)
                    inserted += 1
                except Exception as e:
                    logger.exception(f"Error processing row in {path}: {e}")
                    continue

        except Exception as e:
            logger.exception(f"Error processing bank statement CSV {path}: {e}")
            continue

    db.commit()
    logger.info(f"Inserted {inserted} records from bank statements")
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

    if not aging_csv_path:
        logger.warning("No creditors-aging CSV path provided")
        return inserted, updated

    try:
        # Read CSV file
        df = pd.read_csv(aging_csv_path)
        if df.empty:
            logger.warning(f"Empty CSV file: {aging_csv_path}")
            return inserted, updated

        # Standardize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

        # Check for required columns
        required_cols = ["invoice_date", "amount"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.warning(f"Missing required columns in {aging_csv_path}: {missing_cols}")
            return inserted, updated

        # Normalize date columns to datetime.date
        for col in df.columns:
            if "date" in col:
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
                except Exception as e:
                    logger.error(f"Error converting {col} to date: {e}")

        # Drop rows with invalid invoice dates
        df = df.dropna(subset=["invoice_date"])

        # Process each row
        for _, row in df.iterrows():
            try:
                # Get invoice date
                invoice_date = row.get("invoice_date")
                if pd.isna(invoice_date):
                    continue

                # Get or default due date
                due_date = row.get("due_date")
                if pd.isna(due_date):
                    due_date = invoice_date

                # Validate and convert amount
                try:
                    amount = float(row.get("amount", 0))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid amount value: {row.get('amount')}")
                    continue

                # Get or default aging days
                try:
                    aging_days = int(row.get("aging_days", 0))
                except (ValueError, TypeError):
                    # Calculate aging days if not provided
                    aging_days = (pd.Timestamp.now().date() - invoice_date).days

                # Get or default status
                status = str(row.get("status", "")).strip()
                if not status:
                    status = "payment"  # Default status

                # Get supplier name
                supplier_name = str(row.get("supplier") or row.get("description") or "").strip()
                if not supplier_name:
                    logger.warning("Skipping row with missing supplier name")
                    continue

                # Get or create supplier
                supplier = get_or_create_supplier(db, supplier_name)

                # Check for existing record
                existing = (
                    db.query(Creditor)
                    .filter_by(supplier_id=supplier.id, invoice_date=invoice_date)
                    .first()
                )

                if existing:
                    # Update existing record
                    existing.due_date = due_date
                    existing.amount = amount
                    existing.aging_days = aging_days
                    existing.status = status
                    updated += 1
                else:
                    # Create new record
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
            except Exception as e:
                logger.exception(f"Error processing row in {aging_csv_path}: {e}")
                continue

        db.commit()
        logger.info(f"Processed creditors-aging: inserted={inserted}, updated={updated}")
        return inserted, updated

    except Exception as e:
        logger.exception(f"Error processing creditors-aging CSV {aging_csv_path}: {e}")
        return 0, 0


@measure_duration(etl_duration_seconds)
def run_etl(bank_csv_paths: List[str], aging_csv_path: str) -> None:
    """Execute full ETL: bank statements and creditors-aging ingestion.

    Args:
        bank_csv_paths (List[str]): List of file paths to bank statement CSVs.
        aging_csv_path (str): File path to the creditors-aging CSV.

    Returns:
        None
    """
    with get_db_session() as db:
        try:
            # Validate inputs
            if not bank_csv_paths and not aging_csv_path:
                logger.warning("No input files provided for ETL")
                return

            # Process bank statements
            count_bank = 0
            if bank_csv_paths:
                count_bank = ingest_bank_statements(db, bank_csv_paths)

            # Process creditors aging
            count_insert, count_update = 0, 0
            if aging_csv_path:
                count_insert, count_update = ingest_creditors_aging(db, aging_csv_path)

            # Log summary
            logger.info(f"ETL completed: Bank statements inserted: {count_bank}, "
                        f"Creditors-aging inserted: {count_insert}, updated: {count_update}")

        except Exception as e:
            logger.exception(f"ETL pipeline failed: {e}")
            raise
