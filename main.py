# API de Livros

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends
from fastapi import Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
import secrets
import os

import redis
from tasks import fatorial, somar
# from celery_app import celery_app
# from celery.result import AsyncResult
# from kafka_producer import enviar_evento

from sqlalchemy import create_engine, Column, Integer, String, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session


def configurar_logging_arquivo() -> None:
    # Logs operacionais (uvicorn/app) ficam separados do log estruturado ingerido pelo Logstash.
    log_file = os.getenv("LOG_FILE_PATH", "./logs/local-dev.log")
    audit_log_file = os.getenv("AUDIT_LOG_FILE_PATH", "./logs/app.log")
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    audit_log_dir = os.path.dirname(audit_log_file)
    if audit_log_dir:
        os.makedirs(audit_log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Evita adicionar handlers duplicados quando o processo reinicializa em modo dev.
    ja_configurado = any(
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", "") == file_handler.baseFilename
        for handler in root_logger.handlers
    )

    if not ja_configurado:
        root_logger.addHandler(file_handler)

    audit_logger_obj = logging.getLogger("audit")
    audit_logger_obj.setLevel(logging.INFO)
    audit_logger_obj.propagate = False

    audit_formatter = logging.Formatter("%(message)s")
    audit_file_handler = logging.FileHandler(audit_log_file, encoding="utf-8")
    audit_file_handler.setFormatter(audit_formatter)

    audit_ja_configurado = any(
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", "") == audit_file_handler.baseFilename
        for handler in audit_logger_obj.handlers
    )

    if not audit_ja_configurado:
        audit_logger_obj.addHandler(audit_file_handler)

    # Loggers do uvicorn devem propagar para o root, sem handlers extras.
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.setLevel(logging.INFO)
        uvicorn_logger.propagate = True

    # Reduz ruído de hot-reload no arquivo e no Elasticsearch.
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)


load_dotenv()
configurar_logging_arquivo()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não configurada. Defina DATABASE_URL no .env ou no shell antes de iniciar a API."
    )

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")


class RedisFallbackClient:
    def get(self, *_args, **_kwargs):
        return None

    def setex(self, *_args, **_kwargs):
        return True

    def lpush(self, *_args, **_kwargs):
        return 0

    def ltrim(self, *_args, **_kwargs):
        return True


try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
except Exception:
    redis_client = RedisFallbackClient()

app = FastAPI(
    title="API de Livros",
    description="API para gerenciar catálogo de livros.",
    version="1.0.0",
    contact={
        "name": "Atilio Hector",
        "email": "thehacktour@gmail.com"
    }
)

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


def extrair_usuario_basic_auth(request: Request) -> str:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("basic "):
        return "anonimo"

    token = auth_header.split(" ", 1)[1].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
        username = decoded.split(":", 1)[0].strip()
        return username if username else "anonimo"
    except Exception:
        return "anonimo"


