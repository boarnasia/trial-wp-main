## Context

- 段階 1（`migrate-to-django`）で、ダッシュボードと CLI は 1 つの Django プロジェクトになった。DB は SQLite で設定済みだが、モデルはなく、INSTALLED_APPS に `auth`・`contenttypes`・`sessions` もない。
- 段階 1 で決めた方針: DB に書き込むのはダッシュボード（Web プロセス）だけ。CLI から更新が必要なときは Web API を呼ぶ。理由は、macOS の Docker Desktop の bind mount では SQLite のファイルロックが信頼できないため。
- ダッシュボードは gunicorn（2 worker）で動き、Caddy の内部 CA による HTTPS（`local.wp-main.yamashita109.com`）で公開される。`PROXY_BIND_ADDRESS=0.0.0.0` にすると LAN からも見える。
- CLI は Caddy のルート証明書を `.local/caddy-root.crt`（`config.CA_CERT_FILE`）に書き出す処理を持つ（`trust.export_root_cert`）。
- `devenv check-health` の HTTP 確認は、キーチェーンの CA を参照するために macOS 標準の curl を使っている。

## Goals / Non-Goals

**Goals:**
- `install`・`migrate`・`check-health` の結果を、ダッシュボードの DB に残して一覧で見られるようにする。
- 「Web だけが書き込み、CLI は API を呼ぶ」という形を、認証と失敗時の扱いを含めて実装として確立する。以後の DB 利用はこの形に従う。
- 記録の失敗が CLI 本来の動作を変えないようにする。

**Non-Goals:**
- ログイン、admin、ユーザー管理。
- 記録できなかった履歴の再送（ユーザーの判断で、警告して続行とする）。
- 履歴の検索、絞り込み、削除の UI。
- ダッシュボードからホストを操作する機能。

## Decisions

### 1. モデル

`wp_main.dashboard` に 1 モデルだけ置く。

```python
class Operation(models.Model):
    command = models.CharField(max_length=32)        # install / migrate / check-health
    options = models.JSONField(default=dict)         # {"root": "...", "auto": true, ...}
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(db_index=True)
    exit_code = models.IntegerField()
    succeeded = models.BooleanField()
    summary = models.CharField(max_length=500)       # "3 → 4" / "OK 26 / WARN 1 / FAIL 0 / SKIP 0" / エラー文
```

- 成否は `exit_code == 0` と同じとは限らない（`migrate --auto` は失敗しても 0 で終わる）。そのため `succeeded` を別に持つ。
- `options` には typer が受け取った引数の値だけを入れる。今の CLI には秘密値を受け取るオプションがないので、そのまま保存してよい。秘密値を受け取るオプションを加えるときは、除外の仕組みを先に入れる。
- 1000 件を超えたら、記録の直後に古い順に削除する。件数が小さいので、別のジョブは作らない。
- INSTALLED_APPS に `django.contrib.contenttypes` は加えない。`JSONField` と通常のモデルには不要。

### 2. DB の置き場所と django:migration

- `docker-compose.yml` にボリューム `wp-dashboard-data` を定義し、ダッシュボードの `/data` にマウントする。`DJANGO_DB_PATH=/data/db.sqlite3` をコンテナに渡す。
- イメージのビルドで `/data` を作り、所有者を `nobody` にする。名前付きボリュームは、初回のマウント時にイメージ側のディレクトリの所有者を引き継ぐ。
- 起動コマンドを `manage.py migrate --noinput && exec gunicorn ...` にする。healthcheck は gunicorn が応答してから通るので、「healthy になる前に適用される」が満たされる。
- gunicorn の 2 worker が同時に書き込むと、SQLite の書き込みロックで待ちが起きる。`OPTIONS: {"timeout": 5}` と WAL モード（`init_command` で `PRAGMA journal_mode=WAL`）で吸収する。ボリュームはコンテナ内の Linux のファイルシステムなので、WAL が問題なく動く。
- ホストで `uv run manage.py migrate` を実行すると、ホストの `.local/db.sqlite3` に同じスキーマが作られる。ダッシュボードの DB とは無関係で、何も読まれない。README に「ホストで `manage.py migrate` は不要」と書く。
- 代替案: `.local/` の bind mount。ユーザーとの合意で名前付きボリュームを採った。

### 3. API

Django Ninja の既存の `NinjaAPI` にルートを加える。

| メソッド | パス | 用途 |
| --- | --- | --- |
| POST | `/api/operations` | 1 件を記録する。201 と記録した内容を返す |
| GET | `/api/operations?limit=20` | 新しい順に返す（`limit` は 1〜100） |

- 認証は Ninja の `HttpBearer` で行う。`Authorization: Bearer <DASHBOARD_API_TOKEN>` を `hmac.compare_digest` で比べる。環境変数が空なら常に拒否する。
- パスワード取得 API（`/api/sites/{id}/password`）には認証を付けない。今の動作を変えないため（ブラウザからトークンなしで呼んでいる）。
- 入力は Ninja の `Schema` で検証する。`command` は 3 つの値に限る。`summary` は 500 文字で切る。
- トップページの一覧は API を経由せず、ビューが直接 ORM で読む。読むのもダッシュボード内なので、方針に反しない。

