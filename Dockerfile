FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app.py db.py logic.py ./
COPY templates ./templates
COPY static ./static
COPY seed ./seed
ENV LANCE_DB=/data/lance.db
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2"]
