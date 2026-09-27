## Context

動機は proposal.md、判断の経緯は `docs/adr/0001-main-controller-and-shared-mysql.md`、用語は `CONTEXT.md` を参照。

現状の前提:
- wp-main の `docker-compose.yml` は `../wp-wp1/docker-compose.yml`・`../wp-wp2/docker-compose.yml` を `include` し、各サイトの `.env` はサイトのディレクトリから読まれる。
- サイトの compose は `wpN-db`（MySQL 8.0、ボリューム `wpN-db-data`）・`wpN-wordpress`・`wpN-cli`（profile `cli`）を持ち、すべて `restart: unless-stopped`。
- 両サイトの `.env` は `MYSQL_DATABASE=wordpress`・`MYSQL_USER=wordpress`・サイトごとのランダムなパスワードを持つ。
- `devenv serve` は `cli/management/commands/devenv.py` の typer サブコマンドで、`processes.supervise()` にホストのプロセスを渡す。
- `rebuild_if_running()`（migration 用）と `devenv install` は `compose up -d --wait` で全サービスを起動する。
- `dashboard/power.py` は `docker inspect` の `com.docker.compose.project` ラベルで単体起動を判定し、`<site>-wordpress` と `<site>-db` を操作する。

## Goals / Non-Goals

**Goals:**
- サイトの追加が「サイトのリポジトリ」「`SITES` への 1 行」「compose のサイト定義ファイル 1 つ」で済む形にする。
- 開発セッションの外でサイトが勝手に動かない状態を、install・migration・Docker Desktop の再起動のどれを経ても保つ。

**Non-Goals:**
- サイトに付属するホスト側のプロセス（vite など）。
- `--root` で wp-main の親以外にサイトを置く構成を compose で扱うこと（compose の相対パスは今と同じく `../wp-wpN` 固定）。
- MySQL のバージョンを上げること。

## Decisions

### 1. サイトの定義は wp-main の `compose/<site>.yml` に分け、`include` の `env_file` でサイトの `.env` を渡す
wp-main の `docker-compose.yml` は Caddy・共有 MySQL・ネットワーク・ボリュームを持ち、サイトは次のように取り込む。

```yaml
include:
  - path: compose/wp1.yml
    project_directory: ../wp-wp1
    env_file:
      - "${WP1_ENV_FILE:-../wp-wp1/.env}"
```

`compose/wp1.yml` は `wp1-wordpress` と `wp1-cli` を手書きで定義し、`${WP_IMAGE}` などはサイトの `.env`、`${DB_USER}` などは wp-main の `.env`（プロジェクトの `.env` として自動で読まれる）から補間される。`project_directory` をサイトのディレクトリにすることで、`./wp-content` などの相対パスは今のサイトの compose と同じ書き方のまま使える。

- 代替案: 1 つの `docker-compose.yml` に全サイトを書く。サービスごとに補間元の `.env` を変えられないため、`${WP1_IMAGE}` のようにサイト接頭辞付きの変数を wp-main の `.env` に写す必要があり、「サイト設定の正本はサイトの `.env`」に反する。
- 代替案: `SITES` から生成する。grilling で不採用（Q12）。

### 2. 共有 DB の変数名は `DB_*` にする（`MYSQL_*` を使わない）
既存のサイトの `.env` には `MYSQL_USER`・`MYSQL_PASSWORD` が残っている（migration はサイトのファイルを変えられない）。wp-main の `.env` が優先されるため実害は出にくいが、同じ名前が 2 か所にあると読み手がどちらの値か迷う。wp-main 側を `DB_USER`・`DB_PASSWORD`・`DB_ROOT_PASSWORD` にすれば、名前が重ならない。MySQL コンテナの環境変数（`MYSQL_ROOT_PASSWORD` など）へは compose の中で写す。

### 3. schema と権限はサイトを起動する直前に用意する
共有 MySQL の初期化（`MYSQL_DATABASE`）では 1 つの schema しか作れず、サイトを追加するたびにボリュームを作り直すことになる。そこで、サイトを起動する処理（serve・ダッシュボード・install が共通で使う `sites.start`）が、`docker exec wp-mysql mysql -uroot` で `CREATE DATABASE IF NOT EXISTS` と `GRANT ALL ON \`<schema>\`.* TO <DB_USER>` を実行してから `compose up -d --wait <site>-wordpress` する。root のパスワードはコマンドラインに出さず、環境変数 `MYSQL_PWD` で渡す。

### 4. 起動・停止の処理を `power.py` からサイトの操作として切り出し、serve・ダッシュボード・install で共有する
- 起動: schema の用意 → `compose up -d --wait --wait-timeout 120 <site>-wordpress`（`depends_on: condition: service_healthy` で共有 MySQL も起動する）
- 停止: `compose stop <site>-wordpress`（共有 MySQL は止めない）
- 状態: `<site>-wordpress` と `wp-mysql` の `docker inspect` から求める。単体起動の判定（project ラベル）はなくす
- 共有インフラの起動: `compose up -d --wait caddy mysql`
- 起動中のサイトの一覧: `compose ps --status running --format json` から `-wordpress` のサービスを拾う

操作のロック（`site_lock`）は今のまま使い、serve の開始・終了とダッシュボードの操作が同じサイトで重ならないようにする。

### 5. `serve` は独立した管理コマンドにし、開発セッションの前後処理を `supervise` の外に置く
`cli/management/commands/serve.py` を追加し、次の順で動く。
1. `--site` の解決（不正なら何もしない）→ ポートの確認 → django:migration
2. 共有インフラの起動（失敗したら終了）
3. 指定したサイトを順に起動（失敗は表示と履歴だけ）
4. `processes.supervise()`
5. `finally` で、起動中のサイトをすべて停止し、履歴を記録する

