# dev-host-processes Specification

## Purpose
開発セッション（`serve` の開始から終了まで）を定める。ダッシュボードや将来の vite などのホストのプロセスと、共有インフラ・指定したサイトを 1 つのコマンドでまとめて起動し、終了時にサイトを止める。

## Requirements

### Requirement: devenv serve によるまとめての起動
`uv run manage.py serve` は、wp-main が定義するホストのプロセスの一覧をすべて起動し、前面で動き続けなければならない (MUST)。この変更の時点で、一覧はダッシュボードだけとする。各プロセスの出力は、プロセス名を行頭に付けて端末に表示しなければならない (MUST)。Ctrl-C（SIGINT）または SIGTERM を受け取ったときは、すべてのプロセスを止めてから終了コード 0 で終わらなければならない (MUST)。いずれかのプロセスが予期せず終了した場合は、残りのプロセスを止め、終了したプロセスの名前と終了コードを表示し、0 以外の終了コードで終わらなければならない (MUST)。プロセスの一覧は、既存のプロセスの動作を変えずに項目を加えられる形でなければならない (MUST)。`uv run manage.py devenv serve` は何も起動せずに、`uv run manage.py serve` を使うよう表示して 0 以外の終了コードで終わらなければならない (MUST)。

#### Scenario: 起動して止める
- **WHEN** `uv run manage.py serve` を実行し、ダッシュボードが応答するようになってから Ctrl-C を押す
- **THEN** ダッシュボードのプロセスが止まり、`serve` は終了コード 0 で終わる

#### Scenario: プロセスが落ちる
- **WHEN** `serve` の実行中にダッシュボードのプロセスが異常終了する
- **THEN** 残りのプロセスが止められ、`dashboard` と終了コードが表示され、`serve` は 0 以外の終了コードで終わる

#### Scenario: 出力の区別
- **WHEN** `serve` の実行中にダッシュボードへリクエストする
- **THEN** アクセスログの行が `dashboard` の接頭辞付きで表示される

#### Scenario: 旧コマンド
- **WHEN** `uv run manage.py devenv serve` を実行する
- **THEN** 何も起動されず、`uv run manage.py serve` を使うよう表示され、0 以外の終了コードで終わる

### Requirement: 待ち受けるアドレスとポート
ダッシュボードは `127.0.0.1` だけで待ち受けなければならない (MUST)。ポートは既定で 8000 とし、wp-main の `.env` の `DASHBOARD_PORT` で変えられなければならない (MUST)。ポートが既に使われている場合、`serve` は共有インフラ・サイト・プロセスのいずれも起動せずに、使用中のポートと変更の方法を表示し、0 以外の終了コードで終わらなければならない (MUST)。

#### Scenario: ループバックだけで待ち受ける
- **WHEN** `serve` を実行する
- **THEN** `127.0.0.1:8000` には接続でき、ホストの LAN 側のアドレスの 8000 番には接続できない

#### Scenario: ポートが使用中
- **WHEN** 8000 番を別のプロセスが使っている状態で `serve --site=wp1` を実行する
- **THEN** 何も起動されず、8000 番が使用中であることと `DASHBOARD_PORT` で変更できることが表示され、0 以外の終了コードで終わる

### Requirement: 起動前の DB の準備
`serve` は、プロセスを起動する前に django:migration を適用しなければならない (MUST)。適用に失敗した場合は、共有インフラ・サイト・プロセスのいずれも起動せずに原因を表示し、0 以外の終了コードで終わらなければならない (MUST)。

#### Scenario: 未適用のスキーマ
- **WHEN** `.local/db.sqlite3` がない状態で `serve` を実行する
- **THEN** `.local/db.sqlite3` が作られて最新のスキーマになり、その後にダッシュボードが起動する

### Requirement: 開発セッションで起動するサイトの指定
`serve` は `--site` で起動するサイトを受け付けなければならない (MUST)。値はカンマ区切りのサイト ID、または全サイトを表す `all` としなければならない (MUST)。`--site` を省いた場合は、サイトを起動してはならない (MUST NOT)。存在しないサイト ID が含まれる場合は、何も起動せずに、指定できるサイト ID の一覧を表示し、0 以外の終了コードで終わらなければならない (MUST)。

#### Scenario: サイトを指定する
- **WHEN** 全サイトが停止している状態で `uv run manage.py serve --site=wp1` を実行する
- **THEN** 共有インフラと wp1 とダッシュボードが起動し、wp2 は停止したままになる

#### Scenario: 全サイト
- **WHEN** `uv run manage.py serve --site=all` を実行する
- **THEN** wp1 と wp2 が起動する

#### Scenario: 指定しない
- **WHEN** `uv run manage.py serve` を実行する
- **THEN** 共有インフラとダッシュボードが起動し、サイトは起動しない

#### Scenario: 存在しないサイト
- **WHEN** `uv run manage.py serve --site=wp1,wp3` を実行する
- **THEN** 何も起動されず、`wp3` が存在しないことと、指定できる `wp1`・`wp2`・`all` が表示され、0 以外の終了コードで終わる

### Requirement: 開発セッションの開始と終了
`serve` は、ホストのプロセスを起動する前に、共有インフラ（プロキシと共有 MySQL）を起動し、共有 MySQL が healthy になるまで待たなければならない (MUST)。共有インフラを起動できない場合は、サイトとホストのプロセスを起動せずに原因を表示し、0 以外の終了コードで終わらなければならない (MUST)。続いて `--site` で指定したサイトを起動しなければならない (MUST)。サイトの起動に失敗した場合は、失敗したサイトと原因を表示し、残りのサイトとホストのプロセスの起動を続けなければならない (MUST)。`serve` が終わるとき（Ctrl-C、SIGTERM、ホストのプロセスが落ちたとき）は、その時点で起動しているサイトを、`--site` で指定したかどうかにかかわらずすべて停止しなければならない (MUST)。共有インフラは停止してはならない (MUST NOT)。

#### Scenario: 終了するとサイトを止める
- **WHEN** `serve --site=wp1` の実行中にダッシュボードから wp2 を起動し、その後 Ctrl-C を押す
- **THEN** `wp1-wordpress` と `wp2-wordpress` が停止し、`wp-caddy` と `wp-mysql` は起動したままになり、`serve` は終了コード 0 で終わる

#### Scenario: サイトの起動に失敗する
- **WHEN** wp1 の `.env` がない状態で `serve --site=wp1,wp2` を実行する
- **THEN** wp1 の起動に失敗したことと原因が表示され、wp2 とダッシュボードは起動し、`serve` は動き続ける

#### Scenario: 共有インフラを起動できない
- **WHEN** Docker Desktop が停止している状態で `serve --site=wp1` を実行する
- **THEN** ダッシュボードは起動されず、Docker に接続できないことが表示され、0 以外の終了コードで終わる
