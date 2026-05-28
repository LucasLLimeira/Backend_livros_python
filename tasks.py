from celery_app import celery_app
import time

@celery_app.task(bind=True)
def somar(self, a, b):
    time.sleep(5)  # Simula uma tarefa demorada
    return a + b

@celery_app.task(bind=True)
def fatorial(self, n):
    time.sleep(5)  # Simula uma tarefa demorada
    if n < 0:
        raise ValueError("Fatorial não é definido para números negativos")
    elif n == 0 or n == 1:
        return 1
    else:
        resultado = 1
        for i in range(2, n + 1):
            resultado *= i
        return resultado