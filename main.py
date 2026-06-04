# API de Livros

#GET, POST, PUT, DELETE

#Get - Ler dados
#Post - Criar dados
#Put - Atualizar dados
#Delete - Deletar dados

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import Optional
import secrets
import os
import math
from datetime import datetime
import redis
import json
from redis.exceptions import RedisError
from fastapi import BackgroundTasks
from tasks import somar, fatorial
from celery_app import celery_app
from celery.result import AsyncResult

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

import asyncio

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

redis_client = redis.Redis(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT", 6379)), db=0, decode_responses=True)
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 30))
TASK_HISTORY_KEY = "calcular:tarefas"
TASK_HISTORY_LIMIT = 20
TASK_RECORD_TTL_SECONDS = 24 * 60 * 60
TASK_PAGE_SIZE = 10

app = FastAPI(
    title="API de Livros",
    description="API para gerenciar uma coleção de livros",
    version="1.0.0",
    contact={
        "name": "Lucas Limeira",
        "email": "lucasdllimeira@gmail.com"
    }
)

MEU_USUARIO = os.getenv("MEU_USUARIO")
MINHA_SENHA = os.getenv("MINHA_SENHA")

security = HTTPBasic()

class LivroDB(Base):
    __tablename__ = "livros"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, index=True)
    autor = Column(String, index=True)
    lancamento = Column(Integer)

class Livro(BaseModel):
    titulo: str
    autor: str
    lancamento: int

Base.metadata.create_all(bind=engine)

def salvar_livro_cache(livro: LivroDB):
    try:
        redis_client.setex(
            f"livro:{livro.id}",
            CACHE_TTL_SECONDS,
            json.dumps(
                {
                    "id": livro.id,
                    "titulo": livro.titulo,
                    "autor": livro.autor,
                    "lancamento": livro.lancamento,
                }
            ),
        )
        return True
    except RedisError:
        return False

def deletar_livro_cache(id: int):
    try:
        redis_client.delete(f"livro:{id}")
        return True
    except RedisError:
        return False

