## RENAMED Requirements

- FROM: `### Requirement: devenv serve によるまとめての起動`
- TO: `### Requirement: serve up によるまとめての起動`

## MODIFIED Requirements

### Requirement: serve up によるまとめての起動
`uv run manage.py serve up` は、wp-main が定義するホストのプロセスの一覧をすべて起動しなければならない (MUST)。この変更の時点で、一覧はダッシュボードだけとする。`--detach` を付けない場合は前面で動き続け、各プロセスの出力をプロセス名を行頭に付けて端末に表示しなければならない (MUST)。前面の `serve up` が Ctrl-C（SIGINT）または SIGTERM を受け取ったときは、開発セッションを終えてから（「開発セッションの開始と終了」）終了コード 0 で終わらなければならない (MUST)。いずれかのプロセスが予期せず終了した場合は、開発セッションを終え、終了したプロセスの名前と終了コードを表示し（デタッチ中はログに書き）、前面なら 0 以外の終了コードで終わらなければならない (MUST)。プロセスの一覧は、既存のプロセスの動作を変えずに項目を加えられる形でなければならない (MUST)。サブコマンドを付けない `uv run manage.py serve` は、何も起動せずに `uv run manage.py serve up` を使うよう表示して 0 以外の終了コードで終わらなければならない (MUST)。`uv run manage.py devenv serve` は何も起動せずに、`uv run manage.py serve up` を使うよう表示して 0 以外の終了コードで終わらなければならない (MUST)。

#### Scenario: 起動して止める
- **WHEN** `uv run manage.py serve up` を実行し、ダッシュボードが応答するようになってから Ctrl-C を押す
- **THEN** ダッシュボードのプロセスが止まり、`serve up` は終了コード 0 で終わる

#### Scenario: プロセスが落ちる
- **WHEN** 前面の `serve up` の実行中にダッシュボードのプロセスが異常終了する
- **THEN** 開発セッションが終わり、`dashboard` と終了コードが表示され、`serve up` は 0 以外の終了コードで終わる

#### Scenario: 出力の区別
- **WHEN** 前面の `serve up` の実行中にダッシュボードへリクエストする
- **THEN** アクセスログの行が `dashboard` の接頭辞付きで表示される

#### Scenario: サブコマンドがない
- **WHEN** `uv run manage.py serve --site=wp1` を実行する
- **THEN** 何も起動されず、`uv run manage.py serve up --site=wp1` のように `serve up` を使うよう表示され、0 以外の終了コードで終わる

#### Scenario: 旧コマンド
- **WHEN** `uv run manage.py devenv serve` を実行する
- **THEN** 何も起動されず、`uv run manage.py serve up` を使うよう表示され、0 以外の終了コードで終わる

### Requirement: 待ち受けるアドレスとポート
ダッシュボードは `127.0.0.1` だけで待ち受けなければならない (MUST)。ポートは既定で 8000 とし、wp-main の `.env` の `DASHBOARD_PORT` で変えられなければならない (MUST)。開発セッションが動いていない状態でポートが既に使われている場合、`serve up` は共有インフラ・サイト・プロセスのいずれも起動せずに、使用中のポートと変更の方法を表示し、0 以外の終了コードで終わらなければならない (MUST)。

#### Scenario: ループバックだけで待ち受ける
- **WHEN** `serve up` を実行する
- **THEN** `127.0.0.1:8000` には接続でき、ホストの LAN 側のアドレスの 8000 番には接続できない

#### Scenario: ポートが使用中
- **WHEN** 開発セッションが動いておらず、8000 番を別のプロセスが使っている状態で `serve up --site=wp1` を実行する
- **THEN** 何も起動されず、8000 番が使用中であることと `DASHBOARD_PORT` で変更できることが表示され、0 以外の終了コードで終わる

### Requirement: 起動前の DB の準備
`serve up` は、プロセスを起動する前に django:migration を適用しなければならない (MUST)。適用に失敗した場合は、共有インフラ・サイト・プロセスのいずれも起動せずに原因を表示し、0 以外の終了コードで終わらなければならない (MUST)。

#### Scenario: 未適用のスキーマ
- **WHEN** `.local/db.sqlite3` がない状態で `serve up` を実行する
- **THEN** `.local/db.sqlite3` が作られて最新のスキーマになり、その後にダッシュボードが起動する

### Requirement: 開発セッションで起動するサイトの指定
`serve up` は `--site` で起動するサイトを受け付けなければならない (MUST)。値はカンマ区切りのサイト ID、または全サイトを表す `all` としなければならない (MUST)。`--site` を省いた場合は、サイトを起動してはならない (MUST NOT)。存在しないサイト ID が含まれる場合は、何も起動・停止せずに、指定できるサイト ID の一覧を表示し、0 以外の終了コードで終わらなければならない (MUST)。

#### Scenario: サイトを指定する
- **WHEN** 全サイトが停止している状態で `uv run manage.py serve up --site=wp1` を実行する
- **THEN** 共有インフラと wp1 とダッシュボードが起動し、wp2 は停止したままになる

