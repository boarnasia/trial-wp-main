## 1. 設定と依存

- [x] 1.1 `pyproject.toml` の `gunicorn`・`whitenoise` を extras から通常の依存に移し、`uv sync` と `uv run python -c "import gunicorn, whitenoise"` が通ることを確かめる
- [x] 1.2 `settings.py` に `django.contrib.messages`、`CsrfViewMiddleware`、`MessageMiddleware`、messages の context processor、`MESSAGE_STORAGE`（CookieStorage）、`CSRF_TRUSTED_ORIGINS`、`CSRF_COOKIE_SECURE` を加え、`DJANGO_DB_PATH` の説明コメントをホスト前提に直す。`uv run manage.py check` が通ることを確かめる
- [x] 1.3 `config.py` に `DASHBOARD_PORT` の既定値（8000）と wp-main の `.env` から読む関数、ロックのディレクトリ（`.local/locks`）を加え、`tests/test_config.py` に既定値と `.env` での上書きのテストを加える

## 2. 操作履歴の直接書き込み

- [x] 2.1 `operations.record()` を、django:migration の適用と `Operation` の作成・`prune()` に置き換え、`call_api`・`ca_file`・`send`・`ApiError`・`API_URL`・`TOKEN_KEY` を削除する。`tests/test_operations.py` を、DB への記録、DB がない場合の作成、書き込めない場合の警告のテストに書き換えて通す
- [x] 2.2 `tests/conftest.py` の `operations.send` を差し替える autouse fixture を `operations.write` の差し替えに改め、テストが実際の `.local/db.sqlite3` に書かないようにする（DB への書き込みそのものは `tests/test_operations.py` で確かめる）。`tests/test_cli_recording.py` を通す
- [x] 2.3 `dashboard/views.py` から `/api/operations` の 2 つの API と `TokenAuth`・`OperationIn`・`OperationOut` を削除し、`tests/test_operation_api.py` を削除する。`uv run pytest` が通ることを確かめる

## 3. ホストのプロセスと devenv serve

- [x] 3.1 `src/wp_main/processes.py` に `HostProcess` とプロセスの一覧（dashboard: `python -m gunicorn ... --bind 127.0.0.1:{port} --workers 2 --timeout 150 --access-logfile -`）を作り、一覧の内容をテストで確かめる
- [x] 3.2 スーパーバイザー（起動、名前付きの出力、SIGINT / SIGTERM での停止、1 つが落ちたら全停止）を実装し、ダミーのプロセス（`python -c ...`）を使ったテストで、正常な停止が終了コード 0、異常終了が 0 以外とプロセス名の表示になることを確かめる
- [x] 3.3 `devenv serve`（`--root` 付き）を追加する。ポートの使用中の検査、django:migration の事前適用、`WP_MAIN_ROOT` の受け渡しを行い、ポートが使用中の場合に何も起動しないことをテストで確かめる。`uv run manage.py help devenv` に `serve` が出ることを確かめる
- [x] 3.4 `devenv serve` を実際に動かし、`curl http://127.0.0.1:8000/healthz` が 200 を返し、LAN 側のアドレスでは接続できず、Ctrl-C で終了コード 0 で終わることを確かめる

## 4. ダッシュボードのホスト対応

- [x] 4.1 `dashboard/data.py` の読み込み元を `{root}/wp-wpN/.env`（`WP_MAIN_ROOT`、なければ `resolve_root(None)`）に変え、`DASHBOARD_SITES_DIR` を削除する。`tests/test_dashboard.py` を新しい読み込み元で通す
- [x] 4.2 `docker-compose.yml` から `dashboard` サービスとボリューム `dashboard_data` を削除し、caddy に `DASHBOARD_PORT` と `extra_hosts: host.docker.internal:host-gateway` を加える。`Caddyfile` のダッシュボードの転送先を `host.docker.internal:{$DASHBOARD_PORT}` にする。`docker compose config` が通ることを確かめる
- [x] 4.3 `dashboard.Dockerfile` を削除し、`config.py` の `DASHBOARD_IMAGE`・`DASHBOARD_VOLUME` は旧環境の後片付け用として残す（コメントで理由を書く）。`.env.example` から `DASHBOARD_API_TOKEN` を外し、`DASHBOARD_PORT` をコメント付きで加える