def registrar_tarefa(task_id: str, tipo: str, entrada: dict):
    tarefa = {
        "task_id": task_id,
        "tipo": tipo,
        "entrada": entrada,
        "status": "Pendente",
        "resultado": None,
        "criada_em": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

    try:
        redis_client.setex(
            f"calcular:task:{task_id}",
            TASK_RECORD_TTL_SECONDS,
            json.dumps(tarefa),
        )
        redis_client.lpush(TASK_HISTORY_KEY, task_id)
        redis_client.ltrim(TASK_HISTORY_KEY, 0, TASK_HISTORY_LIMIT - 1)
    except RedisError:
        pass

    return tarefa


def formatar_status_tarefa(task_id: str):
    tarefa_salva = None
    try:
        tarefa_bruta = redis_client.get(f"calcular:task:{task_id}")
        if tarefa_bruta:
            tarefa_salva = json.loads(tarefa_bruta)
    except RedisError:
        pass

    task_result = AsyncResult(task_id, app=celery_app)
    status_map = {
        "PENDING": "Pendente",
        "STARTED": "Em execução",
        "SUCCESS": "Concluída",
        "FAILURE": "Falhou",
    }
    status = status_map.get(task_result.state, task_result.state)

    resposta = tarefa_salva or {"task_id": task_id}
    resposta.update(
        {
            "status": status,
            "resultado": task_result.result if task_result.state == "SUCCESS" else (str(task_result.result) if task_result.state == "FAILURE" else None),
        }
    )
    return resposta


def total_tarefas_registradas() -> int:
    try:
        return redis_client.llen(TASK_HISTORY_KEY)
    except RedisError:
        return 0

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def autenticar_usuario(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, MEU_USUARIO)
    correct_password = secrets.compare_digest(credentials.password, MINHA_SENHA)
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

@app.get("/")
async def ler_raiz():
    return {"message": "Bem-vindo à API de Livros!"}

@app.post("/calcular/soma")
async def calcular_soma(a: int, b: int, background_tasks: BackgroundTasks):
    task = somar.delay(a, b)
    registrar_tarefa(task.id, "soma", {"a": a, "b": b})
    return {
        "task_id": task.id,
        "tipo": "soma",
        "entrada": {"a": a, "b": b},
        "status": "Pendente",
        "message": "Tarefa de soma iniciada. Use a lista de tarefas para acompanhar o andamento.",
    }

@app.post("/calcular/fatorial")
async def calcular_fatorial(n: int, background_tasks: BackgroundTasks):
    task = fatorial.delay(n)
    registrar_tarefa(task.id, "fatorial", {"n": n})
    return {
        "task_id": task.id,
        "tipo": "fatorial",
        "entrada": {"n": n},
        "status": "Pendente",
        "message": "Tarefa de fatorial iniciada. Use a lista de tarefas para acompanhar o andamento.",
    }

@app.get("/calcular/tarefas")
async def listar_tarefas(page: int = 1):
    if page < 1:
        raise HTTPException(status_code=400, detail="Page deve ser maior que zero.")

    try:
        total_tarefas = total_tarefas_registradas()
        offset = (page - 1) * TASK_PAGE_SIZE
        task_ids = redis_client.lrange(TASK_HISTORY_KEY, offset, offset + TASK_PAGE_SIZE - 1)
    except RedisError:
        total_tarefas = 0
        task_ids = []

    tarefas = [formatar_status_tarefa(task_id) for task_id in task_ids]
    return {
        "page": page,
        "limit": TASK_PAGE_SIZE,
        "total_tarefas": total_tarefas,
        "total_paginas": math.ceil(total_tarefas / TASK_PAGE_SIZE) if total_tarefas else 0,
        "tarefas": tarefas,
    }

@app.get("/calcular/tarefas/{task_id}")
async def obter_tarefa(task_id: str):
    tarefa = formatar_status_tarefa(task_id)
    return {
        "task_id": tarefa["task_id"],
        "tipo": tarefa.get("tipo"),
        "entrada": tarefa.get("entrada"),
        "status": tarefa["status"],
        "result": tarefa.get("resultado"),
        "criada_em": tarefa.get("criada_em"),
    }

@app.get("/debug/redis")
async def debug_redis():
    try:
        itens_cache = []
        for pattern in ("livro:*", "livros:*"):
            keys = redis_client.keys(pattern)
            for key in keys:
                valor = redis_client.get(key)
                if not valor:
                    continue

                ttl = redis_client.ttl(key)
                itens_cache.append(
                    {
                        "chave": key,
                        "ttl_segundos_restantes": ttl if ttl >= 0 else None,
                        "valor": json.loads(valor),
                    }
                )

        return {
            "redis_status": "ok",
            "ttl_padrao_segundos": CACHE_TTL_SECONDS,
            "itens_cache": itens_cache,
        }
    except RedisError:
        return {"redis_status": "indisponivel", "itens_cache": []}

@app.get("/livros")
async def ler_livros(page: int = 1, limit: int = 10, db: Session = Depends(get_db), credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    if page < 1 or limit < 1:
        raise HTTPException(status_code=400, detail="Page ou limit estão com valores inválidos.")

    cache_livros = f"livros:page={page}&limit={limit}"
    try:
        cached = redis_client.get(cache_livros)
        if cached:
            return json.loads(cached)
    except RedisError:
        pass
    
    livros = db.query(LivroDB).offset((page - 1) * limit).limit(limit).all()

    if not livros:
        raise HTTPException(status_code=404, detail="Nenhum livro encontrado")
    
    total_livros = db.query(LivroDB).count()

    resposta = {
        "page": page,
        "limit": limit,
        "total_livros": total_livros,
        "livros": [{"id": livro.id, "titulo": livro.titulo, "autor": livro.autor, "lancamento": livro.lancamento} for livro in livros]
    }

    try:
        redis_client.setex(cache_livros, CACHE_TTL_SECONDS, json.dumps(resposta))
    except RedisError:
        pass

    return resposta

@app.post("/adicionar_livros")
async def criar_livro(livro: Livro, db: Session = Depends(get_db), credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    if db.query(LivroDB).filter(LivroDB.titulo == livro.titulo, LivroDB.autor == livro.autor).first():
        raise HTTPException(status_code=400, detail="Livro já existe")
    else:
        novo_livro = LivroDB(titulo=livro.titulo, autor=livro.autor, lancamento=livro.lancamento)
        db.add(novo_livro)
        db.commit()
        db.refresh(novo_livro)
        cache_salvo = salvar_livro_cache(novo_livro)

    response = {
        "detail": "Livro adicionado com sucesso",
        "livro": {
            "id": novo_livro.id,
            "titulo": novo_livro.titulo,
            "autor": novo_livro.autor,
            "lancamento": novo_livro.lancamento,
        },
    }

    if not cache_salvo:
        response["cache_warning"] = "Livro salvo no banco, mas o Redis esta indisponivel"

    return response

@app.put("/atualizar_livros/{id}")
async def atualizar_livro(id: int, livro: Livro, db: Session = Depends(get_db), credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    livro_db = db.query(LivroDB).filter(LivroDB.id == id).first()
    if not livro_db:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    livro_db.titulo = livro.titulo
    livro_db.autor = livro.autor
    livro_db.lancamento = livro.lancamento
    db.commit()
    db.refresh(livro_db)
    cache_salvo = salvar_livro_cache(livro_db)

    response = {
        "detail": "Livro atualizado com sucesso",
        "livro": {
            "id": livro_db.id,
            "titulo": livro_db.titulo,
            "autor": livro_db.autor,
            "lancamento": livro_db.lancamento,
        },
    }

    if not cache_salvo:
        response["cache_warning"] = "Livro atualizado no banco, mas o Redis esta indisponivel"

    return response

@app.delete("/deletar_livros/{id}")
async def deletar_livro(id: int, db: Session = Depends(get_db), credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    livro_db = db.query(LivroDB).filter(LivroDB.id == id).first()
    if not livro_db:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    db.delete(livro_db)
    db.commit()
    cache_deletado = deletar_livro_cache(id)
    if not cache_deletado:
        return {
            "detail": "Livro deletado com sucesso",
            "cache_warning": "Livro removido do banco, mas o Redis esta indisponivel",
        }
    return {"detail": "Livro deletado com sucesso"}