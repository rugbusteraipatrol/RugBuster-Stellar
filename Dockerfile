# Zero runtime dependencies (see pyproject.toml): run the stdlib HTTP server
# straight from source. No pip install of the local package, so there is no
# Nixpacks-style staged-copy ordering issue to fight.
FROM python:3.12-slim

WORKDIR /app
COPY . /app

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0

EXPOSE 8787

CMD ["python3", "-m", "rugbuster_stellar.web"]
