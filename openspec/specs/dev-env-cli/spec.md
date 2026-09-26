# dev-env-cli Specification

## Purpose
wp-main から 1 コマンドでマルチリポジトリ WordPress 開発環境を構築・破棄できるようにし、ホスト OS と Docker に残るリソースを CLI が一元管理する。

## Requirements

### Requirement: CLI エントリポイント
wp-main ディレクトリで `uv run cli <command>` を実行したとき、CLI は `dev-env:install`、`dev-env:uninstall`、`help`、`version` の各コマンドを受け付けなければならない (MUST)。

#### Scenario: help を表示する
- **WHEN** ユーザーが `uv run cli help` を実行する
- **THEN** 利用可能なコマンド一覧と各コマンドの説明が表示され、終了コード 0 で終了する

#### Scenario: version を表示する
- **WHEN** ユーザーが `uv run cli version` を実行する
- **THEN** wp-main パッケージのバージョン文字列が 1 行で表示され、終了コード 0 で終了する

#### Scenario: 未知のコマンド
- **WHEN** ユーザーが存在しないコマンドを指定する
- **THEN** エラーメッセージが表示され、0 以外の終了コードで終了する

### Requirement: ルートディレクトリの決定
CLI は `{root}` を wp-main の親ディレクトリとして扱わなければならない (MUST)。`--root <path>` が指定された場合はそのパスを `{root}` として扱わなければならない (MUST)。

#### Scenario: 既定のルート
- **WHEN** `/work/wp-main` で `uv run cli dev-env:install` を実行する
- **THEN** サイトは `/work/wp-wp1` と `/work/wp-wp2` に配置される

### Requirement: サイトリポジトリの取得
`dev-env:install` は `{root}/wp-wp1` と `{root}/wp-wp2` を各 GitHub リモートから clone しなければならない (MUST)。clone したリポジトリが空の場合、CLI は wp-main のサイトテンプレートからファイルを生成し、ローカルに初回コミットを作成しなければならない (MUST)。CLI はリモートへ push してはならない (MUST NOT)。

#### Scenario: 空リモートからの初期化
- **WHEN** リモート `trial-wp-wp1` にコミットがない状態で install を実行する
- **THEN** `{root}/wp-wp1` に `docker-compose.yml`・`.env.example`・wp-config 追加コードが生成され、`origin` が設定された状態で初回コミットが作成される

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
`dev-env:install` は wp-main と各サイトに `.env` が存在しない場合、`.env.example` を元に `.env` を生成しなければならない (MUST)。DB パスワードなどの秘密値はランダム値で生成しなければならない (MUST)。既存の `.env` を上書きしてはならない (MUST NOT)。

#### Scenario: 初回生成
- **WHEN** `{root}/wp-wp1/.env` が存在しない状態で install を実行する
- **THEN** `.env` が生成され、`MYSQL_PASSWORD` などの秘密値は `.env.example` のプレースホルダーと異なるランダム値になる

#### Scenario: 再実行
- **WHEN** `.env` が既に存在する状態で install を再実行する
- **THEN** `.env` の内容は変わらない

### Requirement: hosts エントリの管理
`dev-env:install` は `/etc/hosts` に `local.wp1.yamashita109.com` と `local.wp2.yamashita109.com` を `127.0.0.1` に向けるエントリを、CLI 専用のマーカーで囲んだブロックとして追加しなければならない (MUST)。ブロックが既に存在する場合は重複させてはならない (MUST NOT)。`dev-env:uninstall` はそのブロックだけを削除しなければならない (MUST)。マーカーの開始と終了の対応が崩れている場合、CLI は `/etc/hosts` を変更してはならない (MUST NOT)。CLI は `/etc/hosts` を書き換える前に、元の内容をバックアップしなければならない (MUST)。

#### Scenario: 冪等な追加
- **WHEN** install を 2 回実行する
- **THEN** `/etc/hosts` のマーカーブロックは 1 つだけ存在する

#### Scenario: 他のエントリを保持する
- **WHEN** uninstall を実行する
- **THEN** マーカーブロック以外の `/etc/hosts` の行は変更されない

#### Scenario: マーカーの対応が崩れている
- **WHEN** `/etc/hosts` に開始マーカーだけがあり終了マーカーがない状態で install または uninstall を実行する
- **THEN** CLI は `/etc/hosts` を変更せず、崩れている行を示してエラーにする

#### Scenario: 書き換え前のバックアップ
- **WHEN** install または uninstall が `/etc/hosts` を書き換える
- **THEN** 書き換え直前の内容が `/etc/hosts.wp-dev-env.bak` に保存される

### Requirement: 共通ネットワークの作成
`dev-env:install` は Docker ネットワーク `wp-global-net` が存在しない場合に作成しなければならない (MUST)。

#### Scenario: ネットワーク作成
- **WHEN** `wp-global-net` がない状態で install を実行する
- **THEN** `docker network ls` に `wp-global-net` が表示される

### Requirement: 環境の起動と CA の信頼登録
`dev-env:install` は、`--no-start` が指定されない限り wp-main で全サービスを起動しなければならない (MUST)。起動後、`--skip-trust` が指定されない限り Caddy の内部 CA ルート証明書を macOS System キーチェーンに信頼済みとして登録し、登録した証明書の識別子を記録しなければならない (MUST)。

#### Scenario: 起動と信頼登録
- **WHEN** オプションなしで install を実行する
- **THEN** 全コンテナが起動し、Caddy のルート証明書が System キーチェーンに信頼済みで登録される

#### Scenario: 信頼登録を省略する
- **WHEN** `--skip-trust` を付けて install を実行する
- **THEN** キーチェーンは変更されず、手動で信頼登録する手順が表示される

### Requirement: 環境の破棄
`dev-env:uninstall` は、確認プロンプトで承認された場合、または `--yes` が指定された場合にのみ削除を実行しなければならない (MUST)。削除対象は、全コンテナ、install 由来のボリュームとイメージ、`wp-global-net`、hosts のマーカーブロック、記録済みの信頼済み CA 証明書、`{root}/wp-wp1`、`{root}/wp-wp2` とする。`/etc/hosts` のバックアップは復旧用に残し、削除方法を表示しなければならない (MUST)。サイトディレクトリに未コミットまたは未 push の変更がある場合、CLI は確認プロンプトの前に警告を表示しなければならない (MUST)。

#### Scenario: 確認を拒否する
- **WHEN** uninstall の確認プロンプトで `N` を入力する
- **THEN** 何も削除されずに終了する

#### Scenario: 未 push の変更を警告する
- **WHEN** `{root}/wp-wp1` に未 push のコミットがある状態で uninstall を実行する
- **THEN** 確認プロンプトの前に、変更が失われる旨の警告が表示される

#### Scenario: 完全な後片付け
- **WHEN** `--yes` を付けて uninstall を実行する
- **THEN** `{root}/wp-wp1` と `{root}/wp-wp2` が削除され、`wp-global-net`・関連ボリューム・hosts ブロック・信頼済み CA が残らない

#### Scenario: hosts のバックアップは残して案内する
- **WHEN** `/etc/hosts.wp-dev-env.bak` がある状態で uninstall を実行する
- **THEN** バックアップは削除されず、最後に `sudo rm /etc/hosts.wp-dev-env.bak` による削除方法が表示される

#### Scenario: 部分的な状態でも完了する
- **WHEN** 一部のリソースが既に存在しない状態で uninstall を実行する
- **THEN** 存在しないリソースはスキップされ、残りのリソースの削除は続行される
