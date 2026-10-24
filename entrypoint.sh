#!/bin/sh
set -e

echo "Running migrations..."
python manage.py migrate


echo "Starting .. .."
python manage.py server web-with-command-workers
