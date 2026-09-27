# wp-main

WordPress 7 系（wp-wp1）と 6 系（wp-wp2）のローカル開発環境を管理するリポジトリ。
wp-main はメインコントローラーで、Caddy リバースプロキシ（内部 CA による HTTPS）・全サイトが共用する MySQL・各サイトの WordPress の Compose 定義と、環境を構築・破棄する CLI を持つ。サイトのリポジトリが持つのはサイトの中身（`wp-content/`）とサイト設定（`.env`）だけで、サイトは wp-main からしか起動しない。用語は [CONTEXT.md](CONTEXT.md)、設計判断は [docs/adr/](docs/adr/) にある。

| サイト | リポジトリ | URL | イメージ | デバッグ用ポート |
| --- | --- | --- | --- | --- |
| wp1 | `../wp-wp1`（trial-wp-wp1） | https://local.wp1.yamashita109.com/ | `wordpress:7.1-apache` | 127.0.0.1:8081 |
| wp2 | `../wp-wp2`（trial-wp-wp2） | https://local.wp2.yamashita109.com/ | `wordpress:6.7-apache` | 127.0.0.1:8082 |

開発は開発セッションとして始める。開発セッションの間だけ、共有インフラ・指定したサイト・ダッシュボードが動く。

```bash
uv run manage.py serve up --site=wp1,wp2 --detach   # 始める（端末から切り離す）
uv run manage.py serve logs -f                      # ログを追う
uv run manage.py serve down                         # 終える（共有インフラも止める。データは残る）
```

ダッシュボード: https://local.wp-main.yamashita109.com/ （両サイトへのリンク、ログインリンク、管理者の ID/PW、サイトの起動・停止、操作履歴）

```
{root}/
├── wp-main/   Caddyfile, docker-compose.yml（Caddy・共有 MySQL）, compose/<サイト ID>.yml（各サイトの WordPress）, CLI, ダッシュボード（ホストで動く）
├── wp-wp1/    wp-content/, config/, .env（サイト設定）
└── wp-wp2/    wp-content/, config/, .env（サイト設定）
        └── wp-global-net（外部ネットワーク）で Caddy と WordPress を接続。共有 MySQL（wp-mysql）は WordPress とだけ共有する wp-db ネットワーク
```

コンテナで動かすのは Caddy と WordPress・MySQL などの実行環境だけ。ダッシュボードのような開発用の道具は、ホストのプロセスとして `serve up` がまとめて起動する（Caddy は `host.docker.internal` 経由で転送する）。

共有インフラ（Caddy・MySQL）もサイトも、開発セッションの外では止まっているのが正常（[ADR 0002](docs/adr/0002-serve-daemonizes-itself.md)）。

## 前提

- macOS、Docker Desktop（Compose v2.20 以上）、uv
- GitHub に SSH で接続できること（サイトリポジトリを clone する）
- ポート 80 / 443 が空いていること

## CLI

```bash
uv run manage.py serve up --site=wp1,wp2     # 開発セッションを始める（前面で動く。Ctrl-C で終了。--detach で切り離す）
uv run manage.py serve down                   # 開発セッションを終える
uv run manage.py serve logs -f                # 開発セッションのログを追う
uv run manage.py help devenv                  # 環境の整備のコマンド一覧
uv run manage.py devenv version
uv run manage.py devenv check-health          # 環境が正常か確認（読み取りのみ）
uv run manage.py devenv migrate               # 環境を最新の環境バージョンへ移行
uv run manage.py devenv install               # 構築する（sudo のパスワードを求められる）
uv run manage.py devenv install --dry-run     # 実行内容の確認だけ
uv run manage.py devenv uninstall             # 確認後にすべて削除（--yes で確認を省略）
```

CLI はダッシュボードと同じ Django プロジェクトの management command（`serve` と `devenv`）として動く。以前の `uv run cli dev-env:<name>`・`devenv serve`・サブコマンドのない `serve` は廃止し、実行すると新しいコマンドを案内して終了する。`serve` は Django の `runserver` とは別物。

`devenv install` が行うこと:

