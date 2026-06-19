from celery_app import celery_app


@celery_app.task(name="tasks.somar", bind=True)
def somar(self, a, b):  # Simula uma tarefa demorada
    
    return a + b

@celery_app.task(name="tasks.fatorial", bind=True)
def fatorial(self, n):  # Simula uma tarefa demorada
    if n < 0:
        raise ValueError("Fatorial não é definido para números negativos")
    elif n == 0 or n == 1:
        return 1
    else:
        resultado = 1
        for i in range(2, n + 1):
            resultado *= i
        return resultado