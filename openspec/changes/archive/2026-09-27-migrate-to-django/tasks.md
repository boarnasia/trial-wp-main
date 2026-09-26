## 0. 前提

- [x] 0.1 `add-dashboard-migration-health` の残りのタスク 3.2 を終えてアーカイブする。`openspec list` にその change が出ず、`openspec validate migrate-to-django --strict` に dev-dashboard の INFO が出ないことを確認する

## 1. Django の土台

- [x] 1.1 `pyproject.toml` の依存を入れ替える（`django`、`django-ninja`、`django-typer` を本体に、`gunicorn`、`whitenoise` を extra `dashboard` に、`pytest-django` を dev に加え、`fastapi`、`uvicorn`、`jinja2`、`httpx2` を外す）。pytest の設定に `DJANGO_SETTINGS_MODULE = "wp_main.settings"` を加える。`uv sync` が通ることを確認する
- [x] 1.2 `manage.py`、`src/wp_main/settings.py`、`urls.py`、`wsgi.py` と空の app `wp_main.cli` を作る（design の decision 4 の設定）。`devenv` グループに `typer.Exit(3)` を返すだけの仮のサブコマンドを置き、`uv run manage.py devenv <仮>` の終了コードが 3 になること、`uv run manage.py migrate` が何も適用せず `.local/db.sqlite3` 以外を変えないことを確認する。確認後に仮のサブコマンドを消す

## 2. dev-env:migration の移動

- [x] 2.1 `src/wp_main/devenv.py` を `src/wp_main/devenv/__init__.py` に、`src/wp_main/migrations/` を `src/wp_main/devenv/migrations/` に `git mv` し、`versioning.py` の既定のパッケージとインポートを直す。`tests/test_versioning.py` と `tests/test_m0002_dashboard.py` が通ることを確認する

## 3. CLI

- [x] 3.1 `src/wp_main/cli/management/commands/devenv.py` に `install`、`uninstall`、`migrate`、`check-health`、`version` を移す。オプション、出力、終了コード、`--auto` の終了コード 0、環境バージョンの警告（`migrate`、`check-health`、`version` では出さない）を現在と同じにする。旧 `src/wp_main/cli.py` を削除する。CLI を呼ぶテスト（`tests/test_health.py`、`tests/test_versioning.py`）を `manage.py` 経由に書き換えて通す
- [x] 3.2 `src/wp_main/cli/legacy.py` を作り、`[project.scripts] cli` をそこへ向ける。`uv run cli dev-env:check-health` が何も実行せずに `uv run manage.py devenv check-health` を案内し、0 以外で終わるテストを加えて通す
- [x] 3.3 コード内の案内文（`versioning.MIGRATE_COMMAND`、`versioning.py` の未導入の案内、`health.py` の `INSTALL_HINT` と `--skip-trust` の案内、ダッシュボードのテンプレート）を新しいコマンドに置き換える。`grep -rn "uv run cli\|dev-env:" src .githooks` が legacy.py 以外で 0 件になることを確認する（`dev-env:migration` の用語は除く）
- [x] 3.4 `.githooks/post-merge` と `post-rewrite` を `uv run --quiet manage.py devenv migrate --auto` に変える。一時的なリポジトリで post-merge を実行し、失敗しても終了コード 0 になることを確認する

## 4. ダッシュボード

- [x] 4.1 `src/wp_main/dashboard/` を Django app にする。`/`（GET と HEAD、no-store）、`/healthz` を Django のビューで、`/api/sites/{site_id}/password` を Django Ninja で実装する（docs と openapi は無効）。`app.py` を削除する。`data.py` は `url_label` の追加だけにする
- [x] 4.2 `templates/index.html` を Django テンプレート言語に書き換える（`{% static %}`、表示用の `url_label`）。静的ファイルは WhiteNoise で `/static/` から配る
- [x] 4.3 `tests/test_dashboard.py` を `django.test.Client` に移し、既存の観点（一覧、HTML にパスワードを含まない、パスワード取得、404、no-store、HEAD、`.env` がない場合と値が欠けている場合）がすべて通ることを確認する
- [x] 4.4 `dashboard.Dockerfile` を gunicorn の起動に変え、`docker-compose.yml` のダッシュボードに `DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:-}` を渡す。`.env.example` に `DJANGO_SECRET_KEY=change-me` を加える。`docker compose build dashboard` が通り、起動したコンテナが healthy になることを確認する

## 5. dev-env:migration 3

- [x] 5.1 `src/wp_main/devenv/migrations/m0003_django.py` を追加する（`REQUIRES_SUDO = False`、`DESTRUCTIVE = False`）。`.env` に `DJANGO_SECRET_KEY` がなければ追記し、Caddy が起動中なら `docker compose up -d --build --wait` を実行する。キーの追記、既存のキーを変えないこと、起動中と停止中での compose の呼び出し、`--auto` で実行されることのテストを加えて通す。`discover()` の最新のバージョンが 3 になることを確認する

## 6. ドキュメントと確認

- [x] 6.1 README の CLI の節、ダッシュボードの節、環境バージョンの節を新しいコマンドに書き換え、dev-env:migration と django:migration の用語、DB の方針（SQLite、Web 側だけが書き込む）を加える
- [x] 6.2 `uv run pytest` がすべて通ることを確認する
- [x] 6.3 実環境（環境バージョン 2）で、この change のブランチを `git pull` 相当で取り込み、フックで migration 3 が自動適用されて環境バージョンが 3 になることを確認する。続けて `uv run manage.py devenv check-health` がすべて OK になり、ダッシュボードの一覧とパスワードの表示とコピーが切り替え前と同じに動くことをブラウザで確認する