1. `{root}/wp-wp1`、`{root}/wp-wp2` を clone する（リモートが空ならテンプレートから初期化してローカルにコミットする。push はしない）
2. wp-main と各サイトの `.env` を `.env.example` から生成する（`change-me` はランダム値に置き換える。既存の `.env` は上書きしない）。共有 MySQL の接続情報（`DB_USER`・`DB_PASSWORD`・`DB_ROOT_PASSWORD`）は wp-main の `.env` にある
3. `wp-global-net` ネットワークを作る
4. `/etc/hosts` に `# >>> wp-dev-env >>>` ブロックを追加する（sudo）。書き換え前の内容は `/etc/hosts.wp-dev-env.bak` に保存する。マーカーの対応が崩れている場合は書き換えずに止まる
5. 共有インフラ（Caddy・MySQL）を起動し、各サイトを 1 つずつ起動して WordPress を初期セットアップし、終わったらサイトを止める
6. Caddy の内部 CA を System キーチェーンに信頼済みとして登録する（sudo）。`--skip-trust` で省略
7. 共有インフラを止める（開発セッション中に実行した場合は止めない）
8. ダッシュボードの DB（`.local/db.sqlite3`）を最新のスキーマにし、最後に `serve up --site=all` の実行方法を表示する

主なオプション: `--root <dir>`（既定は wp-main の親）、`--no-start`、`--skip-trust`。

`devenv uninstall` は、コンテナ・ボリューム（共有 MySQL の `wp-mysql-data` を含む）・イメージ・ネットワーク・hosts ブロック・CA・サイトディレクトリ・`.local/` の状態ファイルとダッシュボードの DB を削除する。開発セッションが動いていれば、先に `serve down` で止めるよう表示する。サイトに未コミットや未 push の変更があれば警告する。`/etc/hosts.wp-dev-env.bak` は復旧用に残し、削除コマンド（`sudo rm /etc/hosts.wp-dev-env.bak`）を最後に案内する。

管理者のユーザー名とパスワードは各サイトの `.env`（`WP_ADMIN_USER` / `WP_ADMIN_PASSWORD`）にある。

## 開発セッション（serve）

```bash
uv run manage.py serve up --site=wp1          # wp1 だけ（前面で動く。Ctrl-C で終了）
uv run manage.py serve up --site=wp1,wp2      # 複数（カンマ区切り）
uv run manage.py serve up --site=all          # 全サイト
uv run manage.py serve up                     # サイトは起動しない（共有インフラとダッシュボードだけ）
uv run manage.py serve up --site=all --detach # 端末から切り離す（-d でもよい）
uv run manage.py serve down                   # 終える
uv run manage.py serve logs                   # ログを表示する（serve・dashboard・caddy・mysql・wp1・wp2 で絞れる）
uv run manage.py serve logs -f --tail 50 dashboard wp1
```

`serve up` が行うこと:

1. `--site` を確かめる（存在しない ID があれば何も起動せず、指定できる ID を表示して終わる）
2. 開発セッションが既に動いていれば、それを終える（共有インフラは止めずに使い回す）
3. ダッシュボードのポートが空いているか確かめ、ログを新しくする（直前のログは `.local/logs/*.log.1` に残る）
4. django:migration を適用し、共有インフラ（Caddy・MySQL）を起動する。起動できなければ、ここで失敗して終わる
5. 指定したサイトを起動する。起動に失敗したサイトは表示と操作履歴に残し、残りは続ける
6. ホストのプロセス（ダッシュボード）を起動する。`--detach` のときは、ダッシュボードが応答するのを確かめてから戻る

開発セッションは、`serve down`、前面の Ctrl-C、ホストのプロセスの異常終了のいずれかで終わる。終わるときは、ダッシュボード・その時点で動いているサイト（セッション中にダッシュボードから起動したものも含む）・共有インフラをすべて止める。コンテナは削除するが、ボリューム（共有 MySQL のデータなど）は残る。

- 開発セッションの PID は `.local/serve.pid`、ホストのプロセスのログは `.local/logs/` にある
- 監督するプロセスが強制終了されてコンテナが残った場合も、`serve down` で片付けられる（開発セッションがなくても、残ったサイトと共有インフラを止める）
- 以前の版から更新した環境で共有インフラが動いたまま残っている場合も、`serve down` で止まる

## ダッシュボード

`https://local.wp-main.yamashita109.com/` で、両サイトの URL・ログインリンク・デバッグ用ポート・管理者のユーザー名とパスワード・起動状態を確認できる。

