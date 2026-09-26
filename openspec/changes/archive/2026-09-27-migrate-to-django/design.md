## Context

- ダッシュボードは `src/wp_main/dashboard/` の FastAPI アプリ（`app.py` 34 行、`data.py` 75 行、Jinja2 テンプレート 1 枚、静的ファイル 2 つ）。DB・認証・フォームはない。コンテナ `wp-dashboard` で uvicorn が動き、Caddy が `dashboard:8000` へ転送する。サイトディレクトリは `/sites/<id>` に読み取り専用でマウントする。
- CLI は `src/wp_main/cli.py` の Typer アプリで、ホスト上で `uv run cli dev-env:<name>` として動く。callback で環境バージョンの警告を出し、`DevEnvError` を終了コード 1 に変える。`--auto` はどんな失敗でも終了コード 0 にする。
- dev-env:migration は `src/wp_main/migrations/mNNNN_*.py` にあり、`versioning.discover()` が読み込む。git のフック（`.githooks/post-merge`、`post-rewrite`）が `uv run cli dev-env:migrate --auto` を呼ぶ。
- `add-dashboard-migration-health`（migration 2）は実装済みで未アーカイブ。この change の delta はそのアーカイブ後の spec を前提にしている。
- `devenv install` は `.env` も Docker もない状態から動く必要がある。

## Goals / Non-Goals

**Goals:**
- ダッシュボードと CLI を 1 つの Django プロジェクト（同じ settings、同じ `manage.py`）に載せる。
- 利用者から見える動作を変えない。ダッシュボードの URL・HTML・API 応答・ヘッダー、CLI のオプション・出力・終了コードは同じにする。変わるのはコマンドの呼び出し方だけにする。
- dev-env:migration と django:migration を、置き場所・コマンド・記録先で分ける。
- 既存の環境が `git pull` だけで新しいダッシュボードに切り替わる。

**Non-Goals:**
- モデル、admin、認証、セッションの導入（段階 2）。
- ダッシュボードからホストを操作する機能。
- ドメインロジック（`health`、`hosts`、`sites`、`trust`、`docker`、`runner` など）の書き直し。移動とインポートの修正だけにする。

## Decisions

### 1. プロジェクトの構成

```
manage.py                         # DJANGO_SETTINGS_MODULE=wp_main.settings
src/wp_main/
├── settings.py  urls.py  wsgi.py
├── cli/                          # Django app（management command の置き場）
│   ├── management/commands/devenv.py
│   └── legacy.py                 # 旧 `uv run cli` の案内だけ
├── dashboard/                    # Django app（views、api、templates、static）
├── devenv/                       # Django app にしない普通のパッケージ
│   ├── __init__.py               # 旧 devenv.py（install / uninstall）
│   └── migrations/               # dev-env:migration（旧 wp_main/migrations/）
└── config.py health.py hosts.py sites.py trust.py docker.py runner.py versioning.py
```

- `wp_main` 自体は Django app にしない。app にすると `wp_main/migrations/` を Django が DB の移行として探すため。
- `devenv` も INSTALLED_APPS に入れない。入れると `devenv/migrations/` が django:migration として読まれる。management command は別の app（`wp_main.cli`）に置く。
- 代替案: dev-env:migration を `env_migrations/` などの別名にする。ユーザーと合意した `devenv/migrations/` を優先し、app に入れないことで衝突を避ける。

### 2. CLI は django-typer で書く

- `manage.py devenv <sub>` を、django-typer の `TyperCommand` のサブコマンドとして実装する。既存の Typer の `Annotated` オプション、`typer.secho`、`typer.Exit` の書き方をほぼそのまま移せる。
- 環境バージョンの警告は、django-typer のグループの初期化 callback で出す。`migrate`、`check-health`、`version` では出さない。Django 本体のコマンドと `manage.py help` には callback が関わらないので、警告は出ない。
- `version` は `devenv version` にする。`manage.py version` は Django のバージョンを表示し、上書きしない。
- django-typer のバージョンと、`typer.Exit` の終了コードがそのまま `manage.py` の終了コードになることは、実装の最初に確かめる（tasks 1.2）。想定どおりでなければ、`sys.exit` で返す薄い処理を callback 側に置く。
- 代替案: Django 標準の `BaseCommand` で書く。サブコマンドとオプションの定義を argparse で書き直す量が多く、既存のテストも崩れるため採らない。

### 3. `uv run cli` は案内だけを残す

- `[project.scripts] cli = "wp_main.cli.legacy:main"` とし、引数の `dev-env:<name>` を `uv run manage.py devenv <name>` に読み替えた文を表示して終了コード 2 で終わる。何も実行しない。
- 自動で読み替えて実行はしない。新しいコマンドを覚えてもらうのが目的のため。次の段階で削除してよい。

### 4. settings