## 5. サイトの起動・停止

- [x] 5.1 サイトの状態の取得（`docker inspect` の解析、起動中・停止中・一部停止・取得不可、操作するプロジェクトの判定）を実装し、inspect の出力の例を使ったテストで、各状態と単体起動時の `cwd` の判定を確かめる
- [x] 5.2 起動（`up -d --wait --wait-timeout 120 <site>-wordpress`）と停止（`stop <site>-wordpress <site>-db`）を、ファイルロック付きで実装する。Runner を差し替えたテストで、実行されるコマンドと `cwd`、ロック中は実行しないことを確かめる
- [x] 5.3 `POST /sites/<id>/start`・`POST /sites/<id>/stop` のビューを加える（`require_POST`、CSRF、`PROXY_BIND_ADDRESS` の検査、結果を messages と操作履歴（`site-start`・`site-stop`）に残して `/` へリダイレクト）。テストで、CSRF トークンなしは 403、GET は 405、LAN 公開時は 403、成功時に履歴が 1 件増えることを確かめる
- [x] 5.4 `index.html` と `dashboard.css` に、状態の表示、起動・停止のフォーム（`{% csrf_token %}`）、無効時の理由、messages の表示、送信中にボタンを無効にする小さなスクリプトを加える。テストで、状態ごとのボタンの出し分けと、Docker に接続できないときに 200 が返ることを確かめる

## 6. check-health

- [x] 6.1 `health.py` から `container.wp-dashboard` と `http.api.dashboard` を削除し、`host.dashboard`（`127.0.0.1:{DASHBOARD_PORT}/healthz`、応答しなければ WARN と `devenv serve` の案内）を加え、`http.https.dashboard` の前提にする。`tests/test_health.py` を、ダッシュボードが停止している場合の WARN と SKIP、項目数 27 で通す

## 7. install / uninstall と dev-env:migration 5

- [x] 7.1 `devenv install` に django:migration の適用と、最後の `devenv serve` の案内を加える。`compose up` の `--build` を外す。`tests/test_install.py` で確かめる
- [x] 7.2 `devenv uninstall` の削除対象に `.local/db.sqlite3`（WAL のファイルを含む）と `.local/locks` を加え、旧ダッシュボードのコンテナ `wp-dashboard` も削除する。`devenv serve` が応答している場合は止めるよう表示する。`tests/test_uninstall.py` で確かめる
- [x] 7.3 `devenv/migrations/m0005_host_dashboard.py` を作る（旧コンテナの削除、DB の写しと integrity_check、ボリュームとイメージの削除、起動中ならプロキシの作り直し、`devenv serve` の案内）。`tests/test_m0005_host_dashboard.py` で、DB を写す場合、既に `.local/db.sqlite3` がある場合、写しに失敗した場合（ボリュームを消さない）、再実行、プロキシが停止中の場合を確かめる。`versioning.latest()` が 5 になることを確かめる

## 8. ドキュメントと全体の確認

- [x] 8.1 README を更新する（`devenv serve`、ダッシュボードがホストで動くこと、`DASHBOARD_PORT`、サイトの起動・停止、LAN 公開時の制限、操作履歴の保存先、API の廃止）。調査メモの冒頭に、Docker Desktop に移行したことと、この変更で採った方式を追記する
- [x] 8.2 `uv run pytest` がすべて通ることを確かめる
- [x] 8.3 実環境で確かめる: `uv run manage.py devenv migrate` で環境バージョン 5 になり、`wp-dashboard` のコンテナ・イメージ・ボリュームがなくなること。`devenv serve` を動かして `https://local.wp-main.yamashita109.com/` が表示されること。ダッシュボードから wp1 を停止・起動でき、wp2 と Caddy が影響を受けず、履歴に `site-stop`・`site-start` が残ること。`devenv check-health` が全項目 OK になり、`devenv serve` を止めると `host.dashboard` が WARN になること
