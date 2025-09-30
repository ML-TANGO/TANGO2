from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)

def get_service_id():
    return os.environ["SERVICE_ID"]


def test_items():
    response = client.get("/items", params={})
    assert response.status_code == 200
    assert response.json() == [
        {"Hello": "World"},
        {"CI": "CD"},
        {"ServiceID": get_service_id()}
    ]



