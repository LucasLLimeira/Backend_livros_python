# Backend Livros Python

API REST para gerenciamento de livros com FastAPI, SQLAlchemy, SQLite, Redis e publicação de eventos em Kafka.

## Stack
- Python 3.14+
- FastAPI
- SQLAlchemy
- SQLite
- Redis
- Celery
- Apache Kafka
- Zookeeper
- Kafka UI
- Poetry
- Podman + podman-compose

## Funcionalidades
- CRUD de livros
- Paginação na listagem com cache Redis
- Debug de cache e TTL no endpoint /debug/redis
- Execução assíncrona de soma e fatorial com lista de tarefas recentes em /calcular/tarefas
- Registro único de tarefa por requisição de soma/fatorial (sem duplicidade no histórico)
- Autenticação HTTP Basic
- Publicação de eventos Kafka no tópico `livros_eventos` ao criar livros

## Variáveis de ambiente
Crie um arquivo .env na raiz do projeto com:

DATABASE_URL=sqlite:///./livros.db
MEU_USUARIO=admin
MINHA_SENHA=senha_forte
REDIS_HOST=redis
REDIS_PORT=6379
CACHE_TTL_SECONDS=30
KAFKA_SERVER=kafka:9092

Para executar fora do Compose (Poetry local), ajuste REDIS_HOST para localhost.

## Deploy local com Minikube (script.sh)

### Dependências obrigatórias
- bash (Git Bash ou WSL no Windows)
- Docker Desktop (com engine Linux)
- minikube
- kubectl

### Essencial para testes futuros (Windows + Hyper-V)
1. Se o driver configurado for Hyper-V, execute o terminal como Administrador antes de rodar `minikube start`.
2. Garanta que o contexto ativo seja o do Minikube:
   `kubectl config use-context minikube`
3. Este projeto usa `imagePullPolicy: Never` no deployment, então a imagem precisa existir dentro do Minikube em cada ambiente novo:
   `minikube image build -t livros-api:latest .`
4. Valide status antes do deploy:
   `minikube status` e `kubectl get nodes`
5. Se o deploy travar em pods não prontos, diagnostique com:
   `kubectl describe pod -l app=livros-api` e `kubectl logs -l app=livros-api --tail=100`

### Instalação de dependências ausentes (Windows)

PowerShell (winget):

```powershell
winget install -e --id Docker.DockerDesktop
winget install -e --id Kubernetes.minikube
winget install -e --id Kubernetes.kubectl
```

PowerShell (Chocolatey):

```powershell
choco install docker-desktop minikube kubernetes-cli -y
```

Se for usar Git Bash, execute o script dentro do Git Bash na raiz do projeto.

### Instalação rápida (Linux Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y docker.io kubectl curl
curl -LO https://github.com/kubernetes/minikube/releases/download/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```

### Comandos para iniciar

Na raiz do projeto:

PowerShell (Windows):

```powershell
bash ./script.sh
```

Git Bash:

```bash
./script.sh
```

O script valida dependências, inicia o minikube (se necessário), aplica [deployment.yaml](deployment.yaml) e [service.yaml](service.yaml), cria port-forward e abre http://localhost:8000.

Para garantir que os pods iniciem em ambiente novo, rode antes do script:

```powershell
minikube image build -t livros-api:latest .
```

### Comandos para parar

1. Parar o port-forward em execução:
- pressione Ctrl+C no terminal onde o script está rodando.

2. Remover os recursos aplicados:

```bash
kubectl delete -f service.yaml
kubectl delete -f deployment.yaml
```

3. Parar o Minikube:

```bash
minikube stop
```

4. (Opcional) Limpar cluster local para teste do zero:

```bash
minikube delete
```

### Troubleshooting rápido
- Erro de kubectl context: `kubectl config use-context minikube`
- Porta 8000 ocupada: finalize o processo da porta e rode o script novamente
- Minikube não sobe: valide se Docker Desktop está em execução
- Hyper-V sem permissão: abra o PowerShell como Administrador
- Pods em timeout no `kubectl wait`: rode `minikube image build -t livros-api:latest .` e faça `kubectl rollout restart deployment/livros-api`

