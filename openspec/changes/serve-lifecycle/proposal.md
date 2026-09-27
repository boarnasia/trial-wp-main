## Why

`uv run manage.py serve` は前面で動き続けるため、端末を 1 つ占有し、ログを後から見返す手段もない。また、終了しても共有インフラ（caddy・mysql）が残り、止めるには `docker compose down` を別に覚える必要がある。docker compose と同じ `up` / `down` / `logs` の形にそろえ、開発セッションを端末から切り離して動かせるようにし、終了時にはセッションで動かしたものをすべて片付ける。判断の経緯は `docs/adr/0002-serve-daemonizes-itself.md`、用語は `CONTEXT.md` の「開発セッション」にまとめた。

## What Changes

- **BREAKING** `uv run manage.py serve` をサブコマンドに分ける: `serve up [--site=...] [--detach]`、`serve down`、`serve logs [-f] [--tail N] [名前...]`。サブコマンドのない `serve` は何も起動せずに `serve up` を案内し、0 以外の終了コードで終わる。`stop` は作らない。
- `serve up --detach` は、監督プロセスを端末から切り離して動かす。共有インフラ・指定したサイト・ダッシュボードの起動を確かめてから URL を表示して終了コード 0 で戻る。共有インフラかダッシュボードの起動に失敗したら、起動したものをすべて止めて 0 以外で終わる。サイトの失敗は表示して続ける。
- 開発セッションの PID を `.local/serve.pid` に記録する（前面で動かしたときも記録する）。
- **BREAKING** 開発セッションの終了（`serve down`、前面の Ctrl-C・SIGTERM、ホストのプロセスの異常終了）では、ホストのプロセスと動いているサイトに加えて、共有インフラも止める。コンテナは削除し、ボリュームは残す。
- `serve down` は、開発セッションがなくても残っているサイトと共有インフラを止め、何もなければその旨を表示して終了コード 0 で終わる。
- 開発セッションが動いているときに `serve up` を実行すると、今のセッションを終えてから新しく始める。その間、共有インフラは止めずに使い回す。
- ホストのプロセスの出力を `.local/logs/` のファイルに書く。`up` のたびに新しくし、直前の 1 世代を `*.log.1` として残す。`serve logs` は、ホストのプロセスのログと、共有インフラ・サイトのコンテナのログを、名前の接頭辞付きで 1 本にまとめて表示し、名前で絞り込める。
- **BREAKING** `devenv install` と dev-env:migration は、自分で起動した共有インフラを最後に止める（開発セッション中なら止めない）。
- `devenv check-health` は、開発セッションの外では共有インフラの項目も SKIP にする。セッションの判定は `.local/serve.pid` のプロセスが生きているかで行う。
- 案内の文言（install・migration 5 と 6・check-health・README・サイトテンプレート）を `serve up` / `serve down` に直す。

## Capabilities

### New Capabilities
（なし）

### Modified Capabilities
- `dev-host-processes`: `serve` のサブコマンド化（`up` / `down` / `logs`）、デタッチ起動、PID とログのファイル、開発セッションの終了で共有インフラも止めること、二重起動・セッションがないときの `down` の扱い。
- `dev-env-health`: 開発セッションの外では共有インフラの項目も SKIP にする。セッションの判定方法と案内の文言。
- `dev-env-cli`: コマンドの一覧（`serve up` / `down` / `logs`）、install の後に共有インフラを止めること、案内するコマンド、uninstall の案内。
- `dev-env-versioning`: dev-env:migration は開発セッションの外で共有インフラも起動したままにしない。`serve` の起動で DB を移行するタイミングを `serve up` に読み替える。
- `dev-shared-db`: migration 6 の後の状態（セッションの外なら共有インフラも停止）と案内するコマンド。
- `dev-dashboard`: migration 5 の最後に案内するコマンドを `serve up` にする。
- `proxy-gateway`: 開発セッションの外ではプロキシ自体が止まっていることを前提に、シナリオを直す。
- `dev-operation-history`: 前面の Ctrl-C だけでなく `serve down` による停止も `serve` 出どころの `site-stop` として記録する。

## Impact

- コード: `cli/management/commands/serve.py`（サブコマンド化）、`session.py`（終了で共有インフラも止める、PID の管理）、`processes.py`（デタッチ、ログファイルへの書き出し）、`power.py`（共有インフラの停止）、`health.py`（セッション判定、共有インフラの SKIP）、`devenv/__init__.py`（install の後始末、案内の文言）、`devenv/migrations/m0006_shared_mysql.py`（後始末と文言）、`m0005_host_dashboard.py`（文言）、`cli/management/commands/devenv.py`（旧 `devenv serve` の案内）
- ファイル: `.local/serve.pid`、`.local/logs/*.log`・`*.log.1`（`.local/` は既に git の対象外）
- ドキュメント: `README.md`、`templates/wp-site/README.md`。wp-wp1・wp-wp2 の README に `serve --site` の記述があれば、各リポジトリで直す
- 利用者: 起動は `uv run manage.py serve up --site=...`、終了は `serve down` または Ctrl-C に変わる。セッションの後に共有インフラが残らなくなり、次の `up` は MySQL の起動を待つ
