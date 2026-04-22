web: gunicorn --config gunicorn_conf.py docia.wsgi
worker: celery --app docia worker -l INFO -Q celery -n celery@%h --concurrency=2
workerocr: celery --app docia worker -l INFO -Q ocr -n ocr@%h --concurrency=1
postdeploy: if [ "$DISABLE_MIGRATE" != "1" ]; then python manage.py migrate; fi
