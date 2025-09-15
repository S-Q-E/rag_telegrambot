# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

# Добавляем путь к проекту, чтобы можно было импортировать api.main
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Моки для OpenAI и зависимостей ---

# Мокаем AsyncOpenAI клиент до его импорта в других модулях
@pytest.fixture(autouse=True)
def mock_openai_client():
    with patch('api.llm_client.AsyncOpenAI') as mock_client_llm, \
         patch('api.retriever.AsyncOpenAI') as mock_client_retriever:
        
        # Мок для Chat Completion
        mock_chat_response = MagicMock()
        mock_chat_response.choices = [MagicMock()]
        mock_chat_response.choices[0].message.content = "Mocked OpenAI response"
        mock_client_llm.return_value.chat.completions.create = AsyncMock(return_value=mock_chat_response)

        # Мок для Embeddings
        mock_embedding_response = MagicMock()
        mock_embedding_response.data = [MagicMock()]
        mock_embedding_response.data[0].embedding = [0.1] * 1536
        mock_client_retriever.return_value.embeddings.create = AsyncMock(return_value=mock_embedding_response)
        
        yield mock_client_llm, mock_client_retriever

# Устанавливаем переменную окружения до импорта main
os.environ['OPENAI_API_KEY'] = 'fake-key'

from api.main import app, get_db

# --- Моки для БД ---
@pytest.fixture
def db_session_mock():
    return MagicMock()

@pytest.fixture(autouse=True)
def override_get_db(db_session_mock):
    app.dependency_overrides[get_db] = lambda: db_session_mock
    yield
    app.dependency_overrides = {}

# --- Тесты ---
client = TestClient(app)

@patch('api.main.os.path.exists', return_value=True)
@patch('api.retriever.Retriever.search', new_callable=AsyncMock) 
def test_query_with_context(mock_search, mock_os_exists, mock_openai_client):
    """Тест: API находит контекст и генерирует ответ через ChatCompletion."""
    mock_search.return_value = ["some relevant context"]
    mock_chat_client, _ = mock_openai_client

    response = client.post("/query", json={"assistant": "shop", "query": "test", "user_id": 123})
    
    assert response.status_code == 200
    assert response.json()["response"] == "Mocked OpenAI response"
    # Проверяем, что поиск был вызван
    mock_search.assert_called_once()
    # Проверяем, что ChatCompletion был вызван
    mock_chat_client.return_value.chat.completions.create.assert_called_once()

@patch('api.main.os.path.exists', return_value=True)
@patch('api.retriever.Retriever.search', new_callable=AsyncMock)
def test_query_no_context_fallback(mock_search, mock_os_exists, mock_openai_client):
    """Тест: API не находит контекст и возвращает fallback-ответ, не вызывая ChatCompletion."""
    mock_search.return_value = []  # Ретривер ничего не нашел
    mock_chat_client, _ = mock_openai_client

    response = client.post("/query", json={"assistant": "shop", "query": "test", "user_id": 123})
    
    assert response.status_code == 200
    assert response.json()["response"] == "К сожалению, я не нашел информации по вашему вопросу."
    # Проверяем, что поиск был вызван
    mock_search.assert_called_once()
    # Убеждаемся, что ChatCompletion НЕ был вызван
    mock_chat_client.return_value.chat.completions.create.assert_not_called()

@pytest.mark.asyncio
async def test_embedding_generation(mock_openai_client):
    """Юнит-тест для проверки вызова генерации эмбеддингов."""
    from api.retriever import get_openai_embedding
    _, mock_embedding_client = mock_openai_client

    embedding = await get_openai_embedding("test text")

    assert embedding == [0.1] * 1536
    # Проверяем, что метод create у embeddings был вызван с нужными параметрами
    mock_embedding_client.return_value.embeddings.create.assert_called_once_with(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        input=["test text"]
    )