from celery import Celery

celery_app = Celery('tarefas_livros', 
                    broker='redis://localhost:6379/0',
                    backend='redis://localhost:6379/0')

celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    result_persistent=True,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
)