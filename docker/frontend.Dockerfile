# The demo page. It only calls the API, so it holds no model. Build from the repo root.
FROM python:3.12-slim-bookworm AS build
RUN pip install --no-cache-dir uv==0.9.28
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable --extra frontend

FROM python:3.12-slim-bookworm
RUN useradd --create-home --uid 1000 fruity
WORKDIR /app
COPY --from=build /app/.venv ./.venv
USER fruity
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2)"
CMD ["streamlit", "run", ".venv/lib/python3.12/site-packages/fruity/lib/frontend/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
