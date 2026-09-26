## 1. 依存と設定

- [x] 1.1 `pyproject.toml` に optional dependency `dashboard`（fastapi・uvicorn・jinja2）を追加し、dev グループに `wp-main[dashboard]` と `httpx2`（Starlette の TestClient が推奨する HTTP クライアント）を加える。`uv sync` が成功し、`uv run cli help` が従来どおり動くことを確認する
- [x] 1.2 `src/wp_main/config.py` に `DASHBOARD_DOMAIN` と `DASHBOARD_IMAGE = "wp-main-dashboard"` を追加し、`.env.example` に `DASHBOARD_DOMAIN` を追加する。`uv run pytest tests/test_config.py` が通ることを確認する

## 2. ダッシュボードのアプリケーション

- [x] 2.1 `src/wp_main/dashboard/` に、`SITES` と `parse_env` を使って `DASHBOARD_SITES_DIR`（既定 `/sites`）配下の `<id>/.env` からサイトごとの表示データ（URL・ログイン URL・バージョン・ポート・ユーザー名・不足項目）を作る関数を実装する。`tests/test_dashboard.py` で、通常・`.env` なし・`WP_ADMIN_PASSWORD` なし・`latest` タグのケースが通ることを確認する
- [x] 2.2 FastAPI アプリに `GET /`（Jinja2 の一覧 HTML）、`GET /api/sites/{id}/password`（`Cache-Control: no-store`、該当なしは 404）、`GET /healthz` を実装する。TestClient で、一覧が 200 でパスワードの値を含まないこと、`.env` を書き換えると次のリクエストで API の値が変わること、未知の ID が 404 になることを確認する
- [x] 2.3 案 B（`Compact.dc.html`）に沿ってテンプレートと CSS を作り、表示切替・コピー・コピー済み表示の JavaScript を実装する。パスワード未設定の行ではボタンを無効にする。`uv run uvicorn` をローカルで起動し、ブラウザで表示・切替・コピーが動くことを確認する

## 3. コンテナとプロキシ

- [x] 3.1 `dashboard.Dockerfile` と `.dockerignore` を追加する。`docker build -f dashboard.Dockerfile -t wp-main-dashboard .` が成功し、イメージに `.env` や `.git` が含まれないことを確認する
- [x] 3.2 `docker-compose.yml` に `dashboard` サービス（固定イメージ名、両サイトディレクトリの `:ro` マウント、`wp-global-net`、`/healthz` の healthcheck、ポート公開なし）を追加し、Caddy の環境変数に `DASHBOARD_DOMAIN`（既定値付き）を加える。`docker compose config` が成功することを確認する
- [x] 3.3 Caddy の `ports` を `${PROXY_BIND_ADDRESS:-127.0.0.1}` 付きに変え、`.env.example` に `# PROXY_BIND_ADDRESS=0.0.0.0` を説明付きで追加する。既定、`.env` で指定、`PROXY_BIND_ADDRESS=0.0.0.0 docker compose config` の 3 通りで、`docker compose config` のポートのアドレスが期待どおりになることを確認する
- [x] 3.4 `Caddyfile` に `{$DASHBOARD_DOMAIN}` のブロックを追加し、`tls internal` で `dashboard` へ転送する。`docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile` が成功することを確認する

## 4. CLI

- [x] 4.1 `dev-env:install` の hosts ブロックに `DASHBOARD_DOMAIN` を加える。`tests/test_hosts.py` に、wp1/wp2 だけの既存ブロックが 3 ドメインのブロック 1 つに置き換わるテストを追加して通す
- [x] 4.2 `dev-env:uninstall` の削除対象イメージに `DASHBOARD_IMAGE` を加える。`tests/test_uninstall.py` で `docker image rm wp-main-dashboard` が呼ばれることを確認する

## 5. ドキュメントと統合確認

- [x] 5.1 `README.md` にダッシュボードの URL、既存環境での反映手順（`dev-env:install` の再実行）、`PROXY_BIND_ADDRESS` による公開範囲の切り替え方法と、`0.0.0.0` にしたときに LAN からパスワードが見える点の注意を追記する
- [ ] 5.2 実環境で `uv run cli dev-env:install` を実行し、`https://local.wp-main.yamashita109.com/` が証明書エラーなしで開くこと、両サイトの行とリンクが正しいこと、`docker compose ps` に 6 コンテナが表示されること、`lsof -nP -iTCP:443 -sTCP:LISTEN` で `127.0.0.1` にだけ待ち受けていることを確認する
- [ ] 5.3 実環境で `../wp-wp1/.env` の `WP_ADMIN_PASSWORD` を一時的に書き換え、コンテナを再起動せずにダッシュボードの表示が変わること、コンテナ内から `/sites/wp1/.env` に書き込めないことを確認し、値を元に戻す