- `serve` は、ダッシュボード（gunicorn）を `127.0.0.1:8000` だけで待ち受けて起動する。ポートは wp-main の `.env` の `DASHBOARD_PORT` で変えられる。変えたら `serve` を再起動し、`docker compose up -d caddy` で Caddy にも反映する
- `serve` は、ホストで動かす開発用のプロセスをまとめて起動する仕組みで、今はダッシュボードだけを動かす。vite などは `src/wp_main/processes.py` の一覧に加える。1 つが落ちると全体を止める
- `serve` を動かしていないときは、ダッシュボードの URL は 502 になる（各サイトには影響しない）
- 値は表示のたびに `{root}/wp-wp1/.env` と `{root}/wp-wp2/.env` から読み込む。`.env` を書き換えれば、再起動せずに次の表示から反映される。ダッシュボードはサイトディレクトリに書き込まない
- パスワードは伏せて表示し、表示ボタンかコピーボタンを押したときだけ取得する
- 画面は上から、共有インフラ、サイト、操作履歴の順に並ぶ。ヘッダーには環境バージョン（`環境 v6`。古いときは migrate の案内）を出す
- サイトの表には GitHub のリポジトリへのリンクがある。「サイト名で絞り込み」に入れた値は URL の `?site=` に残る

### DB 接続情報

共有インフラの欄に、ホストの DB クライアントから共有 MySQL につなぐための値（`127.0.0.1:<MYSQL_PORT>`、root と共用ユーザー `DB_USER` のパスワード）と、`wp-mysql` の状態を表示する。

- 値は表示のたびに wp-main の `.env` から読み込む。`MYSQL_PORT` の既定は 3306、`DB_USER` の既定は `wordpress`
- パスワードはサイトの管理者パスワードと同じく伏せて表示し、表示・コピーのときだけ `/api/db/root/password`・`/api/db/user/password` から取得する
- パスワードが `change-me` のままなら警告を出す

### 開発セッションの終了ボタン

ヘッダーの右端の電源ボタンで、確認の後に開発セッションを終了できる（`uv run manage.py serve down` と同じ）。

- `serve down` はダッシュボード自身も止めるため、切り離したプロセスで実行する。その出力は `.local/logs/serve.log` に残る
- LAN に公開している間（`PROXY_BIND_ADDRESS` が `127.0.0.1` 以外）は、ボタンを出さず、要求も拒否する

### サイトの起動・停止

各サイトの行の「起動」「停止」ボタンで、そのサイトの WordPress を起動・停止できる。

- 起動は、共有 MySQL にサイトの schema がなければ作ってから `docker compose up -d --wait wp1-wordpress`（最大 120 秒待つ）。停止は `docker compose stop wp1-wordpress`。コンテナとボリュームは消さない。共有インフラと他のサイトには触れない
- 状態は、WordPress が動いていて共有 MySQL が healthy なら「起動中」、WordPress が止まっていれば「停止中」、WordPress は動いているが共有 MySQL が healthy でなければ「一部停止」
- 同じサイトへの操作は 1 つずつしか実行しない。実行中の行は「処理中」になる
- 操作の結果は画面の上部と操作履歴（`site-start` / `site-stop`、出どころ `dashboard`）に残る
- ボタンは CSRF トークン付きの POST でだけ動く。LAN に公開している間も使える

### 以前の環境からの移行

- この機能を入れる前に構築した環境では、`uv run manage.py devenv migrate` を実行する（dev-env:migration 2。hosts にドメインを加えるため sudo のパスワードを求められ、pull 後の自動移行では実行されない）
- Django 版への切り替え（dev-env:migration 3）と操作履歴（4）は、`git pull` の後に自動で適用される
- ホストへの移行（dev-env:migration 5）も `git pull` の後に自動で適用される。旧ダッシュボードのコンテナ `wp-dashboard`・イメージ・ボリューム `wp-dashboard-data` を削除し、ボリュームの操作履歴は `.local/db.sqlite3` に写す。プロキシが起動中なら新しい転送先で作り直す

## 操作履歴

`devenv install`・`devenv migrate`・`devenv check-health` の結果と、ダッシュボードと `serve` によるサイトの起動・停止（出どころ `dashboard` / `serve`）は、ダッシュボードのサイト一覧の下に新しい順で 20 件表示される（DB には最大 1000 件を残す）。

- CLI もダッシュボードも、`.local/db.sqlite3` に直接書き込む。ダッシュボードを起動していなくても記録される
- 書き込めないときは `警告: 操作履歴を記録できませんでした` を表示するだけで、コマンドの結果と終了コードは変わらない
- 記録しないもの: `--dry-run` の実行、何も適用しなかった `devenv migrate`、`devenv uninstall`（最後に DB ごと消えるため）、`serve` の実行そのもの
- 以前使っていた操作履歴の API（`/api/operations`）とトークン `DASHBOARD_API_TOKEN` は廃止した。`.env` に残っていても使われない

