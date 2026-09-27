# wp-main

WordPress 7 系（wp-wp1）と 6 系（wp-wp2）のローカル開発環境を管理するリポジトリ。
Caddy リバースプロキシ（内部 CA による HTTPS）と、両サイトを一括起動する Compose 定義、環境を構築・破棄する CLI を持つ。

| サイト | リポジトリ | URL | イメージ | デバッグ用ポート |
| --- | --- | --- | --- | --- |
| wp1 | `../wp-wp1`（trial-wp-wp1） | https://local.wp1.yamashita109.com/ | `wordpress:7.1-apache` | 127.0.0.1:8081 |
| wp2 | `../wp-wp2`（trial-wp-wp2） | https://local.wp2.yamashita109.com/ | `wordpress:6.7-apache` | 127.0.0.1:8082 |

ダッシュボード: https://local.wp-main.yamashita109.com/ （両サイトへのリンク、ログインリンク、管理者の ID/PW を表示する）

```
{root}/
├── wp-main/   Caddyfile, docker-compose.yml（include で両サイトを取り込む）, CLI
├── wp-wp1/    wp1-wordpress + wp1-db
└── wp-wp2/    wp2-wordpress + wp2-db
        └── wp-global-net（外部ネットワーク）で Caddy と WordPress を接続。DB はサイト内ネットワークだけ
```

## 前提

- macOS、Docker Desktop（Compose v2.20 以上）、uv
- GitHub に SSH で接続できること（サイトリポジトリを clone する）
- ポート 80 / 443 が空いていること

## CLI

```bash
uv run manage.py help devenv                  # コマンド一覧
uv run manage.py devenv version
uv run manage.py devenv check-health          # 環境が正常か確認（読み取りのみ）
uv run manage.py devenv migrate               # 環境を最新の環境バージョンへ移行
uv run manage.py devenv install               # 構築して起動（sudo のパスワードを求められる）
uv run manage.py devenv install --dry-run     # 実行内容の確認だけ
uv run manage.py devenv uninstall             # 確認後にすべて削除（--yes で確認を省略）
```

CLI はダッシュボードと同じ Django プロジェクトの management command（`devenv`）として動く。以前の `uv run cli dev-env:<name>` は廃止し、実行すると新しいコマンドを案内して終了する。

`devenv install` が行うこと:

1. `{root}/wp-wp1`、`{root}/wp-wp2` を clone する（リモートが空ならテンプレートから初期化してローカルにコミットする。push はしない）
2. wp-main と各サイトの `.env` を `.env.example` から生成する（`change-me` はランダム値に置き換える。既存の `.env` は上書きしない）
3. `wp-global-net` ネットワークを作る
4. `/etc/hosts` に `# >>> wp-dev-env >>>` ブロックを追加する（sudo）。書き換え前の内容は `/etc/hosts.wp-dev-env.bak` に保存する。マーカーの対応が崩れている場合は書き換えずに止まる
5. `docker compose up -d --wait` で全サービスを起動し、WordPress を初期セットアップする
6. Caddy の内部 CA を System キーチェーンに信頼済みとして登録する（sudo）。`--skip-trust` で省略

主なオプション: `--root <dir>`（既定は wp-main の親）、`--no-start`、`--skip-trust`。

`devenv uninstall` は、コンテナ・ボリューム・イメージ・ネットワーク・hosts ブロック・CA・サイトディレクトリ・`.local/` の状態ファイルを削除する。サイトに未コミットや未 push の変更があれば警告する。`/etc/hosts.wp-dev-env.bak` は復旧用に残し、削除コマンド（`sudo rm /etc/hosts.wp-dev-env.bak`）を最後に案内する。

管理者のユーザー名とパスワードは各サイトの `.env`（`WP_ADMIN_USER` / `WP_ADMIN_PASSWORD`）にある。

## ダッシュボード

`https://local.wp-main.yamashita109.com/` で、両サイトの URL・ログインリンク・デバッグ用ポート・管理者のユーザー名とパスワードを確認できる。

