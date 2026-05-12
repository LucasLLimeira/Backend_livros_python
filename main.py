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

app = FastAPI(
    title="API de Livros",
    description="API para gerenciar uma coleção de livros",
    version="1.0.0",
    contact={
        "name": "Lucas Limeira",
        "email": "lucasdllimeira@gmail.com"
    }
)

MEU_USUARIO = "lucas"
MINHA_SENHA = "123456"

security = HTTPBasic()

meus_livros = {}

class Livro(BaseModel):
    titulo: str
    autor: str
    lancamento: int

def autenticar_usuario(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, MEU_USUARIO)
    correct_password = secrets.compare_digest(credentials.password, MINHA_SENHA)
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

@app.get("/livros")
def ler_livros(page: int = 1, limit: int = 10, credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    if page < 1 or limit < 1:
        raise HTTPException(status_code=400, detail="Page e limit devem ser maiores que 0")
    if not meus_livros:
        raise HTTPException(status_code=404, detail="Nenhum livro encontrado")
    start = (page - 1) * limit
    end = start + limit
    livros_paginados = [
        {"id": id, "titulo": livro_data["titulo"], "autor": livro_data["autor"], "lancamento": livro_data["lancamento"]}
        for id, livro_data in list(meus_livros.items())[start:end]
    ]
    return {
        "page": page,
        "limit": limit,
        "total_livros": len(meus_livros),
        "livros": livros_paginados
    }

@app.post("/adicionar_livros")
def criar_livro(id: int, livro: Livro, credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    if id in meus_livros:
        raise HTTPException(status_code=400, detail="Livro já existe")
    else:
        meus_livros[id] = livro.model_dump()
    return {"detail": "Livro adicionado com sucesso", "livro": meus_livros[id]}

@app.put("/atualizar_livros/{id}")
def atualizar_livro(id: int, livro: Livro, credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    if id not in meus_livros:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    else:
        meus_livros[id] = livro.model_dump()
    return {"detail": "Livro atualizado com sucesso", "livro": meus_livros[id]}

@app.delete("/deletar_livros/{id}")
def deletar_livro(id: int, credenciais: HTTPBasicCredentials = Depends(autenticar_usuario)):
    if id not in meus_livros:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    del meus_livros[id]
    return {"detail": "Livro deletado com sucesso"}