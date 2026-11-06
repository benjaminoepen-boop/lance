#!/bin/zsh
# Starts Lance on this Mac: http://127.0.0.1:8770
cd "$(dirname "$0")"
exec uv run --no-dev gunicorn app:app --bind 127.0.0.1:8770 --workers 1 --access-logfile -