- 値は表示のたびに `../wp-wp1/.env` と `../wp-wp2/.env` から読み込む。`.env` を書き換えれば、再起動せずに次の表示から反映される
- サイトディレクトリは読み取り専用でマウントしている
- パスワードは伏せて表示し、表示ボタンかコピーボタンを押したときだけ取得する
- この機能を入れる前に構築した環境では、`uv run manage.py devenv migrate` を実行する（dev-env:migration 2。hosts にドメインを加えるため sudo のパスワードを求められ、pull 後の自動移行では実行されない）
- Django 版への切り替え（dev-env:migration 3）は、`git pull` の後に自動で適用される。wp-main の `.env` に `DJANGO_SECRET_KEY` を加え、プロキシが起動中ならダッシュボードを再ビルドする

## 操作履歴

`devenv install`・`devenv migrate`・`devenv check-health` の結果は、ダッシュボードのサイト一覧の下に新しい順で 20 件表示される（DB には最大 1000 件を残す）。

- CLI はコマンドの終了時に、ダッシュボードの API（`/api/operations`）へ結果を送る。認証には wp-main の `.env` の `DASHBOARD_API_TOKEN` を使う
- ダッシュボードが止まっているなどで送れないときは、`警告: 操作履歴を記録できませんでした` を表示するだけで、コマンドの結果と終了コードは変わらない。送れなかった履歴は後から送り直さない
- 記録しないもの: `--dry-run` の実行、何も適用しなかった `devenv migrate`、`devenv uninstall`（最後に DB のボリュームごと消えるため）
- `.env` の `DASHBOARD_API_TOKEN` を書き換えたら、`docker compose up -d --build dashboard` でコンテナに反映する

## 公開範囲（PROXY_BIND_ADDRESS）

Caddy の 80/443 は、既定で `127.0.0.1` にだけ公開する。実機のスマートフォンなど、LAN の他の端末から開くときだけ全インターフェースに公開する。

```bash
PROXY_BIND_ADDRESS=0.0.0.0 docker compose up -d   # その場だけ公開する
echo 'PROXY_BIND_ADDRESS=0.0.0.0' >> .env         # 常に公開する（実行時の指定が .env より優先される）
```

`0.0.0.0` にすると、同じ LAN の端末からダッシュボードの管理者パスワードも見えるようになる。信頼できないネットワークでは使わない。

## 環境バージョンと移行

wp-main の更新には、pull するだけでは反映されない変更（ボリューム名の変更、`.env` への変数の追加など）がある。これを migration として配り、環境バージョンで適用状況を管理する。

migration は 2 種類あり、呼び分ける。この節の migration は dev-env:migration を指す。

| 呼び方 | 対象 | 置き場所 | 実行 | 記録先 |
| --- | --- | --- | --- | --- |
| dev-env:migration | 開発環境のリソース（hosts、ボリューム、`.env` など） | `src/wp_main/devenv/migrations/` | `uv run manage.py devenv migrate` | `.local/dev-env-state.json` |
| django:migration | Django の DB スキーマ | 各 Django app の `migrations/` | ダッシュボードのコンテナの起動時に自動 | ダッシュボードの DB（ボリューム `wp-dashboard-data`） |

- 最新のバージョン: `src/wp_main/devenv/migrations/` にある migration の最大番号（migration がなければ 1）
- 導入済みのバージョン: `.local/dev-env-state.json` の `env_version`（マシンごと、git の管理外）。記録がない既存の環境は 1 とみなす

```bash
uv run manage.py devenv migrate               # 未適用の migration を順に実行
uv run manage.py devenv migrate --dry-run     # 実行する migration の一覧だけ表示
```

`devenv install` は wp-main の `core.hooksPath` を `.githooks` に設定する。これにより、`git pull`（merge と rebase の両方）の後に `devenv migrate --auto` が自動で動く。
自動で実行するのは、sudo もデータの削除も必要とせず、Docker に接続できる場合だけ。それ以外は何もせずに、端末で `uv run manage.py devenv migrate` を実行するよう表示する。
install 済みの環境でフックだけを有効にするには、`git config core.hooksPath .githooks` を実行する。

環境バージョンが古いと、`devenv` の各サブコマンドが警告を出し、`devenv check-health` は WARN を出す。

### migration の書き方

`src/wp_main/devenv/migrations/m0002_<名前>.py` のように、2 からの連番で 1 ファイルずつ追加する。

```python
VERSION = 2                      # ファイル名の番号と同じ
DESCRIPTION = "wp1 の DB ボリューム名を変更"
REQUIRES_SUDO = False            # True なら自動実行しない（端末での実行が必要）
DESTRUCTIVE = False              # True なら自動実行せず、実行前に確認をとる
LOSES = ""                       # DESTRUCTIVE のとき、失われるものを書く

def up(ctx):                     # ctx.runner / ctx.root / ctx.main_dir / ctx.sites
    ...
```

