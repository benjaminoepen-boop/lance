FROM python:3.12-slim
# uv at one exact version, so a new release cannot change the build; the packages themselves are fixed in uv.lock
RUN pip install --no-cache-dir uv==0.12.23
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app.py db.py logic.py ./
COPY templates ./templates
COPY static ./static
COPY seed ./seed
# The app runs as its own user: it can read its code but write only /data, where the database lives
RUN useradd --system --no-create-home lance && mkdir -p /data && chown lance /data
USER lance
ENV LANCE_DB=/data/lance.db
EXPOSE 8000
# Threaded workers: a slow upload or a connection a browser keeps open for later (Safari does) holds one thread, not a whole worker
CMD ["/app/.venv/bin/gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "gthread", "--threads", "4", "--preload"]
