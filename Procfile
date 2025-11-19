web: gunicorn --config gunicorn_conf.py docia.wsgi
worker: celery --app docia worker -l INFO -Q celery -n celery@%h --concurrency=2
workerheavycpu: celery --app docia worker -l INFO -Q heavy_cpu -n heavy_cpu@%h --concurrency=1
postdeploy: python manage.py migrate