### 4. CLI からの送信

- 新しいモジュール `wp_main/operations.py` に `record(command, options, started_at, exit_code, succeeded, summary)` を置く。
- 送信先は `https://local.wp-main.yamashita109.com/api/operations`。`urllib.request` と、`cafile=CA_CERT_FILE` の `ssl` コンテキストを使う。キーチェーンを参照しないので、`--skip-trust` の環境でも検証できる。CA_CERT_FILE がなければ、`trust.export_root_cert` と同じ `docker compose cp`（読み取りのみ）で書き出してから送る。
- タイムアウトは 3 秒。どんな例外も捕まえて、標準エラー出力に `警告: 操作履歴を記録できませんでした: <理由>` を表示する。終了コードは変えない。
- トークンは wp-main の `.env` から `sites.read_env(MAIN_DIR)` で読む。ない場合は送信せずに警告を出す。
- 各サブコマンドは、本体の処理を `try/finally` で包んで記録する。`typer.Exit` と `DevEnvError` の終了コードを拾うため、記録は `finally` で行う。
  - `install`: `--dry-run` なら記録しない。要約は成功時「構築しました」、失敗時はエラー文。
  - `migrate`: 実行前と実行後の `env_version` を state から読む。変わっておらず失敗もしていなければ記録しない。要約は `前 → 後`。失敗時は `前 → 到達したバージョン: エラー文`。成否は例外の有無と、`versioning.migrate` の戻り値で判定する（`--auto` の終了コード 0 に引きずられない）。
  - `check-health`: 常に記録する。要約は判定ごとの件数。`--json` でも警告は標準エラー出力に出るので、標準出力の JSON は壊れない。
- テストでは送信先を差し替えられるよう、`record` は送信関数を引数で受け取れるようにする。
- `versioning.migrate` に `report(before, after, error)` を渡せるようにし、migration を実際に実行したときだけ呼ぶ。CLI はこれが呼ばれたときだけ記録する。
- `devenv` コマンドは Django のシステムチェックを行わない（`requires_system_checks = []`）。`JSONField` のチェックが DB に接続し、ホストに `.local/db.sqlite3` を作ってしまうため。

### 5. 表示

- トップページのサイト一覧の下に「操作履歴」の表を加える。列は終了日時（`Asia/Tokyo`）、コマンド、結果（成功・失敗）、要約。
- 失敗の行は、既存の CSS の `problem` と同じ色で区別する。色だけに頼らず「失敗」の文字も出す。
- ページは既に `Cache-Control: no-store` なので、再読み込みで最新になる。

### 6. dev-env:migration 4（`m0004_operation_history.py`）

- `REQUIRES_SUDO = False`、`DESTRUCTIVE = False`。
- `.env` に `DASHBOARD_API_TOKEN` がなければランダム値で追記する。m0003 の追記処理を `devenv/migrations/_env.py` のような共通関数に切り出し、両方から使う（ファイル名は `mNNNN_` 形式でないと `discover()` が拒否するため、`_` で始まる名前は `discover()` が無視するよう直す）。
- プロキシが起動中なら `docker compose up -d --build --wait` を実行する。ボリュームの追加、環境変数の追加、起動コマンドの変更を反映するため。

### 7. check-health

- HTTP グループに `http.api.dashboard` を加える。前提は `http.https.dashboard`。`GET /api/operations?limit=1` を CLI と同じ方法（`cafile` と `.env` のトークン）で呼び、200 なら OK。それ以外は WARN。
- 対処方法は `docker compose up -d --build dashboard`（`.env` の変更をコンテナに反映する）。
- 記録は best effort なので、失敗しても FAIL にはしない。

### 8. uninstall

- `docker compose down --volumes` がボリュームを消すが、compose を読めない状態でも消えるよう、削除するボリュームの一覧（`remove_volumes`）に `wp-dashboard-data` を加える。

## Risks / Trade-offs

- [ダッシュボードが止まっている間の操作は残らない] → ユーザーが選んだ方針。警告で気づけるようにする。
- [install の途中で失敗すると、ダッシュボードがまだなく記録できない] → 警告だけを出す。install の失敗は端末の出力で追う。
- [トークンを `.env` で変えても、コンテナを作り直すまで反映されない] → check-health の WARN と対処方法で案内する。
- [LAN に公開している場合、トークンを知っていれば履歴を書き込める] → `.env` は `0600` で、LAN の他の端末からは読めない。トークンなしの書き込みは 401 で拒否する。
- [SQLite の書き込みの競合] → 書き込みは CLI の実行ごとに 1 件で頻度が低い。WAL と timeout で十分。
- [ホストの `manage.py migrate` で無関係な DB ができる] → README で案内する。実害はない。
