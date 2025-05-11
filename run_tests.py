#!/usr/bin/env python
"""Test runner for the Cashflow Forecast application."""

import unittest
import sys
import os

def run_tests():
    """Discover and run all tests in the tests directory."""
    # Add the project root to the Python path
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    
    # Discover and run tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover('tests', pattern='test_*.py')
    
    # Run tests with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests())