## Passo a passo para iniciar o projeto
Use este fluxo toda vez que for subir o ambiente:

1. Abra o terminal na raiz do projeto.
2. Se houver containers antigos do projeto rodando, limpe antes de subir:
   podman-compose down
3. Valide a configuração do Compose:
   podman-compose config
4. Suba os containers:
   podman-compose up -d
5. Verifique se os containers ficaram ativos:
   podman ps
6. Confira a API no navegador ou via terminal:
   http://localhost:8000
7. (Opcional) Acesse a interface do Kafka UI:
   http://localhost:8080

Se quiser acompanhar os logs:

podman-compose logs -f

Para derrubar o ambiente:

podman-compose down

## Executar localmente com Poetry
1. Instale dependências:
   poetry install
2. Em um terminal, suba a API:
   poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
3. Em outro terminal, suba o worker do Celery:
   poetry run celery -A celery_app:celery_app worker -Q livros --loglevel=info
4. Acesse:
   http://localhost:8000
5. Documentação:
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

## Serviços no Compose
- `app`: FastAPI (porta 8000)
- `celery`: worker Celery para fila `livros`
- `redis`: broker/backend do Celery e cache da API (porta 6379)
- `zookeeper`: coordenação do Kafka (porta 2181)
- `kafka`: broker Kafka (porta 9092)
- `kafka-ui`: painel web para visualizar tópicos e mensagens (porta 8080)

## Kafka no projeto
- Broker padrão: `kafka:9092` (via variável `KAFKA_SERVER`)
- Tópico usado pela API: `livros_eventos`
- Evento publicado atualmente: criação de livro no endpoint `POST /adicionar_livros`

## Endpoints principais
- GET /
- GET /debug/redis
- GET /calcular/tarefas?page=1
- GET /calcular/tarefas/{task_id}
- POST /calcular/soma?a=5&b=2
- POST /calcular/fatorial?n=5
- GET /livros?page=1&limit=10
- POST /adicionar_livros
- PUT /atualizar_livros/{id}
- DELETE /deletar_livros/{id}

Todos os endpoints de livros exigem autenticação Basic Auth.

## Como consultar as tarefas
1. Envie a requisição de soma ou fatorial.
2. A resposta já retorna `task_id`, `tipo`, `entrada` e `status`.
3. Para ver as tarefas registradas, consulte:
   `GET /calcular/tarefas?page=1`
4. Para navegar entre as páginas, aumente o valor de `page`.
5. Cada página sempre traz até 10 itens.
6. Para ver uma tarefa específica, use:
   `GET /calcular/tarefas/{task_id}`

## Exemplo de payload
POST /adicionar_livros

{
  "titulo": "Clean Code",
  "autor": "Robert C. Martin",
  "lancamento": 2008
}

## Estrutura atual
- main.py: aplicação FastAPI e rotas
- tasks.py: tarefas assíncronas do Celery (soma e fatorial)
- celery_app.py: configuração da aplicação Celery
- kafka_producer.py: produtor Kafka para envio de eventos
- pyproject.toml: dependências e metadados do projeto
- Dockerfile: imagem da aplicação
- docker-compose.yml: serviços app, celery, redis, zookeeper, kafka e kafka-ui

## Observações
- O banco SQLite é criado automaticamente no arquivo livros.db.
- O cache Redis é configurado por CACHE_TTL_SECONDS e expira automaticamente as chaves de cache.
- O endpoint /debug/redis retorna redis_status, ttl_padrao_segundos e os itens com ttl_segundos_restantes.
- Estratégia fail-soft: se o Redis estiver indisponível, o dado continua sendo salvo no banco e a API retorna aviso de cache quando aplicável.
- Em produção, use um banco gerenciado e segredos fora do arquivo .env.
