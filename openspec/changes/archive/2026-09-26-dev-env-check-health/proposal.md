## Why

install 後に環境のどこが壊れているか（hosts、CA、コンテナ、WordPress）を調べるには、今は README の確認コマンドを 1 つずつ手で実行するしかない。また、`dev-env:install` 全体の流れ（コマンドの順序、`--no-start`・`--skip-trust` の分岐、ポート競合時の中断）は統合テストでしか確かめておらず、変更時に壊れても気づけない。

## What Changes

- `uv run cli dev-env:check-health` を追加する。sudo を使わず読み取りだけで、次の 4 グループを確認し、項目ごとに OK / WARN / FAIL / SKIP と対処方法を表示する。
  - 構成: サイトリポジトリ（期待する origin を持つ clone か）、`.env`（存在し、`change-me` が残っていないか）
  - ホスト: hosts ブロックと名前解決、`wp-global-net`、キーチェーンの CA と Caddy の現在の CA の一致
  - コンテナ: 5 つのコンテナの状態（DB は healthy）
  - HTTP と WordPress: HTTPS の応答と証明書検証、HTTP から HTTPS へのリダイレクト、インストール済みか、メジャーバージョン
- `--json` で機械向けの結果を出力する。FAIL が 1 つでもあれば終了コード 1、なければ 0。
- `tests/test_install.py` を追加し、ダミー実行（FakeRunner）で `dev-env:install` 全体の流れを検証する。

## Capabilities

### New Capabilities
- `dev-env-health`: 開発環境の健全性チェックの振る舞い（確認項目、判定基準、依存する項目のスキップ、出力形式、終了コード）。

### Modified Capabilities
- `dev-env-cli`: 「CLI エントリポイント」要件に `dev-env:check-health` コマンドを追加する。

## Impact

- 新規: `src/wp_main/health.py`、`tests/test_health.py`、`tests/test_install.py`
- 変更: `src/wp_main/cli.py`（コマンド追加）、`README.md`（検証手順を check-health に置き換え）
- 依存の追加はない。HTTPS の確認には macOS の `/usr/bin/curl`（キーチェーンを参照する）を使う。
