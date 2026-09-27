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

# 名前付きボリュームは初回のマウントでこのディレクトリの所有者を引き継ぐ
RUN mkdir /data && chown nobody /data

USER nobody
EXPOSE 8000
ENV DJANGO_SETTINGS_MODULE=wp_main.settings
ENV DJANGO_DB_PATH=/data/db.sqlite3
# DB を書き換えるのはこのコンテナだけなので、django:migration もここで適用する
CMD ["sh", "-c", "python -m django migrate --noinput && exec gunicorn wp_main.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile -"]
