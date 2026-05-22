# Backend Livros Python

API REST para gerenciamento de livros com FastAPI, SQLAlchemy, SQLite e Redis.

## Stack
- Python 3.14+
- FastAPI
- SQLAlchemy
- SQLite
- Redis
- Poetry
- Podman + podman-compose

## Funcionalidades
- CRUD de livros
- Paginação na listagem com cache Redis
- Debug de cache e TTL no endpoint /debug/redis
- Autenticação HTTP Basic

## Variáveis de ambiente
Crie um arquivo .env na raiz do projeto com:

DATABASE_URL=sqlite:///./livros.db
MEU_USUARIO=admin
MINHA_SENHA=senha_forte
REDIS_HOST=redis
REDIS_PORT=6379
CACHE_TTL_SECONDS=30

Para executar fora do Compose (Poetry local), ajuste REDIS_HOST para localhost.

## Executar localmente com Poetry
1. Instale dependências:
   poetry install
2. Suba a API:
   poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
3. Acesse:
   http://localhost:8000
4. Documentação:
   http://localhost:8000/docs

## Executar com Podman Compose
1. Build da imagem:
   podman-compose build
2. Subir containers:
   podman-compose up -d
3. Validar configuração:
   podman-compose config
4. Logs:
   podman-compose logs -f
5. Derrubar ambiente:
   podman-compose down

## Endpoints principais
- GET /
- GET /debug/redis
- GET /livros?page=1&limit=10
- POST /adicionar_livros
- PUT /atualizar_livros/{id}
- DELETE /deletar_livros/{id}

Todos os endpoints de livros exigem autenticação Basic Auth.

## Exemplo de payload
POST /adicionar_livros

{
  "titulo": "Clean Code",
  "autor": "Robert C. Martin",
  "lancamento": 2008
}

## Estrutura atual
- main.py: aplicação FastAPI e rotas
- pyproject.toml: dependências e metadados do projeto
- Dockerfile: imagem da aplicação
- docker-compose.yml: serviço app para execução com Podman

## Observações
- O banco SQLite é criado automaticamente no arquivo livros.db.
- O cache Redis é configurado por CACHE_TTL_SECONDS e expira automaticamente as chaves de cache.
- O endpoint /debug/redis retorna redis_status, ttl_padrao_segundos e os itens com ttl_segundos_restantes.
- Estratégia fail-soft: se o Redis estiver indisponível, o dado continua sendo salvo no banco e a API retorna aviso de cache quando aplicável.
- Em produção, use um banco gerenciado e segredos fora do arquivo .env.
