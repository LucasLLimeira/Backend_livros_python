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
import redis
import json
from redis.exceptions import RedisError

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

import asyncio

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)), db=0, decode_responses=True)

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
        redis_client.set(
            f"livro:{livro.id}",
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

@app.get("/debug/redis")
async def debug_redis():
    try:
        keys = redis_client.keys("livro:*")
        livros = []
        for key in keys:
            livro = redis_client.get(key)
            if livro:
                livros.append(json.loads(livro))
        return {"redis_status": "ok", "livros": livros}
    except RedisError:
        return {"redis_status": "indisponivel", "livros": []}

@app.get("/livros")
async def ler_livros(page: int = 1, limit: int = 10, db: Session = Depends(get_db), credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    if page < 1 or limit < 1:
        raise HTTPException(status_code=400, detail="Page e limit devem ser maiores que 0")
    
    livros = db.query(LivroDB).offset((page - 1) * limit).limit(limit).all()

    if not livros:
        raise HTTPException(status_code=404, detail="Nenhum livro encontrado")
    
    total_livros = db.query(LivroDB).count()

    return {
        "page": page,
        "limit": limit,
        "total_livros": total_livros,
        "livros": [{"id": livro.id, "titulo": livro.titulo, "autor": livro.autor, "lancamento": livro.lancamento} for livro in livros]
    }

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