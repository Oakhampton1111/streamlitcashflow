"""Unit tests for the ETL module."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import pandas as pd
from datetime import datetime, date
import io

# Use unittest directly instead of BaseTestCase
import unittest
from src.etl.etl import get_or_create_supplier, ingest_bank_statements, ingest_creditors_aging, run_etl
from src.db.models import Supplier, Creditor


class TestETL(unittest.TestCase):
    """Test cases for the ETL module."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample bank statement CSV content
        self.bank_csv_content = """date,amount,supplier
2023-01-01,100.00,Supplier A
2023-01-02,-50.00,Supplier B
2023-01-03,75.00,Supplier C
2023-01-04,-25.00,Supplier B
"""
        # Sample creditors aging CSV content
        self.aging_csv_content = """supplier,invoice_date,due_date,amount,aging_days,status
Supplier A,2023-01-01,2023-01-15,100.00,5,credit
Supplier B,2023-01-02,2023-01-20,50.00,4,payment
Supplier C,2023-01-03,2023-01-25,75.00,3,credit
"""

    @patch('src.etl.etl.pd.read_csv')
    @patch('src.etl.etl.get_or_create_supplier')
    def test_ingest_bank_statements(self, mock_get_supplier, mock_read_csv):
        """Test that ingest_bank_statements correctly processes bank statement CSVs."""
        # Set up mocks
        mock_db = MagicMock()

        # Mock the read_csv function
        mock_df = pd.DataFrame({
            'date': [date(2023, 1, 1), date(2023, 1, 2)],
            'amount': [100.0, -50.0],
            'supplier': ['Supplier A', 'Supplier B']
        })
        mock_read_csv.return_value = mock_df

        # Mock supplier creation
        mock_supplier = MagicMock()
        mock_supplier.id = 1
        mock_get_supplier.return_value = mock_supplier

        # Mock the query to check for existing records
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        # Call the function
        result = ingest_bank_statements(mock_db, ['bank.csv'])

        # Assertions
        self.assertEqual(result, 2)  # Should insert 2 records
        mock_read_csv.assert_called_once_with('bank.csv')
        self.assertEqual(mock_db.add.call_count, 2)
        mock_db.commit.assert_called_once()

    @patch('src.etl.etl.pd.read_csv')
    @patch('src.etl.etl.get_or_create_supplier')
    def test_ingest_creditors_aging(self, mock_get_supplier, mock_read_csv):
        """Test that ingest_creditors_aging correctly processes aging CSV."""
        # Set up mocks
        mock_db = MagicMock()

        # Mock the read_csv function
        mock_df = pd.DataFrame({
            'supplier': ['Supplier A', 'Supplier B'],
            'invoice_date': [date(2023, 1, 1), date(2023, 1, 2)],
            'due_date': [date(2023, 1, 15), date(2023, 1, 20)],
            'amount': [100.0, 50.0],
            'aging_days': [5, 4],
            'status': ['credit', 'payment']
        })
        mock_read_csv.return_value = mock_df

        # Mock supplier creation
        mock_supplier = MagicMock()
        mock_supplier.id = 1
        mock_get_supplier.return_value = mock_supplier

        # Mock the query to check for existing records
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        # Call the function
        inserted, updated = ingest_creditors_aging(mock_db, 'aging.csv')

        # Assertions
        self.assertEqual(inserted, 2)  # Should insert 2 records
        self.assertEqual(updated, 0)  # No updates
        mock_read_csv.assert_called_once_with('aging.csv')
        self.assertEqual(mock_db.add.call_count, 2)
        mock_db.commit.assert_called_once()

    @patch('src.etl.etl.get_db_session')
    @patch('src.etl.etl.ingest_bank_statements')
    @patch('src.etl.etl.ingest_creditors_aging')
    def test_run_etl(self, mock_ingest_aging, mock_ingest_bank, mock_get_db_session):
        """Test that run_etl correctly calls the component functions."""
        # Set up mocks
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_db
        mock_get_db_session.return_value = mock_session

        mock_ingest_bank.return_value = 2
        mock_ingest_aging.return_value = (3, 1)

        # Call the function
        run_etl(['bank1.csv', 'bank2.csv'], 'aging.csv')

        # Assertions
        mock_ingest_bank.assert_called_once_with(mock_db, ['bank1.csv', 'bank2.csv'])
        mock_ingest_aging.assert_called_once_with(mock_db, 'aging.csv')


if __name__ == '__main__':
    unittest.main()
