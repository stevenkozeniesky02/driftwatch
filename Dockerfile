FROM python:3.12-slim AS base

WORKDIR /app

RUN groupadd -r driftwatch && useradd -r -g driftwatch driftwatch

COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM base AS runtime

COPY src/ src/

RUN pip install --no-cache-dir -e .

USER driftwatch

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/snapshots')" || exit 1

ENTRYPOINT ["driftwatch"]
CMD ["serve", "--host", "0.0.0.0"]