- 途中で失敗して再実行されても結果が同じになるよう、冪等に書く
- 変更してよいのは環境のリソース（ボリューム、ネットワーク、hosts、`.env` への変数の追加、CA、コンテナ）だけ。wp-wp1 / wp-wp2 の中身は変更しない（サイトの変更は各リポジトリのコミットで配る）
- 後戻り（down）は用意しない。困ったときは uninstall してから install し直す

## 日常の操作（wp-main で実行）

```bash
docker compose up -d                 # 一括起動
docker compose ps
docker compose logs -f caddy wp1-wordpress
docker compose stop                  # 停止（コンテナを残す）
docker compose down                  # 停止して削除（DB と CA のボリュームは残る）
docker compose run --rm wp1-cli wp plugin list   # WP-CLI
```

単体起動（wp-main の Caddy を使わない）:

```bash
cd ../wp-wp2 && docker compose up -d
# デバッグ用ポートはホスト名とポートが WP_HOME と違うため、そのままだと WordPress がポートを外した URL へ 301 を返す
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: local.wp2.yamashita109.com' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8082/   # 200 なら正常
```

単体起動と一括起動はコンテナ名が同じなので同時には動かない。切り替えるときは先に片方を `docker compose down` する。
ボリューム名は固定なので、どちらで起動しても同じ DB を使う。切り替え時に出る `volume ... already exists but was created for project ...` の警告はこのためで、無視してよい。

## 検証

```bash
uv run manage.py devenv check-health          # 各項目を OK / WARN / FAIL / SKIP で表示
uv run manage.py devenv check-health --json   # 機械向け（CI やスクリプトから使う）
```

sudo は使わず、環境も変更しない。確認する項目は次のとおり。

| グループ | 項目 |
| --- | --- |
| 構成 | サイトリポジトリの origin、各 `.env` の有無と `change-me` の残り |
| ホスト | 各サイトとダッシュボードのドメインの名前解決（127.0.0.1）、`wp-global-net`、Caddy の CA がキーチェーンに登録されているか |
| コンテナ | Caddy・各サイトの WordPress と DB・ダッシュボードが running か（DB とダッシュボードは healthy か） |
| HTTP と WordPress | 各サイトとダッシュボードの HTTPS の応答と証明書の検証、HTTP から HTTPS へのリダイレクト、操作履歴 API に接続できるか（できなければ WARN）、WordPress がインストール済みか、メジャーバージョン |

- 前提の項目が FAIL なら、その項目は SKIP になる（例: Caddy が止まっていれば HTTP の項目はすべて SKIP）。WARN と FAIL には対処方法が表示される。
- FAIL が 1 つでもあれば終了コード 1、WARN だけなら 0。
- 管理画面へのログインは確認しない。ブラウザで `/wp-admin/` にログインし、リダイレクトがループしないことを確認する。

## 開発

```bash
uv run pytest
DASHBOARD_SITES_DIR=/path/to/sites DJANGO_DEBUG=1 uv run manage.py runserver   # ダッシュボードだけをローカルで起動（<dir>/wp1/.env と <dir>/wp2/.env を読む）
```

ダッシュボードと CLI は 1 つの Django プロジェクト（`manage.py`、`src/wp_main/settings.py`）にまとめている。ダッシュボードは app `wp_main.dashboard`（API は Django Ninja）、CLI は app `wp_main.cli` の management command。

DB は SQLite で、ダッシュボードのコンテナだけがマウントする名前付きボリューム `wp-dashboard-data`（`/data/db.sqlite3`）に置く。書き込むのはダッシュボードだけにし、CLI から DB を更新する必要があるときは Web API を呼ぶ。macOS の Docker Desktop の bind mount では SQLite のファイルロックが信頼できないため。django:migration はコンテナの起動時に適用されるので、ホストで `uv run manage.py migrate` を実行する必要はない（実行するとホストの `.local/db.sqlite3` に無関係な DB ができるだけ）。

サイトの雛形は `templates/wp-site/` にある（`{{SITE_ID}}` などをサイトごとに置換する）。雛形は空のリモートを初期化するときだけ使う。初期化した後は、各サイトリポジトリ側を直接編集する。
