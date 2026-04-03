#!/usr/bin/env bash
# build.sh — runs on every Render deploy

set -o errexit   # exit on any error

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
