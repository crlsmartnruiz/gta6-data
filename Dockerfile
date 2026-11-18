FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . uvicorn

ENV GTA6_DB=/data/gta6.sqlite3
VOLUME /data
EXPOSE 8000

CMD ["uvicorn", "gta6data.api:app", "--host", "0.0.0.0", "--port", "8000"]