`supervise()` の中でコンテナを扱わないのは、ホストのプロセスの監視（シグナル・出力の中継）と Docker の操作を混ぜると、テストでどちらかだけを差し替えられなくなるため。終了時の停止は `supervise()` が返った後に行うので、Ctrl-C でもプロセスの異常終了でも同じ経路を通る。停止中にもう一度 Ctrl-C が来た場合は、停止を中断して終了する（残ったサイトは次のセッションで扱える）。

`devenv serve` は残し、何もせずに `uv run manage.py serve` を案内して終了コード 1 を返す。

### 6. 「セッションの外でサイトを起動したままにしない」を install と migration で守る
- `devenv install` は `compose up -d --wait caddy mysql` → 各サイトを起動 → `wp core install` → 各サイトを停止。
- `rebuild_if_running()` は、Caddy が起動している場合に `compose up -d --wait caddy` だけを行い、サイトは起動しない。migration 2〜5 は `DB_*` を用意する migration 6 より前に走るため、共有 MySQL はここでは起動しない（`DB_ROOT_PASSWORD` が空のまま MySQL を初期化させない）。migration 2 も同じ関数を使う。

### 7. migration 6 は「旧 DB を一時コンテナで起動 → dump → import → 確認 → 削除」
サイトごとに次を行う（`wpN-db-data` がなければ何もしない）。
1. 旧コンテナ（`wpN-db`・`wpN-wordpress`）があれば停止・削除する（ボリュームは残す）。
2. `docker run -d --name wpN-db-migrate -v wpN-db-data:/var/lib/mysql -e MYSQL_ROOT_PASSWORD=<サイトの .env の値> mysql:8.0` で旧 DB を起動し、`mysqladmin ping` で待つ。
3. 写し先の schema にテーブルがあれば失敗させる。なければ schema を作る。
4. `mysqldump --single-transaction --routines --triggers <旧 MYSQL_DATABASE>` を `mysql <schema>` に流す（ホストのパイプでつなぐ）。
5. 両方の `information_schema.tables` からテーブル名の一覧を、各テーブルで `SELECT COUNT(*)` を取り、比べる。
6. 一致したら一時コンテナと `wpN-db-data` を削除する。一致しなければ一時コンテナだけを削除して失敗させる。

その前に `add_secret` で `DB_USER`（固定値 `wordpress`）・`DB_PASSWORD`・`DB_ROOT_PASSWORD` を wp-main の `.env` に加え、`compose up -d --wait caddy mysql` で共有インフラを起動する。最後に、Caddy を新しい compose 定義で作り直した状態にし、サイトは停止のままにする。

- 代替案: 旧ボリュームのデータディレクトリを共有 MySQL にそのまま使う。schema 名が両方 `wordpress` で衝突し、2 つのデータディレクトリは 1 つにまとめられないため不採用。

### 8. 定義の漏れはテストで検出する
`docker compose config --format json` を使うと Docker が必要になるため、テストでは `compose/*.yml` を YAML として読み、`SITES` の各 ID について `<id>-wordpress`・`<id>-cli` があること、`docker-compose.yml` の `include` に `compose/<id>.yml` があることを確かめる。

## Risks / Trade-offs

- [`include` の `env_file` にサイトの `.env` がないと、compose のプロジェクト全体が読めなくなり、他のサイトや共有インフラも操作できない] → Compose v5.5.1 で確認した結果、ファイルがないと `stat ... no such file or directory` で全体が失敗し、`required: false` は `include` の `env_file` では受け付けられない（decoding エラー）。一方、パスには補間が効く。そこで `env_file: ["${WP1_ENV_FILE:-../wp-wp1/.env}"]` とし、wp-main のツールは `.env` のないサイトについて `WPN_ENV_FILE=/dev/null` を渡して compose を呼ぶ。そのサイトは起動の前に `.env` の有無で失敗させる。`/dev/null` のときもプロジェクトが読めるよう、イメージは `${WP_IMAGE:-wordpress:apache}` のように既定値を持たせる。
- [補間の優先順位] → 確認した結果、wp-main の `.env` の値は `include` の `env_file` より常に優先される（順序によらない）。サイトの `.env` の値が効くのは、wp-main の `.env` とシェルの環境変数にない名前だけなので、サイト設定の変数名（`WP_IMAGE`・`WP_HOME` など）を wp-main の `.env` に置いてはならない。
- [migration 6 が `git pull` の後に自動で走り、数十秒かかる] → sudo も破壊的な操作もないので `--auto` の条件は満たす。進み具合をサイトごとに表示する。
- [旧 DB の中の `siteurl`・`home` はそのまま] → schema 名が変わるだけで URL は変わらないため、書き換えは不要。
- [serve が SIGKILL などで落ちると、サイトが動いたまま残る] → 次の `serve` がそのまま引き継ぎ、終了時に止める。`check-health` は起動中のサイトとして普通に確認する。
- [サイト同士が DB 上で分離されない] → ADR 0001 で受け入れた。

## Migration Plan

1. wp-main の PR をマージし、`git pull` で migration 6 を適用する（自動）。
2. wp-wp1・wp-wp2 の PR（compose の削除、`.env.example` と README の更新）をマージする。順序が逆だと、古い wp-main が `include` 先の compose を見失う。
3. 利用者は `uv run manage.py serve --site=all` で開発を始める。

戻すとき: migration 6 は旧ボリュームを削除するため、戻すには共有 MySQL から `mysqldump` で書き出して旧構成に取り込む必要がある。移行前に残したい場合は、`docker run --rm -v wpN-db-data:/data -v "$PWD":/out alpine tar czf /out/wpN-db-data.tgz -C /data .` でボリュームを保存しておく（README に書く）。
