## MODIFIED Requirements

### Requirement: CLI エントリポイント
wp-main ディレクトリで `uv run manage.py devenv <command>` を実行したとき、CLI は `install`、`uninstall`、`check-health`、`migrate`、`serve`、`version` の各サブコマンドを受け付けなければならない (MUST)。`uv run manage.py help devenv` はサブコマンドの一覧を表示しなければならない (MUST)。旧来の `uv run cli` は、どの引数で実行されても何も変更せず、対応する新しいコマンドを表示して 0 以外の終了コードで終了しなければならない (MUST)。

#### Scenario: help を表示する
- **WHEN** ユーザーが `uv run manage.py help devenv` を実行する
- **THEN** `serve` を含む利用可能なサブコマンドの一覧と各サブコマンドの説明が表示され、終了コード 0 で終了する

#### Scenario: 旧来のコマンド
- **WHEN** ユーザーが `uv run cli dev-env:check-health` を実行する
- **THEN** 確認は実行されず、`uv run manage.py devenv check-health` を使うよう表示され、0 以外の終了コードで終了する

#### Scenario: version を表示する
- **WHEN** ユーザーが `uv run manage.py devenv version` を実行する
- **THEN** wp-main パッケージのバージョン文字列が 1 行で表示され、終了コード 0 で終了する

#### Scenario: 未知のコマンド
- **WHEN** ユーザーが存在しないコマンドを指定する
- **THEN** エラーメッセージが表示され、0 以外の終了コードで終了する

### Requirement: 環境の起動と CA の信頼登録
`devenv install` は、django:migration を適用して `.local/db.sqlite3` を最新のスキーマにしなければならない (MUST)。`--no-start` が指定されない限り、wp-main で全サービスを起動しなければならない (MUST)。起動後、`--skip-trust` が指定されない限り Caddy の内部 CA ルート証明書を macOS System キーチェーンに信頼済みとして登録し、登録した証明書の識別子を記録しなければならない (MUST)。最後に、ダッシュボードを起動するコマンド `uv run manage.py devenv serve` を表示しなければならない (MUST)。

#### Scenario: 起動と信頼登録
- **WHEN** オプションなしで install を実行する
- **THEN** 全コンテナが起動し、Caddy のルート証明書が System キーチェーンに信頼済みで登録され、`uv run manage.py devenv serve` の実行方法が表示される

#### Scenario: 信頼登録を省略する
- **WHEN** `--skip-trust` を付けて install を実行する
- **THEN** キーチェーンは変更されず、手動で信頼登録する手順が表示される

#### Scenario: DB を準備する
- **WHEN** `.local/db.sqlite3` がない状態で install を実行する
- **THEN** `.local/db.sqlite3` が最新のスキーマで作られる

### Requirement: 環境の破棄
`devenv uninstall` は、確認プロンプトで承認された場合、または `--yes` が指定された場合にのみ削除を実行しなければならない (MUST)。削除対象は、全コンテナ、install 由来のボリュームとイメージ（旧ダッシュボードのコンテナ・イメージ・ボリュームが残っていればそれも含む）、`wp-global-net`、hosts のマーカーブロック、記録済みの信頼済み CA 証明書、`.local/db.sqlite3`、`{root}/wp-wp1`、`{root}/wp-wp2` とする。`/etc/hosts` のバックアップは復旧用に残し、削除方法を表示しなければならない (MUST)。サイトディレクトリに未コミットまたは未 push の変更がある場合、CLI は確認プロンプトの前に警告を表示しなければならない (MUST)。`devenv serve` が動いている場合は、それを止めるよう表示しなければならない (MUST)。

#### Scenario: 確認を拒否する
- **WHEN** uninstall の確認プロンプトで `N` を入力する
- **THEN** 何も削除されずに終了する

#### Scenario: 未 push の変更を警告する
- **WHEN** `{root}/wp-wp1` に未 push のコミットがある状態で uninstall を実行する
- **THEN** 確認プロンプトの前に、変更が失われる旨の警告が表示される

#### Scenario: 完全な後片付け
- **WHEN** `--yes` を付けて uninstall を実行する
- **THEN** `{root}/wp-wp1` と `{root}/wp-wp2` が削除され、`wp-global-net`・関連ボリューム・hosts ブロック・信頼済み CA・`.local/db.sqlite3` が残らない

#### Scenario: hosts のバックアップは残して案内する
- **WHEN** `/etc/hosts.wp-dev-env.bak` がある状態で uninstall を実行する
- **THEN** バックアップは削除されず、最後に `sudo rm /etc/hosts.wp-dev-env.bak` による削除方法が表示される

#### Scenario: 部分的な状態でも完了する
- **WHEN** 一部のリソースが既に存在しない状態で uninstall を実行する
- **THEN** 存在しないリソースはスキップされ、残りのリソースの削除は続行される