## 公開範囲（PROXY_BIND_ADDRESS）

Caddy の 80/443 は、既定で `127.0.0.1` にだけ公開する。実機のスマートフォンなど、LAN の他の端末から開くときだけ全インターフェースに公開する。

```bash
PROXY_BIND_ADDRESS=0.0.0.0 docker compose up -d   # その場だけ公開する
echo 'PROXY_BIND_ADDRESS=0.0.0.0' >> .env         # 常に公開する（実行時の指定が .env より優先される）
```

`0.0.0.0` にすると、同じ LAN の端末からダッシュボードの管理者パスワードも見え、サイトの起動・停止もできるようになる。信頼できないネットワークでは使わない。

## 環境バージョンと移行

wp-main の更新には、pull するだけでは反映されない変更（ボリューム名の変更、`.env` への変数の追加など）がある。これを migration として配り、環境バージョンで適用状況を管理する。

migration は 2 種類あり、呼び分ける。この節の migration は dev-env:migration を指す。

| 呼び方 | 対象 | 置き場所 | 実行 | 記録先 |
| --- | --- | --- | --- | --- |
| dev-env:migration | 開発環境のリソース（hosts、ボリューム、`.env` など） | `src/wp_main/devenv/migrations/` | `uv run manage.py devenv migrate` | `.local/dev-env-state.json` |
| django:migration | Django の DB スキーマ | 各 Django app の `migrations/` | `serve`・`devenv install`・操作履歴の記録の前に自動 | `.local/db.sqlite3` |

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
- 開発セッションの外でサイトを起動したままにしない。プロキシを作り直すときは `_env.rebuild_if_running()`（Caddy だけを作り直す）を使う
- 後戻り（down）は用意しない。困ったときは uninstall してから install し直す

## 共有 MySQL

全サイトが 1 台の MySQL 8.0（コンテナ `wp-mysql`、ボリューム `wp-mysql-data`）を共用し、サイトごとに schema を分ける。

- schema 名はサイトの `.env` の `WP_DB_NAME`（未設定ならサイト ID。`wp1`・`wp2`）。サイトを起動するときに、なければ作る
- DB のユーザーは全サイトで 1 つ（wp-main の `.env` の `DB_USER`）。どのサイトからも他のサイトの schema を読み書きできる（[ADR 0001](docs/adr/0001-main-controller-and-shared-mysql.md)）
- ホストの `127.0.0.1:3306` に公開する（wp-main の `.env` の `MYSQL_PORT` で変更できる）。TablePlus などで `DB_USER` / `DB_PASSWORD` で接続できる
- サイト設定の変数（`WP_IMAGE`・`WP_HOME` など）を wp-main の `.env` に書かない。wp-main の `.env` の値がサイトの `.env` より優先されるため、全サイトに効いてしまう

### サイトごとの DB からの移行（dev-env:migration 6）

以前はサイトごとに MySQL（`wp1-db` / `wp2-db`、ボリューム `wp1-db-data` / `wp2-db-data`）を持っていた。migration 6 は `git pull` の後に自動で適用され、次を行う。

1. wp-main の `.env` に `DB_USER`・`DB_PASSWORD`・`DB_ROOT_PASSWORD` を加える（既にあれば変えない）
2. 旧構成のコンテナ（`wpN-wordpress`・`wpN-db`）を削除し、共有インフラを起動する
3. サイトごとに、旧ボリュームを一時コンテナで起動して `mysqldump` し、共有 MySQL の schema に取り込む
4. テーブルの一覧と各テーブルの行数が一致したときだけ、旧ボリュームを削除する。一致しない、または写し先に既にテーブルがあるときは、旧ボリュームを残して失敗する

旧ボリュームは削除されると戻せない。移行前に残しておきたい場合は、pull の前に次で保存する（wp2 も同じ）。

```bash
docker run --rm -v wp1-db-data:/data -v "$PWD":/out alpine tar czf /out/wp1-db-data.tgz -C /data .
```

wp-main と wp-wp1 / wp-wp2 を更新するときは、wp-main を先に pull する。サイトのリポジトリだけを先に更新すると、古い wp-main がサイトの `docker-compose.yml` を見失って起動できない。

## 日常の操作（wp-main で実行）

