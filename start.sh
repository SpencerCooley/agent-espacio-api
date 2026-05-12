#!/bin/bash

# Wait for PostgreSQL to become available
echo "Waiting for PostgreSQL..."
until pg_isready -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER}; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL is up - starting application"

# Start the FastAPI application
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2 --timeout-keep-alive 4000 --reload
