FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/deployment_package_factory /app/deployment_package_factory
COPY templates /app/templates

RUN pip install --no-cache-dir .

EXPOSE 8096

CMD ["uvicorn", "deployment_package_factory.main:app", "--host", "0.0.0.0", "--port", "8096"]
