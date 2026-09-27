## MODIFIED Requirements

### Requirement: CLI エントリポイント
wp-main ディレクトリで `uv run manage.py devenv <command>` を実行したとき、CLI は `install`、`uninstall`、`check-health`、`migrate`、`version` の各サブコマンドを受け付けなければならない (MUST)。開発セッションは `uv run manage.py serve` で始めなければならない (MUST)。`uv run manage.py help devenv` はサブコマンドの一覧を表示しなければならない (MUST)。旧来の `uv run cli` は、どの引数で実行されても何も変更せず、対応する新しいコマンドを表示して 0 以外の終了コードで終了しなければならない (MUST)。

#### Scenario: help を表示する
- **WHEN** ユーザーが `uv run manage.py help devenv` を実行する
- **THEN** 利用可能なサブコマンドの一覧と各サブコマンドの説明が表示され、終了コード 0 で終了する

#### Scenario: 旧来のコマンド
- **WHEN** ユーザーが `uv run cli dev-env:check-health` を実行する
- **THEN** 確認は実行されず、`uv run manage.py devenv check-health` を使うよう表示され、0 以外の終了コードで終了する

#### Scenario: version を表示する
- **WHEN** ユーザーが `uv run manage.py devenv version` を実行する
- **THEN** wp-main パッケージのバージョン文字列が 1 行で表示され、終了コード 0 で終了する

#### Scenario: 未知のコマンド
- **WHEN** ユーザーが存在しないコマンドを指定する
- **THEN** エラーメッセージが表示され、0 以外の終了コードで終了する

### Requirement: サイトリポジトリの取得
`devenv install` は `{root}/wp-wp1` と `{root}/wp-wp2` を各 GitHub リモートから clone しなければならない (MUST)。clone したリポジトリが空の場合、CLI は wp-main のサイトテンプレートからファイルを生成し、ローカルに初回コミットを作成しなければならない (MUST)。サイトテンプレートはコンテナの定義を含んではならない (MUST NOT)。CLI はリモートへ push してはならない (MUST NOT)。

#### Scenario: 空リモートからの初期化
- **WHEN** リモート `trial-wp-wp1` にコミットがない状態で install を実行する
- **THEN** `{root}/wp-wp1` に `.env.example`・wp-config 追加コード・`wp-content/` が生成され、`docker-compose.yml` は生成されず、`origin` が設定された状態で初回コミットが作成される

#### Scenario: 既に clone 済み
- **WHEN** `{root}/wp-wp1` が `origin` に期待するリモートを持つ git リポジトリとして存在する
- **THEN** CLI は clone をスキップし、既存ファイルを変更しない

#### Scenario: 空ディレクトリが存在する
- **WHEN** `{root}/wp-wp2` が空のディレクトリとして存在する
- **THEN** CLI はそのディレクトリを clone 先として使う

#### Scenario: 無関係なディレクトリが存在する
- **WHEN** `{root}/wp-wp1` が空でないディレクトリとして存在し、期待するリモートを持つ git リポジトリではない
- **THEN** CLI は何も変更せずにエラーで終了し、原因のパスを表示する

### Requirement: 環境変数ファイルの生成
`devenv install` は wp-main と各サイトに `.env` が存在しない場合、`.env.example` を元に `.env` を生成しなければならない (MUST)。DB パスワードや管理者のパスワードなどの秘密値はランダム値で生成しなければならない (MUST)。既存の `.env` を上書きしてはならない (MUST NOT)。

#### Scenario: 初回生成
- **WHEN** wp-main と `{root}/wp-wp1` に `.env` が存在しない状態で install を実行する
- **THEN** 両方の `.env` が生成され、wp-main の `DB_PASSWORD` と wp1 の `WP_ADMIN_PASSWORD` は `.env.example` のプレースホルダーと異なるランダム値になる

#### Scenario: 再実行
- **WHEN** `.env` が既に存在する状態で install を再実行する
- **THEN** `.env` の内容は変わらない

### Requirement: 環境の起動と CA の信頼登録
`devenv install` は、django:migration を適用して `.local/db.sqlite3` を最新のスキーマにしなければならない (MUST)。`--no-start` が指定されない限り、共有インフラを起動し、WordPress の初期セットアップのために各サイトを起動し、初期セットアップが終わったらサイトを停止しなければならない (MUST)。共有インフラは起動したまま残さなければならない (MUST)。起動後、`--skip-trust` が指定されない限り Caddy の内部 CA ルート証明書を macOS System キーチェーンに信頼済みとして登録し、登録した証明書の識別子を記録しなければならない (MUST)。最後に、開発セッションを始めるコマンド `uv run manage.py serve --site=all` を表示しなければならない (MUST)。

#### Scenario: 起動と信頼登録
- **WHEN** オプションなしで install を実行する
- **THEN** 各サイトの WordPress の初期セットアップが済み、`wp-caddy` と `wp-mysql` は起動し、`wp1-wordpress` と `wp2-wordpress` は停止し、Caddy のルート証明書が System キーチェーンに信頼済みで登録され、`uv run manage.py serve --site=all` の実行方法が表示される

#### Scenario: 信頼登録を省略する
- **WHEN** `--skip-trust` を付けて install を実行する
- **THEN** キーチェーンは変更されず、手動で信頼登録する手順が表示される

#### Scenario: DB を準備する
- **WHEN** `.local/db.sqlite3` がない状態で install を実行する
- **THEN** `.local/db.sqlite3` が最新のスキーマで作られる

### Requirement: 環境の破棄
`devenv uninstall` は、確認プロンプトで承認された場合、または `--yes` が指定された場合にのみ削除を実行しなければならない (MUST)。削除対象は、全コンテナ、install 由来のボリュームとイメージ（共有 MySQL のボリューム、旧ダッシュボードとサイトごとの旧 DB のコンテナ・ボリュームが残っていればそれも含む）、`wp-global-net` と共有 MySQL の内部ネットワーク、hosts のマーカーブロック、記録済みの信頼済み CA 証明書、`.local/db.sqlite3`、`{root}/wp-wp1`、`{root}/wp-wp2` とする。`/etc/hosts` のバックアップは復旧用に残し、削除方法を表示しなければならない (MUST)。サイトディレクトリに未コミットまたは未 push の変更がある場合、CLI は確認プロンプトの前に警告を表示しなければならない (MUST)。`serve` が動いている場合は、それを止めるよう表示しなければならない (MUST)。

#### Scenario: 確認を拒否する
- **WHEN** uninstall の確認プロンプトで `N` を入力する
- **THEN** 何も削除されずに終了する

#### Scenario: 未 push の変更を警告する
- **WHEN** `{root}/wp-wp1` に未 push のコミットがある状態で uninstall を実行する
- **THEN** 確認プロンプトの前に、変更が失われる旨の警告が表示される

#### Scenario: 完全な後片付け
- **WHEN** `--yes` を付けて uninstall を実行する
- **THEN** `{root}/wp-wp1` と `{root}/wp-wp2` が削除され、`wp-global-net`・`wp-mysql-data` を含む関連ボリューム・hosts ブロック・信頼済み CA・`.local/db.sqlite3` が残らない

#### Scenario: hosts のバックアップは残して案内する
- **WHEN** `/etc/hosts.wp-dev-env.bak` がある状態で uninstall を実行する
- **THEN** バックアップは削除されず、最後に `sudo rm /etc/hosts.wp-dev-env.bak` による削除方法が表示される

#### Scenario: 部分的な状態でも完了する
- **WHEN** 一部のリソースが既に存在しない状態で uninstall を実行する
- **THEN** 存在しないリソースはスキップされ、残りのリソースの削除は続行される