def parse_int_param(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@app.middleware("http")
async def auditoria_requisicoes(request: Request, call_next):
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        status_code = response.status_code if response is not None else 500
        page = parse_int_param(request.query_params.get("page"))
        limit = parse_int_param(request.query_params.get("limit"))
        total_livros = None

        if request.url.path == "/livros" and response is not None and hasattr(response, "body"):
            body_content = getattr(response, "body", b"")
            if isinstance(body_content, bytes) and body_content:
                try:
                    payload = json.loads(body_content.decode("utf-8"))
                    total_livros = payload.get("total_livros")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    total_livros = None

        evento = {
            "endpoint": request.url.path,
            "limit": limit,
            "page": page,
            "status": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_livros": total_livros,
            "usuario": extrair_usuario_basic_auth(request),
        }
        audit_logger.info(json.dumps(evento, ensure_ascii=False))

security = HTTPBasic()

meus_livrozinhos = {}

class LivroDB(Base):
    __tablename__ = "livros"
    id = Column(Integer, primary_key=True, index=True)
    nome_livro = Column(String, index=True)
    autor_livro = Column(String, index=True)
    ano_livro = Column(Integer)

    def __init__(self, **kwargs):
        if "titulo" in kwargs and "nome_livro" not in kwargs:
            kwargs["nome_livro"] = kwargs.pop("titulo")
        if "autor" in kwargs and "autor_livro" not in kwargs:
            kwargs["autor_livro"] = kwargs.pop("autor")
        if "lancamento" in kwargs and "ano_livro" not in kwargs:
            kwargs["ano_livro"] = kwargs.pop("lancamento")
        super().__init__(**kwargs)

    @property
    def titulo(self):
        return self.nome_livro

    @titulo.setter
    def titulo(self, value):
        self.nome_livro = value

    @property
    def autor(self):
        return self.autor_livro

    @autor.setter
    def autor(self, value):
        self.autor_livro = value

    @property
    def lancamento(self):
        return self.ano_livro

    @lancamento.setter
    def lancamento(self, value):
        self.ano_livro = value

class Livro(BaseModel):
    nome_livro: str
    autor_livro: str
    ano_livro: int


def migrar_schema_livros_compatibilidade():
    inspector = inspect(engine)
    if not inspector.has_table("livros"):
        return

    colunas_existentes = {col["name"] for col in inspector.get_columns("livros")}

    with engine.begin() as conn:
        if "nome_livro" not in colunas_existentes:
            conn.execute(text("ALTER TABLE livros ADD COLUMN nome_livro TEXT"))
            colunas_existentes.add("nome_livro")

        if "autor_livro" not in colunas_existentes:
            conn.execute(text("ALTER TABLE livros ADD COLUMN autor_livro TEXT"))
            colunas_existentes.add("autor_livro")

        if "ano_livro" not in colunas_existentes:
            conn.execute(text("ALTER TABLE livros ADD COLUMN ano_livro INTEGER"))
            colunas_existentes.add("ano_livro")

        if "titulo" in colunas_existentes and "nome_livro" in colunas_existentes:
            conn.execute(text("UPDATE livros SET nome_livro = titulo WHERE nome_livro IS NULL"))

        if "autor" in colunas_existentes and "autor_livro" in colunas_existentes:
            conn.execute(text("UPDATE livros SET autor_livro = autor WHERE autor_livro IS NULL"))

        if "lancamento" in colunas_existentes and "ano_livro" in colunas_existentes:
            conn.execute(text("UPDATE livros SET ano_livro = lancamento WHERE ano_livro IS NULL"))


Base.metadata.create_all(bind=engine)
migrar_schema_livros_compatibilidade()

# def salvar_livro_redis(livro_id: int, livro: Livro):
#     redis_client.set(f"livro:{livro_id}", json.dumps(livro.dict()))

# def deletar_livro_redis(livro_id: int):
#     redis_client.delete(f"livro:{livro_id}")

def sessao_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db():
    yield from sessao_db()

def autenticar_meu_usuario(credentials: HTTPBasicCredentials = Depends(security)):
    meu_usuario = os.getenv("MEU_USUARIO")
    minha_senha = os.getenv("MINHA_SENHA")

    if meu_usuario is None or minha_senha is None:
        raise HTTPException(
            status_code=500,
            detail="Credenciais de autenticação não configuradas",
        )

    is_username_correct = secrets.compare_digest(credentials.username, meu_usuario)
    is_password_correct = secrets.compare_digest(credentials.password, minha_senha)

    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=401,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Basic"}
        )

    return credentials

@app.get("/")
def hello_world():
    logger.info("Endpoint raiz chamado")
    return {"message": "Bem-vindo à API de Livros!"}

@app.post("/calcular/soma")
def calcular_soma(a: int, b: int):
    tarefa = somar.delay(a, b)
    payload = {"a": a, "b": b}
    redis_client.setex(f"tarefa:{tarefa.id}", 3600, json.dumps(payload))
    redis_client.lpush("tarefas_ids", tarefa.id)
    redis_client.ltrim("tarefas_ids", 0, 49)
    return {
        "task_id": tarefa.id,
        "tipo": "soma",
        "entrada": payload,
        "status": "Pendente",
        "message": "Tarefa de soma iniciada. Use a lista de tarefas para acompanhar o andamento.",
    }


@app.post("/calcular/fatorial")
def calcular_fatorial(n: int):
    tarefa = fatorial.delay(n)
    payload = {"n": n}
    redis_client.setex(f"tarefa:{tarefa.id}", 3600, json.dumps(payload))
    redis_client.lpush("tarefas_ids", tarefa.id)
    redis_client.ltrim("tarefas_ids", 0, 49)
    return {
        "task_id": tarefa.id,
        "tipo": "fatorial",
        "entrada": payload,
        "status": "Pendente",
        "message": "Tarefa de fatorial iniciada. Use a lista de tarefas para acompanhar o andamento.",
    }

