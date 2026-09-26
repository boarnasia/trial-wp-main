## 1. install の流れのテスト

- [x] 1.1 `tests/test_install.py` に、ホストのパスを差し替える fixture と、コマンドに応じて返り値を返す FakeRunner の関数を追加し、通常の流れのコマンド順（clone → `.env` → network → hosts のバックアップと書き込み → `compose up` → `wp core install` → `security add-trusted-cert`）を検証する。`uv run pytest tests/test_install.py` が通ることを確認する
- [x] 1.2 `--no-start`、`--skip-trust`、ポート使用中、インストール済みの 4 つの分岐のテストを追加し、`uv run pytest` が全件通ることを確認する

## 2. 健全性チェックの本体

- [x] 2.1 `src/wp_main/health.py` に、`Check` と判定（OK / WARN / FAIL / SKIP）、`requires` による SKIP の処理、集計を実装する。前提が FAIL のときに SKIP になり、SKIP が失敗として数えられないことを `tests/test_health.py` で検証する
- [x] 2.2 構成の項目（リポジトリの origin、`.env` の有無、`change-me` の残り）を実装し、正常・リポジトリなし・`change-me` の残りの 3 ケースをテストで検証する
- [x] 2.3 ホストの項目（名前解決、`wp-global-net`、CA の SHA-1 とキーチェーンの一致）を実装し、名前解決と `security` の出力を差し替えたテストで OK / FAIL / WARN を検証する
- [x] 2.4 コンテナの項目を実装する（`docker compose ps --all --format json` の 1 行 1 オブジェクト形式と配列形式の両方を読む）。停止中・unhealthy・両形式をテストで検証する
- [x] 2.5 HTTP と WordPress の項目（HTTPS と証明書の検証、HTTP のリダイレクト、インストール済み、メジャーバージョン）を `/usr/bin/curl` で実装し、curl の出力を差し替えたテストで各判定を検証する

## 3. CLI と出力

- [x] 3.1 `cli.py` に、`dev-env:check-health`（`--root`、`--json`）と、人が読む形式の出力を追加する。`uv run cli help` に表示され、FAIL があれば終了コード 1 になることをテストで確認する
- [x] 3.2 `--json` の出力を実装し、標準出力が JSON として解析できること、`ok` と `summary` が正しいことをテストで確認する
- [x] 3.3 README の「検証」節を `uv run cli dev-env:check-health` を使う形に更新する

## 4. 実環境での確認

- [x] 4.1 起動中の環境で `uv run cli dev-env:check-health` を実行し、全項目が OK で終了コード 0 になることを確認する
- [x] 4.2 wp-main で `docker compose stop caddy` を実行した後に check-health を実行し、Caddy の項目が FAIL、HTTP の項目が SKIP、終了コードが 1 になることを確認する。その後 `docker compose start caddy` で戻す
- [x] 4.3 実行の前後で `/etc/hosts`・キーチェーン・`docker ps -a`・`docker volume ls` が変わっていないこと、sudo を求められないことを確認する
