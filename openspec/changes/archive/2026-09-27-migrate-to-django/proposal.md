## Why

ダッシュボード（FastAPI）と CLI（Typer）は別々の仕組みで書かれていて、設定・データ・コマンドの作法を共有できない。今後、ダッシュボードにデータの保持や管理画面を足すときに、FastAPI では DB・認証・管理画面を個別に組み合わせる手間が増える。Django + Django Ninja に揃え、拡張の土台と CLI との一体感を先に作る。この change は段階 1 として、利用者から見える動作（画面・API・コマンドの結果）を変えずに移行する。

## What Changes

- ダッシュボードを Django + Django Ninja で作り直す。URL、画面、パスワード取得 API、`/healthz`、`Cache-Control: no-store` は現在と同じにする。
- **BREAKING** CLI を Django の management command に移す。呼び出しは `uv run cli dev-env:<name>` から `uv run manage.py devenv <name>` に変わる。
  - `dev-env:install` → `devenv install`、`dev-env:uninstall` → `devenv uninstall`、`dev-env:migrate` → `devenv migrate`、`dev-env:check-health` → `devenv check-health`
  - `version` → `devenv version`（`manage.py version` は Django のバージョンを表示するため）
  - `help` → `manage.py help devenv`
  - `uv run cli` は残し、新しいコマンドを案内して 0 以外の終了コードで終わるだけにする
- 環境の移行を `dev-env:migration`、Django の DB の移行を `django:migration` と呼び分ける。dev-env:migration の置き場所を `src/wp_main/migrations/` から `src/wp_main/devenv/migrations/` に移す（Django が app 内の `migrations/` を DB の移行として読むため）。
- dev-env:migration 3 を追加する。wp-main の `.env` に `DJANGO_SECRET_KEY` がなければランダム値で加え、プロキシが起動中ならダッシュボードを再ビルドして起動する。sudo も破壊的な操作も不要なので、`git pull` 後に自動で適用される。
- git のフック（post-merge、post-rewrite）、README、コード内の案内文を新しいコマンドに書き換える。
- DB は SQLite（`.local/db.sqlite3`、git の管理外）とする。段階 1 ではモデルを持たず、DB を使わない。書き込みは Django の Web 側だけが行い、CLI から更新が必要な場合は Web API を呼ぶ方針を design に記録し、具体化は段階 2 で行う。

## Capabilities

### New Capabilities

なし

### Modified Capabilities
- `dev-env-cli`: エントリポイントを `uv run manage.py devenv <name>` に変え、各要件のコマンド名を置き換える。旧 `uv run cli` の案内を加える
- `dev-env-versioning`: コマンド名と案内文を置き換える。dev-env:migration と django:migration の区別と置き場所を加える
- `dev-env-health`: 対処方法として表示するコマンドを置き換える
- `dev-dashboard`: 既存の環境への Django 版ダッシュボードの導入（dev-env:migration 3）を加える

## Impact

- 依存: `fastapi`、`uvicorn`、`jinja2`、`httpx2` を外し、`django`、`django-ninja`、`django-typer`、`gunicorn`、`whitenoise`、`pytest-django` を加える
- コード: `src/wp_main/cli.py` を management command に置き換える。`src/wp_main/devenv.py` と `src/wp_main/migrations/` を `src/wp_main/devenv/` パッケージへ移す。`src/wp_main/dashboard/` を Django app にする。Django の設定（`settings.py`、`urls.py`、`wsgi.py`）と `manage.py` を加える
- コンテナ: `dashboard.Dockerfile` の起動コマンドを gunicorn に変える
- 運用: 既存の環境は `git pull` 後の自動移行で環境バージョン 3 になる。コマンドの打ち方が変わるため、README と手元の手順の更新が必要
- 前提: `add-dashboard-migration-health` を先にアーカイブする（同じ要件を変更しているため）
