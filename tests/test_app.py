import pytest
import os
import tempfile
import shutil
from fastapi.testclient import TestClient
from platform_lookup.app import app, INSTALLATION_PASSWORD

client = TestClient(app)

# Valid Z85-encoded test public keys (40 characters each)
TEST_PUBLIC_KEY_1 = "Yne@$w-vo<+T1ed:M$fkMC]IaLV{hID,4IcQ]=IW}"
TEST_PUBLIC_KEY_2 = "D-na+B=>mqLvxm3fr+R(!!!61d66yLk/=ALw}#~d"


@pytest.fixture
def isolated_volttron_home():
    """
    Create an isolated temporary VOLTTRON_HOME for tests.
    Sets it in the environment and cleans up after the test.
    """
    # Save original VOLTTRON_HOME
    original_volttron_home = os.environ.get("VOLTTRON_HOME")

    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="volttron_test_")

    # Set temporary VOLTTRON_HOME
    os.environ["VOLTTRON_HOME"] = temp_dir

    yield temp_dir

    # Cleanup: restore original VOLTTRON_HOME and remove temp directory
    if original_volttron_home is not None:
        os.environ["VOLTTRON_HOME"] = original_volttron_home
    else:
        os.environ.pop("VOLTTRON_HOME", None)

    # Remove temporary directory and all its contents
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

def test_registration_success(isolated_volttron_home):
    payload = {
        "id": "test-platform",
        "address": "tcp://localhost:5555",
        "public_credentials": TEST_PUBLIC_KEY_1,
        "group": "test"
    }
    response = client.post("/platform", json=payload, headers={"Registration-Password": INSTALLATION_PASSWORD})
    assert response.status_code == 201
    assert response.json()["id"] == "test-platform"

    # Cleanup: delete the registered platform
    cleanup_response = client.delete("/platform/test-platform", headers={"Registration-Password": INSTALLATION_PASSWORD})
    assert cleanup_response.status_code == 200

def test_registration_invalid_password(isolated_volttron_home):
    payload = {
        "id": "test-platform-fail",
        "address": "tcp://localhost:5555",
        "public_credentials": TEST_PUBLIC_KEY_1,
        "group": "test"
    }
    response = client.post("/platform", json=payload, headers={"Registration-Password": "wrongpassword"})
    assert response.status_code == 401

def test_read_platforms_success(isolated_volttron_home):
    # List platforms with valid master password
    response = client.get("/platforms", headers={"Registration-Password": INSTALLATION_PASSWORD})
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_read_platforms_no_auth(isolated_volttron_home):
    response = client.get("/platforms")
    assert response.status_code == 401

def test_update_platform_unauthorized(isolated_volttron_home):
    # Try updating with wrong password (header provided but invalid)
    payload = {
        "id": "test-platform",
        "address": "tcp://localhost:5556",
        "public_credentials": TEST_PUBLIC_KEY_2,
        "group": "test"
    }
    response = client.put("/platform/test-platform",
                          json=payload,
                          headers={"Registration-Password": "wrongpassword"})
    assert response.status_code == 401

def test_update_platform_missing_password(isolated_volttron_home):
    # Try updating without auth header (missing required header)
    payload = {
        "id": "test-platform",
        "address": "tcp://localhost:5556",
        "public_credentials": TEST_PUBLIC_KEY_2,
        "group": "test"
    }
    response = client.put("/platform/test-platform", json=payload)
    assert response.status_code == 422

def test_update_platform_success(isolated_volttron_home):
    # First register a platform
    register_payload = {
        "id": "test-platform",
        "address": "tcp://localhost:5555",
        "public_credentials": TEST_PUBLIC_KEY_1,
        "group": "test"
    }
    client.post("/platform", json=register_payload, headers={"Registration-Password": INSTALLATION_PASSWORD})

    # Update with master password
    payload = {
        "id": "test-platform",
        "address": "tcp://localhost:5556",
        "public_credentials": TEST_PUBLIC_KEY_2,
        "group": "test"
    }
    response = client.put("/platform/test-platform",
                          json=payload,
                          headers={"Registration-Password": INSTALLATION_PASSWORD})
    assert response.status_code == 201

    # Cleanup: delete the registered platform
    cleanup_response = client.delete("/platform/test-platform", headers={"Registration-Password": INSTALLATION_PASSWORD})
    assert cleanup_response.status_code == 200
