# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Добавляем путь к проекту, чтобы можно было импортировать api.main
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Мокаем тяжелые зависимости ДО их импорта в main
embedding_model_mock = MagicMock()
embedding_model_mock.encode.return_value = [0.1] * 384

# Применяем патчи
patcher_st = patch('sentence_transformers.SentenceTransformer', return_value=embedding_model_mock)
patcher_st.start()

from api.main import app, get_db

# --- Моки для БД ---
# Переопределяем зависимость get_db для тестов
@pytest.fixture
def db_session_mock():
    db = MagicMock()
    # Мокаем поиск в ретривере
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        MagicMock(content="mocked document content")
    ]
    return db

@pytest.fixture(autouse=True)
def override_get_db(db_session_mock):
    app.dependency_overrides[get_db] = lambda: db_session_mock
    yield
    app.dependency_overrides = {}

# --- Тесты ---
client = TestClient(app)

@patch('api.main.os.path.exists')
def test_query_endpoint_success(mock_exists):
    """Тест успешного ответа от эндпоинта /query."""
    mock_exists.return_value = True  # Имитируем, что конфиг ассистента существует

    response = client.post("/query", json={
        "assistant": "shop",
        "query": "сколько стоят часы?",
        "user_id": 123
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "mocked document content" in data["response"]

@patch('api.main.os.path.exists')
def test_query_assistant_not_found(mock_exists):
    """Тест ошибки, если ассистент не найден."""
    mock_exists.return_value = False # Имитируем, что конфиг НЕ существует

    response = client.post("/query", json={
        "assistant": "nonexistent",
        "query": "test",
        "user_id": 123
    })
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Assistant 'nonexistent' not found."

def test_health_check():
    """Тест эндпоинта /health."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

# Останавливаем патчер после тестов
patcher_st.stop()
