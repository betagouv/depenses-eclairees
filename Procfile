web: gunicorn --config gunicorn_conf.py docia.wsgi
worker: celery --app docia worker -l INFO --concurrency=2