#### Scenario: 全サイト
- **WHEN** `uv run manage.py serve up --site=all` を実行する
- **THEN** wp1 と wp2 が起動する

#### Scenario: 指定しない
- **WHEN** `uv run manage.py serve up` を実行する
- **THEN** 共有インフラとダッシュボードが起動し、サイトは起動しない

#### Scenario: 存在しないサイト
- **WHEN** `uv run manage.py serve up --site=wp1,wp3` を実行する
- **THEN** 何も起動されず、`wp3` が存在しないことと、指定できる `wp1`・`wp2`・`all` が表示され、0 以外の終了コードで終わる

### Requirement: 開発セッションの開始と終了
`serve up` は、ホストのプロセスを起動する前に、共有インフラ（プロキシと共有 MySQL）を起動し、共有 MySQL が healthy になるまで待たなければならない (MUST)。共有インフラを起動できない場合は、サイトとホストのプロセスを起動せずに原因を表示し、起動した共有インフラを停止し、0 以外の終了コードで終わらなければならない (MUST)。続いて `--site` で指定したサイトを起動しなければならない (MUST)。サイトの起動に失敗した場合は、失敗したサイトと原因を表示し、残りのサイトとホストのプロセスの起動を続けなければならない (MUST)。

開発セッションを終えるとき（`serve down`、前面の `serve up` の Ctrl-C・SIGTERM、ホストのプロセスの異常終了）は、ホストのプロセスを止め、その時点で起動しているサイトを `--site` で指定したかどうかにかかわらずすべて停止し、最後に共有インフラを停止しなければならない (MUST)。共有インフラのコンテナは削除してよいが、ボリュームを削除してはならない (MUST NOT)。

#### Scenario: 終了するとサイトを止める
- **WHEN** `serve up --site=wp1` の実行中にダッシュボードから wp2 を起動し、その後 Ctrl-C を押す
- **THEN** `wp1-wordpress`・`wp2-wordpress`・`wp-caddy`・`wp-mysql` が停止し、`wp-mysql-data` は残り、`serve up` は終了コード 0 で終わる

#### Scenario: サイトの起動に失敗する
- **WHEN** wp1 の `.env` がない状態で `serve up --site=wp1,wp2` を実行する
- **THEN** wp1 の起動に失敗したことと原因が表示され、wp2 とダッシュボードは起動し、開発セッションは続く

#### Scenario: 共有インフラを起動できない
- **WHEN** Docker Desktop が停止している状態で `serve up --site=wp1` を実行する
- **THEN** ダッシュボードは起動されず、Docker に接続できないことが表示され、0 以外の終了コードで終わる

#### Scenario: 次のセッションでデータが残る
- **WHEN** `serve up --site=wp1` で投稿を作り、`serve down` の後にもう一度 `serve up --site=wp1` を実行する
- **THEN** 作った投稿が表示される

## ADDED Requirements

### Requirement: デタッチ起動
`serve up --detach` は、開発セッションを端末から切り離して動かさなければならない (MUST)。共有インフラ・指定したサイト・ホストのプロセスを起動し、ダッシュボードが `127.0.0.1` の設定されたポートで応答することを確かめてから、ダッシュボードの URL を表示して終了コード 0 で戻らなければならない (MUST)。ダッシュボードが応答しないまま終了した場合、または 120 秒以内に応答しない場合は、開発セッションを終えてから（共有インフラも停止する）、原因とログの見方を表示して 0 以外の終了コードで終わらなければならない (MUST)。サイトの起動の失敗は表示するだけで、終了コード 0 で戻らなければならない (MUST)。`serve up` を実行した端末を閉じても、デタッチした開発セッションは動き続けなければならない (MUST)。

#### Scenario: デタッチして戻る
- **WHEN** `uv run manage.py serve up --detach --site=wp1` を実行する
- **THEN** ダッシュボードが応答するようになってから URL が表示されて終了コード 0 で戻り、その後も `https://local.wp1.yamashita109.com/` とダッシュボードに接続できる

#### Scenario: ダッシュボードが起動しない
- **WHEN** ダッシュボードのプロセスが起動直後に異常終了する状態で `serve up --detach` を実行する
- **THEN** `wp-caddy` と `wp-mysql` が停止し、`dashboard` の異常終了と `serve logs` での確認方法が表示され、0 以外の終了コードで終わる

#### Scenario: デタッチ中にプロセスが落ちる
- **WHEN** `serve up --detach --site=wp1` の後にダッシュボードのプロセスが異常終了する
- **THEN** 開発セッションが終わって `wp1-wordpress`・`wp-caddy`・`wp-mysql` が停止し、`serve logs` で `dashboard` の終了コードを確かめられる