- `INSTALLED_APPS`: `django.contrib.staticfiles`、`wp_main.cli`、`wp_main.dashboard`、`django_typer`（必要な場合）。`auth`、`contenttypes`、`sessions`、`admin` は段階 2 まで入れない。これで `manage.py migrate` は何もしない。
- `DATABASES`: SQLite。パスは環境変数 `DJANGO_DB_PATH`、既定は `<wp-main>/.local/db.sqlite3`（`.local/` は既に gitignore 済み）。段階 1 では DB に接続するコードがないので、ファイルは作られない。
- `SECRET_KEY`: 環境変数 `DJANGO_SECRET_KEY`。ない場合はプロセスごとの一時的な値を使う。`devenv install` は `.env` ができる前に動くため、必須にはしない。段階 1 は署名を使う機能（セッション、CSRF 付きフォーム）を持たないので、一時的な値でも動作は変わらない。段階 2 で署名を使う機能を入れるときに必須にする。
- `DEBUG`: 環境変数 `DJANGO_DEBUG`、既定は False。
- `ALLOWED_HOSTS`: `local.wp-main.yamashita109.com`（`config.DASHBOARD_DOMAIN`）、`127.0.0.1`、`localhost`。コンテナの healthcheck が `127.0.0.1:8000` に来るため。
- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`。Caddy が付けるヘッダーを信頼する。
- 静的ファイルは WhiteNoise で配る。ファイルが 2 つだけなので `collectstatic` は使わず、`WHITENOISE_USE_FINDERS = True` で app の `static/` から直接配る。URL は `/static/dashboard.css`、`/static/dashboard.js` のままにする。
- `wp-main/.env.example` に `DJANGO_SECRET_KEY=change-me` を加える。`devenv install` の既存の処理でランダム値に置き換わる。compose は `environment: DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:-}` で渡す。`:?` を使うと、キーのない環境で `docker compose down` まで失敗し、`devenv uninstall` が動かなくなるため使わない。

### 5. ダッシュボード

- `/`: Django のビュー。GET のビューは HEAD にも応答するので、`curl -I` の疎通確認はそのまま通る。`Cache-Control: no-store` を付ける。
- `/api/sites/{site_id}/password`: Django Ninja の `NinjaAPI(docs_url=None, openapi_url=None)` のルート。見つからないときは 404 と `{"detail": "パスワードが見つかりません"}` を返す（FastAPI と同じ形）。成功時も失敗時も `Cache-Control: no-store` を付ける。
- `/healthz`: `{"status": "ok"}` を返す Django のビュー。
- テンプレートは Django テンプレート言語に書き直す。`url_for('static', ...)` は `{% static %}` に、`replace` と `trim` は `SiteView` に表示用の値（`url_label`）を加えて置き換える。`missing | join(', ')` は Django の `join` フィルタで書ける。
- `data.py` はフレームワークに依存していないので、`SiteView.url_label` の追加だけにとどめる。
- JSON は `ensure_ascii=False` で返し、FastAPI 版と同じく日本語をエスケープしない。
- コンテナの起動は `gunicorn wp_main.wsgi:application --bind 0.0.0.0:8000`。代替案の uvicorn + ASGI は、非同期のビューがないため採らない。

### 6. dev-env:migration 3（`devenv/migrations/m0003_django.py`）

- `REQUIRES_SUDO = False`、`DESTRUCTIVE = False` とし、`git pull` 後に自動で適用されるようにする。
- `up`: wp-main の `.env` に `DJANGO_SECRET_KEY` がなければランダム値を追記する。Caddy が起動中なら `docker compose up -d --build --wait` を実行する。migration 2 と同じ判定方法を使う。
- フックはマージ後の作業ツリーのファイルが実行されるので、この change を取り込む `git pull` で新しいフック（`manage.py devenv migrate --auto`）が動く。

### 7. DB の書き込み方針（段階 2 に向けた記録）

- SQLite に書き込むのは Django の Web プロセス（ダッシュボードのコンテナ）だけにする。
- ホストの CLI が DB の内容を変える必要があるときは、ダッシュボードの Web API（Django Ninja）を呼ぶ。CLI は SQLite のファイルを直接開かない。
- 理由: macOS の Docker Desktop の bind mount では SQLite のファイルロックが信頼できない。書き込む側を 1 プロセスにすれば、ロックの競合が起きない。
- DB ファイルの置き場所（bind mount か名前付きボリュームか）、API の認証、ダッシュボードが停止しているときの CLI の振る舞いは、段階 2 で決める。

### 8. テスト

- `pytest-django` を使い、`DJANGO_SETTINGS_MODULE = "wp_main.settings"` を pytest の設定に入れる。
- ダッシュボードのテストは FastAPI の `TestClient` から `django.test.Client` に移す。検証する内容（HTML にパスワードを含まない、404、no-store、HEAD）は変えない。
- CLI のテスト（`test_health.py`、`test_versioning.py` の CliRunner を使う部分）は `call_command` か `manage.py` のサブプロセス実行に移す。終了コードと標準出力・標準エラー出力の内容を同じ観点で確かめる。

## Risks / Trade-offs

- [コマンドの打ち方が変わり、手順書やシェルの履歴が使えなくなる] → `uv run cli` を案内だけで残す。README を更新する。
- [`manage.py` のたびに Django の setup が走り、起動が少し遅くなる] → INSTALLED_APPS を最小にする。CLI は DB に接続しない。
- [django-typer の挙動（終了コード、callback）が想定と違う] → 実装の最初に小さな検証を行い、合わなければ decision 2 の代替（薄い終了処理）を使う。
- [SECRET_KEY がない環境で一時的な値を使う] → 段階 1 では署名を使わないので影響はない。段階 2 で必須にする。
- [dev-env:migration 3 の自動実行でダッシュボードの再ビルドが走り、pull が遅くなる] → プロキシが起動中のときだけ実行する。migration 2 と同じ方針。
- [未アーカイブの `add-dashboard-migration-health` と同じ要件を変える] → そちらを先にアーカイブしてから、この change をアーカイブする。
