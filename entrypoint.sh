#!/bin/sh

set -e

echo "Starting Decors..."

echo "Waiting for MySQL..."

python - <<'PY'
import os
import time
import MySQLdb

host = os.getenv("DB_HOST", "db")
port = int(os.getenv("DB_PORT", "3306"))
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
database = os.getenv("DB_NAME")

while True:
    try:
        connection = MySQLdb.connect(
            host=host,
            port=port,
            user=user,
            passwd=password,
            db=database
        )

        connection.close()

        print("MySQL is ready!")
        break

    except Exception as error:
        print("Waiting for MySQL...")
        print(error)
        time.sleep(2)
PY

echo "Running makemigrations..."

python manage.py makemigrations --noinput

echo "Running migrations..."

python manage.py migrate --noinput

echo "Collecting static files..."

python manage.py collectstatic --noinput

echo "Starting Gunicorn..."

exec "$@"