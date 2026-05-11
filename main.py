# API de Livros

#GET, POST, PUT, DELETE

#Get - Ler dados
#Post - Criar dados
#Put - Atualizar dados
#Delete - Deletar dados

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="API de Livros",
    description="API para gerenciar uma coleção de livros",
    version="1.0.0",
    contact={
        "name": "Lucas Limeira",
        "email": "lucasdllimeira@gmail.com"
    }
)

meus_livros = {}

class Livro(BaseModel):
    titulo: str
    autor: str
    lancamento: int

@app.get("/livros")
def ler_livros():
    if not meus_livros:
        raise HTTPException(status_code=404, detail="Nenhum livro encontrado")
    return meus_livros

@app.post("/adicionar_livros")
def criar_livro(id: int, livro: Livro):
    if id in meus_livros:
        raise HTTPException(status_code=400, detail="Livro já existe")
    else:
        meus_livros[id] = livro.model_dump()
    return {"detail": "Livro adicionado com sucesso", "livro": meus_livros[id]}

@app.put("/atualizar_livros/{id}")
def atualizar_livro(id: int, livro: Livro):
    if id not in meus_livros:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    else:
        meus_livros[id] = livro.model_dump()
    return {"detail": "Livro atualizado com sucesso", "livro": meus_livros[id]}

@app.delete("/deletar_livros/{id}")
def deletar_livro(id: int):
    if id not in meus_livros:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    del meus_livros[id]
    return {"detail": "Livro deletado com sucesso"}