```bash
uv run manage.py serve up --site=wp1 -d   # 開発を始める（終えるときは serve down）
docker compose ps
uv run manage.py serve logs -f caddy mysql wp1
docker compose run --rm wp1-cli wp plugin list   # WP-CLI（サイトの起動中に）
```

サイトのディレクトリでは `docker compose` を使わない（コンテナの定義は wp-main にある）。デバッグ用ポートで直接確認する場合:

```bash
# デバッグ用ポートはホスト名とポートが WP_HOME と違うため、そのままだと WordPress がポートを外した URL へ 301 を返す
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: local.wp2.yamashita109.com' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8082/   # 200 なら正常
```

## 検証

```bash
uv run manage.py devenv check-health          # 各項目を OK / WARN / FAIL / SKIP で表示
uv run manage.py devenv check-health --json   # 機械向け（CI やスクリプトから使う）
```

sudo は使わず、環境も変更しない。確認する項目は次のとおり。

| グループ | 項目 |
| --- | --- |
| 構成 | サイトリポジトリの origin、各 `.env` の有無と `change-me` の残り |
| ホスト | 各サイトとダッシュボードのドメインの名前解決（127.0.0.1）、`wp-global-net`、Caddy の CA がキーチェーンに登録されているか、`serve` のダッシュボードが応答するか（しなければ開発セッションの外として SKIP） |
| 共有インフラ | Caddy と共有 MySQL が running か（MySQL は healthy か） |
| サイト | 各サイトの WordPress が running か（止まっていれば停止中として SKIP） |
| HTTP と WordPress | 起動中の各サイトとダッシュボードの HTTPS の応答と証明書の検証、HTTP から HTTPS へのリダイレクト、WordPress がインストール済みか、メジャーバージョン（サイトの `.env` の `WP_IMAGE` と比べる） |

- 前提の項目が FAIL か SKIP なら、その項目は SKIP になる（例: Caddy が止まっていれば HTTP の項目はすべて SKIP、止まっているサイトの HTTP の項目も SKIP）。開発セッションの外で実行しても、壊れているものだけが FAIL / WARN になる。WARN と FAIL には対処方法が表示される。
- FAIL が 1 つでもあれば終了コード 1、WARN だけなら 0。
- 管理画面へのログインは確認しない。ブラウザで `/wp-admin/` にログインし、リダイレクトがループしないことを確認する。

## 開発

```bash
uv run pytest
DJANGO_DEBUG=1 uv run manage.py runserver 127.0.0.1:8000   # 自動リロード付きでダッシュボードだけを起動（serve の代わり。サイトは起動しない）
```

### ダッシュボードの見た目（bun・Vite・Tailwind CSS）

CSS と JS のソースは `src/wp_main/dashboard/frontend/` にあり、bun・Vite・Tailwind CSS v4 でビルドして `src/wp_main/dashboard/static/dist/` に出力する。出力は git に入れているので、ダッシュボードを使うだけなら bun は要らない。見た目を変えるときだけ次を使う（bun の版は `.prototools` で固定している）。

```bash
bun install
bun run dev        # ソースの変更を監視してビルドし直す（ブラウザは手で再読み込み）
bun run build      # 出力を作り直す。変えたら static/dist/ もコミットする
bun run test:e2e   # Bun.WebView による e2e テスト（一時ディレクトリの .env と DB で runserver を起動する）
```

ソースと出力がずれていると、bun がある環境では `tests/test_frontend_build.py` が失敗する。

ダッシュボードと CLI は 1 つの Django プロジェクト（`manage.py`、`src/wp_main/settings.py`）にまとめている。ダッシュボードは app `wp_main.dashboard`（API は Django Ninja）、CLI は app `wp_main.cli` の management command。

DB は SQLite（`.local/db.sqlite3`、git の管理外）。ダッシュボードと CLI はどちらもホストで動き、同じファイルを直接読み書きする（WAL モード）。django:migration は `serve`・`devenv install`・操作履歴の記録の前に自動で適用されるので、手で `uv run manage.py migrate` を実行する必要はない。

サイトの雛形は `templates/wp-site/` にある（`{{SITE_ID}}` などをサイトごとに置換する。コンテナの定義は含まない）。サイトを増やすときは、`config.py` の `SITES`・`compose/<サイト ID>.yml`・`docker-compose.yml` の `include` の 3 か所に加える（食い違いは `tests/test_compose.py` が検出する）。雛形は空のリモートを初期化するときだけ使う。初期化した後は、各サイトリポジトリ側を直接編集する。
