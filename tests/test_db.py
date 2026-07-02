import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from main import Base, LivroDB, get_db, app
from fastapi.testclient import TestClient

DATABASE_URL_TEST = "sqlite://"
engine = create_engine(
    DATABASE_URL_TEST,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(bind=engine)

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_redis(mocker):
    mock_redis_client = mocker.patch("main.redis_client", autospec=True)
    mock_redis_client.get.return_value = None

@pytest.fixture(scope="function")
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def override_db(db):
    def _get_test_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _get_test_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def seed_books(db):
    livros = [
        LivroDB(titulo="Dom Casmurro", autor="Machado de Assis", lancamento=1899),
        LivroDB(titulo="Memórias Póstumas de Brás Cubas", autor="Machado de Assis", lancamento=1881),
        LivroDB(titulo="O Cortiço", autor="Aluísio Azevedo", lancamento=1890),
        LivroDB(titulo="Vidas Secas", autor="Graciliano Ramos", lancamento=1938),
        LivroDB(titulo="Grande Sertão: Veredas", autor="João Guimarães Rosa", lancamento=1956),
        LivroDB(titulo="Capitães da Areia", autor="Jorge Amado", lancamento=1937),
        LivroDB(titulo="A Hora da Estrela", autor="Clarice Lispector", lancamento=1977),
        LivroDB(titulo="Iracema", autor="José de Alencar", lancamento=1865),
        LivroDB(titulo="O Alienista", autor="Machado de Assis", lancamento=1882),
        LivroDB(titulo="Macunaíma", autor="Mário de Andrade", lancamento=1928),
    ]
    db.add_all(livros)
    db.commit()


def test_get_books(db, override_db, seed_books):
    response = client.get("/livros", auth=("lucas", "123456"))
    assert response.status_code == 200

    data = response.json()

    assert len(data["livros"]) == 10 
    assert data["livros"][0]["titulo"] == "Dom Casmurro"
    assert data["livros"][0]["autor"] == "Machado de Assis"
    assert data["livros"][0]["lancamento"] == 1899


def test_get_books_empty_returns_200(db, override_db):
    response = client.get("/livros", auth=("lucas", "123456"))
    assert response.status_code == 200

    data = response.json()
    assert data["total_livros"] == 0
    assert data["livros"] == []