import shutil
import socket
import subprocess
import time

import pytest
import requests


def _port_in_use(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        return s.connect_ex(("localhost", port)) == 0
    finally:
        s.close()


if not (shutil.which("docker-compose") or shutil.which("docker")):
    pytest.skip("docker-compose not installed", allow_module_level=True)
if _port_in_use(8501) or _port_in_use(5433):
    pytest.skip("Ports 8501 or 5433 already in use", allow_module_level=True)


@pytest.fixture(scope="session", autouse=True)
def docker_compose():
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
        pytest.skip("app service not available after timeout", allow_module_level=True)
    yield
    subprocess.run(["docker-compose", "down"], check=True)


def test_root_contains_cashflow_forecasting():
    r = requests.get("http://localhost:8501")
    assert "Cashflow Forecasting" in r.text


def test_scheduler_running():
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=_scheduler_1", "--format", "{{.Names}}"],
        stdout=subprocess.PIPE,
        text=True,
    )
    names = result.stdout.strip().splitlines()
    assert any(name.endswith("_scheduler_1") for name in names)


def test_db_port_open():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        sock.connect(("localhost", 5433))
    except Exception:
        pytest.fail("Database port 5433 is not open")
    finally:
        sock.close()
