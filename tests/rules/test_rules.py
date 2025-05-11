"""Unit tests for the rules module."""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

# Use unittest directly instead of BaseTestCase
import unittest
from src.rules.rules import parse_and_apply_rule, apply_pending_rules, run_rules
from src.db.models import Supplier, RuleChange


class TestRules(unittest.TestCase):
    """Test cases for the rules module."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample rule texts
        self.valid_rule = "Supplier A: flex delay 10 days"
        self.invalid_rule = "Invalid rule format"
        self.unknown_supplier_rule = "Unknown Supplier: core delay 5 days"

    @patch('src.rules.rules.get_db_session')
    def test_parse_and_apply_rule_valid(self, mock_get_db_session):
        """Test that parse_and_apply_rule correctly processes a valid rule."""
        # Set up mocks
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_db
        mock_get_db_session.return_value = mock_session

        # Mock the supplier query
        mock_supplier = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_supplier

        # Call the function
        result = parse_and_apply_rule(self.valid_rule)

        # Assertions
        self.assertTrue(result)
        mock_db.add.assert_called_once()  # Should add a RuleChange record

        # Check that supplier was updated correctly
        self.assertEqual(mock_supplier.type, "flex")
        self.assertEqual(mock_supplier.max_delay_days, 10)

    @patch('src.rules.rules.get_db_session')
    def test_parse_and_apply_rule_invalid_format(self, mock_get_db_session):
        """Test that parse_and_apply_rule handles invalid rule format."""
        # Set up mocks
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_db
        mock_get_db_session.return_value = mock_session

        # Call the function
        result = parse_and_apply_rule(self.invalid_rule)

        # Assertions
        self.assertFalse(result)
        mock_db.add.assert_called_once()  # Should still add a RuleChange record

    @patch('src.rules.rules.get_db_session')
    def test_parse_and_apply_rule_unknown_supplier(self, mock_get_db_session):
        """Test that parse_and_apply_rule handles unknown supplier."""
        # Set up mocks
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_db
        mock_get_db_session.return_value = mock_session

        # Mock the supplier query to return None (supplier not found)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Call the function
        result = parse_and_apply_rule(self.unknown_supplier_rule)

        # Assertions
        self.assertFalse(result)
        mock_db.add.assert_called_once()  # Should still add a RuleChange record

    @patch('src.rules.rules.parse_and_apply_rule')
    @patch('src.rules.rules.get_db_session')
    def test_apply_pending_rules(self, mock_get_db_session, mock_parse_rule):
        """Test that apply_pending_rules processes all pending rules."""
        # Set up mocks
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_db
        mock_get_db_session.return_value = mock_session

        # Mock pending rules query
        mock_rule1 = MagicMock()
        mock_rule1.nl_text = "Rule 1"
        mock_rule2 = MagicMock()
        mock_rule2.nl_text = "Rule 2"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_rule1, mock_rule2]

        # Mock parse_and_apply_rule to succeed for first rule and fail for second
        mock_parse_rule.side_effect = [True, False]

        # Call the function
        applied, failed = apply_pending_rules()

        # Assertions
        self.assertEqual(applied, 1)
        self.assertEqual(failed, 1)
        self.assertEqual(mock_parse_rule.call_count, 2)

    @patch('src.rules.rules.apply_pending_rules')
    @patch('src.rules.rules.get_db_session')
    def test_run_rules(self, mock_get_db_session, mock_apply_rules):
        """Test that run_rules correctly calls apply_pending_rules."""
        # Set up mocks
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_db
        mock_get_db_session.return_value = mock_session

        # Mock suppliers and rules queries
        mock_supplier = MagicMock()
        mock_db.query.return_value.all.return_value = [mock_supplier]

        mock_apply_rules.return_value = (2, 1)

        # Call the function
        run_rules()

        # Assertions
        mock_apply_rules.assert_called_once()


if __name__ == '__main__':
    unittest.main()
