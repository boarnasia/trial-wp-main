## Why

wp-main からサイトの起動・停止ができるようになったが、構成は「各サイトが自分の MySQL と compose を持ち、単体起動もできる」前提のままで、起動方法ごとの分岐（単体起動と一括起動の判定、DB の二重化）が残っている。wp-main をメインコントローラーとして一本化し、開発を始めるときに必要なサイトだけを 1 コマンドで起動・終了できるようにする。判断の経緯は `docs/adr/0001-main-controller-and-shared-mysql.md`、用語は `CONTEXT.md` にまとめた。

## What Changes

- **BREAKING** サイトの単体起動を廃止する。サイトのコンテナ定義はすべて wp-main が持ち、サイトのリポジトリはサイトの中身とサイト設定（`.env`）だけを持つ。wp-wp1・wp-wp2 のリポジトリから `docker-compose.yml`、`.env.example` の DB の項目、README の単体起動の節を削除する（各リポジトリで別の PR にする）。
- **BREAKING** MySQL を共有インフラとして 1 台だけ動かす。サイトごとに schema を分け（既定はサイト ID）、DB ユーザーは 1 つを共用する。接続情報は wp-main の `.env` に置く。ホストの `127.0.0.1:${MYSQL_PORT:-3306}` に公開する。
- **BREAKING** `uv run manage.py devenv serve` を `uv run manage.py serve [--site=wp1,wp2|all]` に移す。serve の開始から終了までを開発セッションとし、開始時に共有インフラと指定したサイトを起動し、終了時に動いているサイトをすべて止める（共有インフラは残す）。`devenv serve` は何も起動せずに新しいコマンドを案内する。
- 共有インフラが起動できなければ serve は失敗する。サイトの起動に失敗した場合は報告だけして続ける。
- サイトの `restart: unless-stopped` を外し、サイトは開発セッションの外では動いていないのを正常とする。`devenv install` と dev-env:migration は、必要なときだけサイトを起動し、終わったら止める。
- `devenv check-health` は、停止中のサイトの項目と、セッションの外でのダッシュボードの項目を SKIP にする。共有 MySQL を確認項目に加える。
- ダッシュボードのサイトの起動・停止は、共有 MySQL を止めずに WordPress だけを止める。単体起動の判定をなくす。
- dev-env:migration 6 で、`wp1-db-data`・`wp2-db-data` のデータを共有 MySQL の schema に移し、確認してから旧ボリュームを削除する。確認に失敗した場合は旧ボリュームを残して失敗する。
- サイトテンプレート（`templates/wp-site`）から compose と DB の項目を削除する。

## Capabilities

### New Capabilities
- `dev-shared-db`: 共有 MySQL（1 台、サイトごとの schema、共用ユーザー、ホストへの公開、schema の用意）と、サイトごとの DB から移す dev-env:migration 6。

### Modified Capabilities
- `wp-site-stack`: サイトのリポジトリが持つもの（中身とサイト設定だけ）に変え、専用スタックと単体起動の要件を削除する。WordPress のコンテナ定義を wp-main 側の要件にする。
- `proxy-gateway`: 一括起動の対象を「プロキシ・共有 MySQL・各サイトの WordPress」に変え、サイトごとの DB をなくす。
- `dev-host-processes`: `serve` への移動、`--site`、開発セッションの開始と終了、共有インフラとサイトの起動の失敗時の扱い。
- `dev-site-power`: 状態の判定と停止の対象を WordPress コンテナにし、単体起動の扱いを削除する。
- `dev-env-cli`: コマンドの一覧（`serve` をトップレベルへ）、サイトテンプレートの中身、install の起動の扱い、uninstall の削除対象。
- `dev-env-health`: 共有 MySQL の項目、停止中のサイトとセッション外のダッシュボードの SKIP、期待する WordPress のバージョンの出どころ。
- `dev-env-versioning`: django:migration を適用するタイミングの `devenv serve` を `serve` に読み替える。
- `dev-operation-history`: serve によるサイトの起動・停止も `site-start`・`site-stop` として記録する。
- `dev-dashboard`: migration 5 の最後に案内するコマンドを `serve` にする。

## Impact

- コード: `docker-compose.yml`（共有 MySQL とサイトの定義）、新しい `compose/` 配下のサイトごとの定義、`config.py`、`processes.py`、`cli/management/commands/`（`serve` の追加、`devenv serve` の案内化）、`devenv/__init__.py`（install・uninstall）、`devenv/migrations/m0006_*.py`、`dashboard/power.py`、`health.py`、`templates/wp-site/`
- 別リポジトリ: wp-wp1・wp-wp2（compose の削除、`.env.example`・README の更新）。マージは wp-main を先にする
- Docker リソース: 新しいコンテナ `wp-mysql` とボリューム `wp-mysql-data`、新しい内部ネットワーク。削除されるもの: `wp1-db`・`wp2-db` のコンテナと `wp1-db-data`・`wp2-db-data` のボリューム
- 利用者: 起動コマンドが `uv run manage.py serve --site=...` に変わる。README を更新する
