FROM python:3.12-slim

ARG APT_MIRROR=""
ARG APT_SECURITY_MIRROR=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEPLOYMENT_PACKAGE_TEMPLATE_DIR=/app/templates

WORKDIR /app

RUN if [ -n "${APT_SECURITY_MIRROR}" ]; then sed -i "s|http://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; fi \
    && if [ -n "${APT_MIRROR}" ]; then sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; fi \
    && printf '%s\n' 'Acquire::Retries "3";' 'Acquire::http::Timeout "30";' 'Acquire::https::Timeout "30";' >/etc/apt/apt.conf.d/99build-timeouts \
    && apt-get update \
    && apt-get install -y --no-install-recommends skopeo ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/deployment_package_factory /app/deployment_package_factory
COPY templates /app/templates

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/data \
    && chown -R app:app /app

USER 10001

EXPOSE 8096

CMD ["uvicorn", "deployment_package_factory.main:app", "--host", "0.0.0.0", "--port", "8096"]
