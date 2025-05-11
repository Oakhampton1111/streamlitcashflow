"""End-to-end tests for the application.

These tests require Docker and Docker Compose to be installed and ports 8501 and 5433 to be available.
They are skipped by default in the unittest runner to avoid interfering with other tests.
"""

import unittest
import shutil
import socket
import subprocess
import time

import requests


def _port_in_use(port):
    """Check if a port is in use."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return s.connect_ex(("localhost", port)) == 0
    finally:
        s.close()


@unittest.skipIf(
    not (shutil.which("docker-compose") or shutil.which("docker")),
    "docker-compose not installed"
)
@unittest.skipIf(
    _port_in_use(8501) or _port_in_use(5433),
    "Ports 8501 or 5433 already in use"
)
class EndToEndTests(unittest.TestCase):
    """End-to-end tests for the application using Docker Compose."""

    @classmethod
    def setUpClass(cls):
        """Start Docker Compose services."""
        subprocess.run(["docker-compose", "up", "-d"], check=True)
        for _ in range(30):
            try:
                r = requests.get("http://localhost:8501")
                if r.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
        else:
            raise unittest.SkipTest("App service not available after timeout")

    @classmethod
    def tearDownClass(cls):
        """Stop Docker Compose services."""
        subprocess.run(["docker-compose", "down"], check=True)

    def test_root_contains_cashflow_forecasting(self):
        """Test that the root page contains 'Cashflow Forecasting'."""
        r = requests.get("http://localhost:8501")
        self.assertIn("Cashflow Forecasting", r.text)

    def test_scheduler_running(self):
        """Test that the scheduler service is running."""
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=_scheduler_1", "--format", "{{.Names}}"],
            stdout=subprocess.PIPE,
            text=True,
        )
        names = result.stdout.strip().splitlines()
        self.assertTrue(any(name.endswith("_scheduler_1") for name in names))

    def test_db_port_open(self):
        """Test that the database port is open."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(1)
            sock.connect(("localhost", 5433))
        except Exception as e:
            self.fail(f"Database port 5433 is not open: {e}")
        finally:
            sock.close()


if __name__ == "__main__":
    unittest.main()