# @app.get("/tarefas/recentes")
# def listar_tarefas_recentes():
#     ids = redis_client.lrange("tarefas_ids", 0, -1)
#     tarefas = []
#     for task_id in ids:
#         resultado = AsyncResult(task_id, app=celery_app)
#         tarefas.append({
#             "task_id": task_id,
#             "status": resultado.status,
#             "resultado": resultado.result if resultado.successful() else None
#         })
#     return {
#         "tarefas": tarefas
#     }

# @app.get("/debug/redis")
# def ver_livros_redis():
#     chaves = redis_client.keys("livros:*")
#     livros = []
#     for chave in chaves:
#         valor = redis_client.get(chave)
#         ttl = redis_client.ttl(chave)
#         livros.append({"chave": chave, "valor": json.loads(valor), "ttl": ttl})
#     return livros

@app.get("/livros")
def get_livros(
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db),
    credentials: HTTPBasicCredentials = Depends(autenticar_meu_usuario)
):
    logger.info("Listando livros", extra={"page": page, "limit": limit})
    if page < 1 or limit < 1:
        raise HTTPException(status_code=400, detail="Page ou limit estão com valores inválidos!!!")

    # cache_key = f"livros:page={page}&limit={limit}"
    # cached = redis_client.get(cache_key) 
    # if cached:
    #     return json.loads(cached)

    livros = db.query(LivroDB).offset((page - 1) * limit).limit(limit).all()

    if not livros:
        return {"total_livros": 0, "livros": []}
    
    total_livros = db.query(LivroDB).count()

    resposta = {
        "total_livros": total_livros,
        "livros": [
            {
                "id": livro.id,
                "titulo": livro.nome_livro,
                "autor": livro.autor_livro,
                "lancamento": livro.ano_livro
            } for livro in livros
        ]
    }

    # redis_client.setex(cache_key, 30, json.dumps(resposta))

    return resposta

@app.post("/adiciona")
async def post_livros(livro: Livro, db: Session = Depends(get_db), credentials: HTTPBasicCredentials = Depends(autenticar_meu_usuario)):
    logger.info("Criando livro", extra={"nome_livro": livro.nome_livro, "autor_livro": livro.autor_livro})
    db_livro = db.query(LivroDB).filter(LivroDB.nome_livro == livro.nome_livro, LivroDB.autor_livro == livro.autor_livro).first()
    if db_livro:
        raise HTTPException(status_code=400, detail="Esse livro já existe dentro do banco de dados!!!")

    novo_livro = LivroDB(nome_livro=livro.nome_livro, autor_livro=livro.autor_livro, ano_livro=livro.ano_livro)
    db.add(novo_livro)
    db.commit()
    db.refresh(novo_livro)

    # salvar_livro_redis(novo_livro.id, livro)

    # enviar_evento("livros_eventos", {
    #     "acao": "criar",
    #     "livro": livro.dict()
    # })

    return {"message": "O livro foi criado com sucesso!"}

@app.put("/atualiza/{id_livro}")
async def put_livros(id_livro: int, livro: Livro, db: Session = Depends(get_db), credentials: HTTPBasicCredentials = Depends(autenticar_meu_usuario)):
    logger.info("Atualizando livro", extra={"id_livro": id_livro})
    db_livro = db.query(LivroDB).filter(LivroDB.id == id_livro).first()
    if not db_livro:
        raise HTTPException(status_code=404, detail="Este livro não foi encontrado no seu banco de dados!")
    
    db_livro.nome_livro = livro.nome_livro
    db_livro.autor_livro = livro.autor_livro
    db_livro.ano_livro = livro.ano_livro

    db.commit()
    db.refresh(db_livro)

    return {"message": "O livro foi atualizado com sucesso!!!"}

@app.delete("/deletar/{id_livro}")
async def delete_livro(id_livro: int, db: Session = Depends(get_db), credentials: HTTPBasicCredentials = Depends(autenticar_meu_usuario)):
    logger.info("Deletando livro", extra={"id_livro": id_livro})
    db_livro = db.query(LivroDB).filter(LivroDB.id == id_livro).first()
    if not db_livro:
        raise HTTPException(status_code=404, detail="Este livro não foi encontrado no seu banco de dados!!!")

    db.delete(db_livro)
    db.commit()

    # deletar_livro_redis(id_livro)

    return {"message": "Seu livro foi deletado com sucesso!"}