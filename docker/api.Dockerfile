# The API: ONNX Runtime and the published model, with no PyTorch. Build from the repo root.
FROM python:3.12-slim-bookworm AS build
RUN pip install --no-cache-dir uv==0.9.28
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --extra serving
# Fails the build if a downloaded file differs from the checksum of the measured model.
RUN .venv/bin/fruity fetch

FROM python:3.12-slim-bookworm
RUN useradd --create-home --uid 1000 fruity
WORKDIR /app
COPY --from=build /app/.venv ./.venv
COPY --from=build /app/models ./models
USER fruity
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "fruity.lib.serving.api:app", "--host", "0.0.0.0", "--port", "8000"]
