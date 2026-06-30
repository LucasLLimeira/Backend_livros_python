import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import Base, get_db, app
from fastapi.testclient import TestClient
import os

DATABASE_URL_TEST = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL_TEST, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(bind=engine)

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_redis(mocker):
    mock_redis_client = mocker.patch("main.redis_client", autospec=True)
    mock_redis_client.get.return_value = None

@pytest.fixture(scope="function")
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_get_books(db, mocker):
    
    response = client.get("/livros", auth=("lucas", "123456"))
    assert response.status_code == 200

    data = response.json()

    assert len(data["livros"]) == 10 
    assert data["livros"][0]["titulo"] == "Dom Casmurro"
    assert data["livros"][0]["autor"] == "Machado de Assis"
    assert data["livros"][0]["lancamento"] == 1899