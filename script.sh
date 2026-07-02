#!/usr/bin/env bash

set -euo pipefail

DEPLOYMENT="deployment.yaml"
SERVICE="service.yaml"
APP_LABEL="app=livros-api"
SERVICE_NAME="livros-api-service"
NAMESPACE="${NAMESPACE:-default}"
LOCAL_PORT=8000
SERVICE_PORT=80
PF_PID=""
MINIKUBE_BIN=""
KUBECTL_BIN=""

resolve_command_path() {
    local cmd="$1"
    local found=""
    local username="${USERNAME:-}"

    found="$(command -v "$cmd" 2>/dev/null || true)"
    if [[ -n "$found" ]]; then
        echo "$found"
        return 0
    fi

    found="$(command -v "${cmd}.exe" 2>/dev/null || true)"
    if [[ -n "$found" ]]; then
        echo "$found"
        return 0
    fi

    if [[ "$OSTYPE" == msys* ]] || [[ "$OSTYPE" == cygwin* ]] || [[ "$OSTYPE" == win32* ]]; then
        local candidates=()

        if [[ "$cmd" == "minikube" ]]; then
            candidates=(
                "/c/Program Files/Kubernetes/Minikube/minikube.exe"
                "/c/ProgramData/chocolatey/bin/minikube.exe"
            )
        fi

        if [[ "$cmd" == "kubectl" ]]; then
            candidates=(
                "/c/ProgramData/chocolatey/bin/kubectl.exe"
                "/c/Program Files/Docker/Docker/resources/bin/kubectl.exe"
            )
        fi

        if [[ -n "$username" ]]; then
            candidates+=("/c/Users/$username/AppData/Local/Microsoft/WinGet/Links/${cmd}.exe")
        fi

        local candidate
        for candidate in "${candidates[@]}"; do
            if [[ -x "$candidate" ]]; then
                echo "$candidate"
                return 0
            fi
        done
    fi

    return 1
}

check_manifest_files() {
    if [[ ! -f "$DEPLOYMENT" ]]; then
        echo "Arquivo não encontrado: $DEPLOYMENT"
        return 1
    fi
    if [[ ! -f "$SERVICE" ]]; then
        echo "Arquivo não encontrado: $SERVICE"
        return 1
    fi
}

is_port_in_use() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -iTCP:"$LOCAL_PORT" -sTCP:LISTEN -t >/dev/null 2>&1
        return $?
    fi

    if command -v ss >/dev/null 2>&1; then
        ss -ltn | grep -q ":$LOCAL_PORT "
        return $?
    fi

    if command -v netstat >/dev/null 2>&1; then
        netstat -an 2>/dev/null | grep -E "[\.:]$LOCAL_PORT[[:space:]].*(LISTEN|LISTENING)" >/dev/null 2>&1
        return $?
    fi

    return 1
}

cleanup() {
    if [[ -n "$PF_PID" ]] && kill -0 "$PF_PID" >/dev/null 2>&1; then
        kill "$PF_PID" >/dev/null 2>&1 || true
        echo "Port-forward encerrado (PID $PF_PID)."
    fi
}

trap cleanup EXIT INT TERM

echo "Validando dependências..."
MINIKUBE_BIN="$(resolve_command_path minikube || true)"
if [[ -z "$MINIKUBE_BIN" ]]; then
    echo "Instale o Minikube e execute novamente."
    exit 1
fi

KUBECTL_BIN="$(resolve_command_path kubectl || true)"
if [[ -z "$KUBECTL_BIN" ]]; then
    echo "Instale o kubectl e execute novamente."
    exit 1
fi

if [[ "$OSTYPE" == linux* ]] && ! command -v xdg-open >/dev/null 2>&1; then
    echo "Aviso: xdg-open não encontrado. O navegador não será aberto automaticamente no Linux."
fi

check_manifest_files

echo "Verificando status do Minikube..."
if ! "$MINIKUBE_BIN" status --format='{{.Host}}' 2>/dev/null | grep -qi "Running"; then
    echo "Minikube não está rodando. Iniciando..."
    "$MINIKUBE_BIN" start
else
    echo "Minikube já está rodando."
fi

echo "Aplicando deployment..."
"$KUBECTL_BIN" apply -f "$DEPLOYMENT"
echo "Aplicando service..."
"$KUBECTL_BIN" apply -f "$SERVICE"

echo "Aguardando pods ficarem prontos..."
"$KUBECTL_BIN" wait --for=condition=ready pod -l "$APP_LABEL" -n "$NAMESPACE" --timeout=120s

if is_port_in_use; then
    echo "A porta local $LOCAL_PORT já está em uso. Libere a porta e execute novamente."
    exit 1
fi

echo "Iniciando port-forward para o serviço $SERVICE_NAME..."
"$KUBECTL_BIN" port-forward -n "$NAMESPACE" service/"$SERVICE_NAME" "$LOCAL_PORT:$SERVICE_PORT" >/dev/null 2>&1 &
PF_PID=$!

sleep 2
if ! kill -0 "$PF_PID" >/dev/null 2>&1; then
    echo "Falha ao iniciar o port-forward. Verifique logs do kubectl e do serviço."
    exit 1
fi

URL="http://localhost:$LOCAL_PORT"

if [[ "$OSTYPE" == linux* ]] && command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
elif [[ "$OSTYPE" == darwin* ]]; then
    open "$URL" >/dev/null 2>&1 || true
elif [[ "$OSTYPE" == cygwin* ]]; then
    cygstart "$URL" >/dev/null 2>&1 || true
elif [[ "$OSTYPE" == msys* ]] || [[ "$OSTYPE" == win32* ]]; then
    cmd.exe /c start "" "$URL" >/dev/null 2>&1 || true
else
    echo "Não foi possível abrir o navegador automaticamente. Acesse manualmente: $URL"
fi

echo "Aplicação disponível em $URL"
echo "Para encerrar o port-forward, pressione Ctrl+C."
echo "Para remover os recursos: kubectl delete -f $SERVICE && kubectl delete -f $DEPLOYMENT"
echo "Para parar o cluster local: minikube stop"

wait "$PF_PID"