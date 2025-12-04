import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

# Добавляем корень проекта в путь, чтобы видеть модули
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Мокаем базу и бота ДО импорта main_webapp
with patch("database.init_db"), \
     patch("common_functions.bot"):
    from main_webapp import app, WEBAPP_TOKEN

client = TestClient(app)

# Мокаем данные БД
@pytest.fixture
def mock_db():
    with patch("database.get_all_courses", return_value=[1, 2]), \
         patch("database.get_topics_by_course", return_value=["Тема 1"]), \
         patch("database.get_lecture", return_value=(1, 1, "Тема 1", "audio_123", None, None, None)):
        yield

def test_get_courses(mock_db):
    response = client.get("/api/courses")
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "title": "Курс 1"}, {"id": 2, "title": "Курс 2"}]

def test_request_file_success(mock_db):
    # Мокаем отправку
    with patch("common_functions.bot.send_document") as mock_send:
        payload = {
            "telegram_id": 123,
            "file_id": "file_123",
            "webapp_token": WEBAPP_TOKEN
        }
        response = client.post("/api/request_file", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_send.assert_called_once()

def test_request_file_bad_token():
    payload = {
        "telegram_id": 123,
        "file_id": "file_123",
        "webapp_token": "WRONG_TOKEN"
    }
    response = client.post("/api/request_file", json=payload)
    assert response.status_code == 403