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

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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
def ler_raiz():
    return {"message": "Bem-vindo à API de Livros!"}

@app.get("/livros")
def ler_livros(page: int = 1, limit: int = 10, db: Session = Depends(get_db), credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
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
def criar_livro(livro: Livro, db: Session = Depends(get_db), credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    if db.query(LivroDB).filter(LivroDB.titulo == livro.titulo, LivroDB.autor == livro.autor).first():
        raise HTTPException(status_code=400, detail="Livro já existe")
    else:
        novo_livro = LivroDB(titulo=livro.titulo, autor=livro.autor, lancamento=livro.lancamento)
        db.add(novo_livro)
        db.commit()
        db.refresh(novo_livro)
    return {"detail": "Livro adicionado com sucesso", "livro": {"id": novo_livro.id, "titulo": novo_livro.titulo, "autor": novo_livro.autor, "lancamento": novo_livro.lancamento}}

@app.put("/atualizar_livros/{id}")
def atualizar_livro(id: int, livro: Livro, db: Session = Depends(get_db), credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    livro_db = db.query(LivroDB).filter(LivroDB.id == id).first()
    if not livro_db:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    livro_db.titulo = livro.titulo
    livro_db.autor = livro.autor
    livro_db.lancamento = livro.lancamento
    db.commit()
    db.refresh(livro_db)
    return {"detail": "Livro atualizado com sucesso", "livro": {"id": livro_db.id, "titulo": livro_db.titulo, "autor": livro_db.autor, "lancamento": livro_db.lancamento}}

@app.delete("/deletar_livros/{id}")
def deletar_livro(id: int, db: Session = Depends(get_db), credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    livro_db = db.query(LivroDB).filter(LivroDB.id == id).first()
    if not livro_db:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    db.delete(livro_db)
    db.commit()
    return {"detail": "Livro deletado com sucesso"}