### Requirement: 開発セッションの記録と二重起動
`serve up` は、前面・デタッチのいずれでも、開発セッションを監督するプロセスの PID を `.local/serve.pid` に記録し、開発セッションが終わったら削除しなければならない (MUST)。記録された PID のプロセスが存在しない場合は、開発セッションは動いていないものとして扱わなければならない (MUST)。開発セッションが動いている状態で `serve up` を実行した場合は、今の開発セッションのホストのプロセスとサイトを止めてから、新しい指定で開発セッションを始めなければならない (MUST)。この入れ替えの間、共有インフラを停止してはならない (MUST NOT)。

#### Scenario: セッションを入れ替える
- **WHEN** `serve up --detach --site=wp1` の後に `serve up --detach --site=wp2` を実行する
- **THEN** `wp1-wordpress` が停止し、`wp2-wordpress` とダッシュボードが起動し、`wp-mysql` は入れ替えの間も起動したままで、開発セッションは 1 つだけ動いている

#### Scenario: 前面のセッションを入れ替える
- **WHEN** 端末 A で前面の `serve up --site=wp1` を実行中に、端末 B で `serve up --detach --site=wp2` を実行する
- **THEN** 端末 A の `serve up` が終了し、wp2 とダッシュボードが動く開発セッションが 1 つだけ残る

#### Scenario: 古い PID ファイル
- **WHEN** 開発セッションのプロセスが強制終了され、`.local/serve.pid` だけが残っている状態で `serve up` を実行する
- **THEN** 新しい開発セッションが始まり、`.local/serve.pid` は新しいプロセスの PID に置き換わる

### Requirement: serve down による終了
`uv run manage.py serve down` は、開発セッションが動いていればそれを終えなければならない (MUST)（「開発セッションの開始と終了」の終了の手順）。前面の `serve up` のセッションも、別の端末から終えられなければならない (MUST)。開発セッションが動いていない場合でも、起動しているサイトと共有インフラを停止し、残っている `.local/serve.pid` を削除しなければならない (MUST)。停止するものが何もなければ、開発セッションがないことを表示しなければならない (MUST)。いずれの場合も、停止に成功したら終了コード 0 で終わらなければならない (MUST)。

#### Scenario: デタッチしたセッションを終える
- **WHEN** `serve up --detach --site=wp1` の後に `serve down` を実行する
- **THEN** ダッシュボード・`wp1-wordpress`・`wp-caddy`・`wp-mysql` が停止し、`.local/serve.pid` がなくなり、終了コード 0 で終わる

#### Scenario: 前面のセッションを別の端末から終える
- **WHEN** 端末 A で前面の `serve up --site=wp1` を実行中に、端末 B で `serve down` を実行する
- **THEN** 端末 A の `serve up` が終了し、wp1 と共有インフラが停止する

#### Scenario: 残ったコンテナを片付ける
- **WHEN** 開発セッションのプロセスが強制終了され、`wp1-wordpress` と共有インフラが残っている状態で `serve down` を実行する
- **THEN** `wp1-wordpress`・`wp-caddy`・`wp-mysql` が停止し、終了コード 0 で終わる

#### Scenario: 何も動いていない
- **WHEN** 何も動いていない状態で `serve down` を実行する
- **THEN** 開発セッションがないことが表示され、終了コード 0 で終わる

### Requirement: ログの保存と表示
開発セッションのホストのプロセスの出力は、前面・デタッチのいずれでも、プロセスごとに `.local/logs/<名前>.log` に書かなければならない (MUST)。`serve up` は開発セッションを始めるたびにログを新しくし、直前のログを `.local/logs/<名前>.log.1` として 1 世代だけ残さなければならない (MUST)。`uv run manage.py serve logs` は、ホストのプロセスのログと、共有インフラ・起動しているサイトのコンテナのログを、行頭に名前を付けて 1 本にまとめて表示しなければならない (MUST)。名前を引数に指定した場合は、そのログだけを表示しなければならない (MUST)。`-f` を付けた場合は、新しい行を追い続け、Ctrl-C で終わらなければならない (MUST)。`--tail N` を付けた場合は、各ログの最後の N 行から表示しなければならない (MUST)。存在しない名前を指定した場合は、指定できる名前を表示して 0 以外の終了コードで終わらなければならない (MUST)。`serve logs` は開発セッションを起動・停止してはならない (MUST NOT)。

#### Scenario: デタッチ後にログを追う
- **WHEN** `serve up --detach --site=wp1` の後に `serve logs -f` を実行し、ダッシュボードと wp1 にアクセスする
- **THEN** `dashboard` と `wp1-wordpress` の接頭辞付きのアクセスログが表示され続ける

#### Scenario: 名前で絞る
- **WHEN** 開発セッション中に `serve logs dashboard` を実行する
- **THEN** ダッシュボードのログだけが表示され、表示し終えたら終了コード 0 で終わる

#### Scenario: 前回のログ
- **WHEN** ダッシュボードの異常終了で開発セッションが終わった後に、`serve up` をもう一度実行する
- **THEN** 前回のダッシュボードの出力が `.local/logs/dashboard.log.1` に残っている

#### Scenario: 存在しない名前
- **WHEN** `serve logs wp3` を実行する
- **THEN** 指定できる名前が表示され、0 以外の終了コードで終わる
