## 1. モデルと DB

- [x] 1.1 `wp_main.dashboard` に `Operation` モデルを加え、`uv run manage.py makemigrations dashboard` で django:migration `0001` を作る。settings の SQLite に WAL と `timeout` を設定する。`uv run pytest` の DB を使うテストで、モデルを保存して読み出せることを確認する
- [x] 1.2 `docker-compose.yml` にボリューム `wp-dashboard-data`（`/data`）、`DJANGO_DB_PATH=/data/db.sqlite3`、`DASHBOARD_API_TOKEN: ${DASHBOARD_API_TOKEN:-}` を加える。`dashboard.Dockerfile` で `/data` を `nobody` の所有で作り、起動時に `manage.py migrate --noinput` を実行してから gunicorn を起動する。`docker compose up -d --build --wait dashboard` で healthy になり、`docker exec wp-dashboard ls /data` に `db.sqlite3` があることを確認する

## 2. API と表示

- [x] 2.1 `POST /api/operations` と `GET /api/operations` を Django Ninja で実装する（`HttpBearer`、`hmac.compare_digest`、トークン未設定なら拒否、`command` の値の検証、`summary` の切り詰め、1000 件を超えた分の削除）。401（トークンなし・不一致・未設定）、201、`limit` の範囲、上限を超えたときの削除のテストを加えて通す
- [x] 2.2 トップページのサイト一覧の下に、直近 20 件の操作履歴の表を加える（新しい順、失敗の区別、履歴なしの表示）。表示の順序、失敗の表示、履歴がないときのテストを加えて通す。パスワード取得 API がトークンなしで従来どおり動くことを既存のテストで確認する

## 3. CLI からの記録

- [x] 3.1 `src/wp_main/operations.py` に `record` を実装する（`.env` のトークン、`cafile=CA_CERT_FILE`、証明書がなければ書き出し、3 秒のタイムアウト、失敗時は標準エラー出力への警告だけ）。送信の成功、ダッシュボード停止時の警告、トークンがないときの警告のテストを加えて通す
- [x] 3.2 `devenv install`・`migrate`・`check-health` から `record` を呼ぶ（design の decision 4 の記録条件と要約）。dry-run と何もしなかった migrate を記録しないこと、`--auto` の失敗を失敗として記録すること、記録に失敗しても出力と終了コードが変わらないこと、`check-health --json` の標準出力が JSON のままであることのテストを加えて通す

## 4. 移行、確認、後片付け

- [x] 4.1 `devenv/migrations/` の `.env` 追記処理を共通関数に切り出し、`discover()` が `_` で始まるモジュールを無視するよう直す。m0003 のテストが通ることを確認する
- [x] 4.2 `m0004_operation_history.py` を追加し（`DASHBOARD_API_TOKEN` の追記、起動中なら再ビルド、sudo 不要、非破壊）、`.env.example` に `DASHBOARD_API_TOKEN=change-me` を加える。キーの追記、既存の値を変えないこと、起動中と停止中での compose の呼び出し、`--auto` で実行されること、最新のバージョンが 4 になることのテストを加えて通す
- [x] 4.3 `devenv check-health` に `http.api.dashboard` を加える（前提は `http.https.dashboard`、失敗は WARN）。OK、トークン不一致で WARN、ダッシュボード停止時に SKIP のテストを加え、正常系の件数を更新して通す
- [x] 4.4 `devenv uninstall` が削除するボリュームに `wp-dashboard-data` を加える。uninstall のテストで削除対象に含まれることを確認する

## 5. ドキュメントと確認

- [x] 5.1 README に操作履歴（記録するコマンド、表示場所、失敗時の警告、`DASHBOARD_API_TOKEN`）、DB の置き場所（ボリューム `wp-dashboard-data`）、ホストで `manage.py migrate` は不要なことを書く。`uv run pytest` がすべて通ることを確認する
- [x] 5.2 実環境（環境バージョン 3）で `.githooks/post-merge` を実行し、migration 4 が自動適用されて環境バージョンが 4 になることを確認する。続けて `devenv check-health` を実行して全項目 OK になり、ダッシュボードの操作履歴に migrate と check-health の 2 件が表示されることを確認する。`wp-dashboard` を停止して `devenv check-health` を実行し、警告が出て終了コードが変わらないことを確認してから、ダッシュボードを起動し直す
