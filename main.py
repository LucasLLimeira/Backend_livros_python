# API de Livros

#GET, POST, PUT, DELETE

#Get - Ler dados
#Post - Criar dados
#Put - Atualizar dados
#Delete - Deletar dados

from fastapi import FastAPI, HTTPException

app = FastAPI()

meus_livros = {}

@app.get("/livros")
def ler_livros():
    if not meus_livros:
        raise HTTPException(status_code=404, detail="Nenhum livro encontrado")
    return meus_livros

@app.post("/adicionar_livros")
def criar_livro(id: int, titulo: str, autor: str, lancamento: int):
    if id in meus_livros:
        raise HTTPException(status_code=400, detail="Livro já existe")
    else:
        meus_livros[id] = {"titulo": titulo, "autor": autor, "lancamento": lancamento}
    return {"detail": "Livro adicionado com sucesso", "livro": meus_livros[id]}

@app.put("/atualizar_livros/{id}")
def atualizar_livro(id: int, titulo: str = None, autor: str = None, lancamento: int = None):
    if id not in meus_livros:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    else:
        if titulo:
            meus_livros[id]["titulo"] = titulo
        if autor:
            meus_livros[id]["autor"] = autor
        if lancamento:
            meus_livros[id]["lancamento"] = lancamento
    return {"detail": "Livro atualizado com sucesso", "livro": meus_livros[id]}

@app.delete("/deletar_livros/{id}")
def deletar_livro(id: int):
    if id not in meus_livros:
        raise HTTPException(status_code=404, detail="Livro não encontrado")
    del meus_livros[id]
    return {"detail": "Livro deletado com sucesso"}