## MODIFIED Requirements

### Requirement: CLI エントリポイント
wp-main ディレクトリで `uv run cli <command>` を実行したとき、CLI は `dev-env:install`、`dev-env:uninstall`、`dev-env:check-health`、`dev-env:migrate`、`help`、`version` の各コマンドを受け付けなければならない (MUST)。

#### Scenario: help を表示する
- **WHEN** ユーザーが `uv run cli help` を実行する
- **THEN** 利用可能なコマンド一覧と各コマンドの説明が表示され、終了コード 0 で終了する

#### Scenario: version を表示する
- **WHEN** ユーザーが `uv run cli version` を実行する
- **THEN** wp-main パッケージのバージョン文字列が 1 行で表示され、終了コード 0 で終了する

#### Scenario: 未知のコマンド
- **WHEN** ユーザーが存在しないコマンドを指定する
- **THEN** エラーメッセージが表示され、0 以外の終了コードで終了する
