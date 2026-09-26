# wp-main ダッシュボード: docker compose が wp-main のルートをビルドコンテキストにしてビルドする
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# 依存だけを先に入れ、ソース変更時の再ビルドでレイヤーキャッシュを効かせる
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra dashboard --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --extra dashboard --no-editable

USER nobody
EXPOSE 8000
CMD ["uvicorn", "wp_main.dashboard.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
