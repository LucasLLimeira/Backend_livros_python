from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_calcular_soma(mocker):
    mock_somar_delay = mocker.patch("tasks.somar.delay")
    mock_redis_setex = mocker.patch("main.redis_client.setex")
    mock_redis_lpush = mocker.patch("main.redis_client.lpush")
    mock_redis_ltrim = mocker.patch("main.redis_client.ltrim")

    mock_somar_delay.return_value.id = "test-task-id"
    mock_redis_setex.return_value = True

    response = client.post("/calcular/soma", params={"a": 3, "b": 4})
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "test-task-id",
        "tipo": "soma",
        "entrada": {"a": 3, "b": 4},
        "status": "Pendente",
        "message": "Tarefa de soma iniciada. Use a lista de tarefas para acompanhar o andamento."}
    mock_redis_setex.assert_called_once()
    mock_redis_lpush.assert_called_once()
    mock_redis_ltrim.assert_called_once()


def test_calcular_fatorial(mocker):
    mock_fatorial_delay = mocker.patch("tasks.fatorial.delay")
    mock_redis_setex = mocker.patch("main.redis_client.setex")
    mock_redis_lpush = mocker.patch("main.redis_client.lpush")
    mock_redis_ltrim = mocker.patch("main.redis_client.ltrim")

    mock_fatorial_delay.return_value.id = "test-task-id"
    mock_redis_setex.return_value = True

    response = client.post("/calcular/fatorial", params={"n": 5})
    assert response.status_code == 200
    assert response.json() == {
        "task_id": "test-task-id",
        "tipo": "fatorial",
        "entrada": {"n": 5},
        "status": "Pendente",
        "message": "Tarefa de fatorial iniciada. Use a lista de tarefas para acompanhar o andamento."}
    mock_redis_setex.assert_called_once()
    mock_redis_lpush.assert_called_once()
    mock_redis_ltrim.assert_called_once()