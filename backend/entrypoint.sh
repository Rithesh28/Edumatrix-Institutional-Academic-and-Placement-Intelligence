#!/bin/bash
set -e

echo "🚀 Starting EduMatrix Backend Service..."

# Extract Postgres host and port from DATABASE_URL if available
if [ -n "$DATABASE_URL" ]; then
    # e.g. postgresql://user:pass@postgres:5432/dbname
    PG_HOST=$(echo "$DATABASE_URL" | sed -e 's/.*@//' -e 's/:.*//' -e 's/\/.*//')
    PG_PORT=$(echo "$DATABASE_URL" | sed -e 's/.*:[0-9]*@//' -e 's/.*://' -e 's/\/.*//')
    [ -z "$PG_PORT" ] && PG_PORT=5432
    
    echo "⏳ Waiting for PostgreSQL at $PG_HOST:$PG_PORT..."
    while ! nc -z "$PG_HOST" "$PG_PORT"; do
        sleep 1
    done
    echo "✅ PostgreSQL is available!"
fi

# Extract Redis host and port from REDIS_URL if available
if [ -n "$REDIS_URL" ]; then
    # e.g. redis://redis:6379/0
    REDIS_HOST=$(echo "$REDIS_URL" | sed -e 's/redis:\/\///' -e 's/:.*//' -e 's/\/.*//')
    REDIS_PORT=$(echo "$REDIS_URL" | sed -e 's/.*://' -e 's/\/.*//')
    [ -z "$REDIS_PORT" ] && REDIS_PORT=6379
    
    echo "⏳ Waiting for Redis at $REDIS_HOST:$REDIS_PORT..."
    while ! nc -z "$REDIS_HOST" "$REDIS_PORT"; do
        sleep 1
    done
    echo "✅ Redis is available!"
fi

echo "🎯 Executing application command: $@"
exec "$@"
