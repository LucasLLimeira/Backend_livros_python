from fastapi.testclient import TestClient
from main import app
import pytest

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_redis(mocker):
    mock_redis_client = mocker.patch("main.redis_client", autospec=True)
    mock_redis_client.get.return_value = None

def test_autenticacao_valida():
    response = client.get("/livros", auth=("lucas", "123456"))
    assert response.status_code == 200

def test_autenticacao_invalida():
    response = client.get("/livros", auth=("lucas", "senha_errada"))
    assert response.status_code == 401
    assert response.json() == {"detail": "Usuário ou senha incorretos"}

def test_autenticacao_usuario_invalido():
    response = client.get("/livros", auth=("usuario_invalido", "123456"))
    assert response.status_code == 401
    assert response.json() == {"detail": "Usuário ou senha incorretos"}