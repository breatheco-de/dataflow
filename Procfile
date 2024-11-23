release: python manage.py migrate && python manage.py
celeryworker: export CELERY_WORKER_RUNNING=True; celery -A breathecode.celery worker --loglevel=DEBUG --concurrency 1 --max-tasks-per-child=1
# channelsworker: python manage.py runworker channel_layer -v2
web: daphne breathecode.asgi:application --port $PORT --bind 0.0.0.0 -v2
