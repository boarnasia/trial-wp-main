## MODIFIED Requirements

### Requirement: 確認項目と判定
CLI は次の項目をサイトごと（該当するもの）に確認し、各項目を OK・WARN・FAIL・SKIP のいずれかで判定しなければならない (MUST)。WARN と FAIL には対処方法を添えなければならない (MUST)。
- 構成: サイトリポジトリが期待する origin を持つ clone であること（なければ FAIL）。導入済みの環境バージョンがコードの最新のバージョンと一致すること（古ければ WARN、コードより新しければ FAIL、環境が未導入なら FAIL）。wp-main と各サイトに `.env` があること（なければ FAIL）、`change-me` が残っていないこと（残っていれば WARN）。
- ホスト: 各サイトのドメインとダッシュボードのドメインが名前解決で `127.0.0.1` になること（ならなければ FAIL）。`wp-global-net` があること（なければ FAIL）。Caddy の現在のルート CA がキーチェーンに登録されていること（なければ WARN）。ホストのダッシュボードのプロセスが `127.0.0.1` の設定されたポートで応答すること（応答しなければ SKIP とし、理由として開発セッションの外であることを表示する）。
- 共有インフラ: Caddy と共有 MySQL のコンテナが起動していること、共有 MySQL が healthy であること（そうでなければ FAIL）。
- サイト: 各サイトの WordPress コンテナが起動していること（停止中なら、そのサイトの項目とそれを前提とする項目を SKIP とし、理由として停止中であることを表示する）。
- HTTP と WordPress: 起動している各サイトのドメインとダッシュボードのドメインへの HTTPS が 200 を返すこと（接続できなければ FAIL、証明書を検証できないだけなら WARN）。HTTP が HTTPS へリダイレクトされること（されなければ FAIL）。WordPress がインストール済みであること（インストール画面へリダイレクトされれば FAIL）。WordPress のメジャーバージョンが、サイトの `.env` の `WP_IMAGE` のタグのメジャーバージョンと一致すること（しなければ WARN）。

ダッシュボードのドメインへの HTTPS の項目は、ホストのダッシュボードのプロセスの項目を前提としなければならない (MUST)。サイトの HTTP と WordPress の項目は、そのサイトの WordPress コンテナの項目を前提としなければならない (MUST)。

#### Scenario: 正常な環境
- **WHEN** install が完了し、`serve --site=all` を実行している状態で実行する
- **THEN** すべての項目が OK になり、終了コード 0 で終了する

#### Scenario: CA を信頼登録していない
- **WHEN** `--skip-trust` で install した環境で、`serve --site=all` を実行している状態で実行する
- **THEN** CA の項目と HTTPS の項目は WARN になり、キーチェーンへの登録手順が表示され、終了コードは 0 になる

#### Scenario: hosts のエントリがない
- **WHEN** `/etc/hosts` から wp-dev-env ブロックを削除した状態で実行する
- **THEN** 名前解決の項目が FAIL になり、`uv run manage.py devenv install` の再実行が対処方法として表示される

#### Scenario: WordPress が未インストール
- **WHEN** schema を初期化した直後で WordPress の初期セットアップが済んでいないサイトを起動した状態で実行する
- **THEN** そのサイトのインストール済みの項目が FAIL になる

#### Scenario: 環境バージョンが古い
- **WHEN** 未適用の migration がある状態で実行する
- **THEN** 環境バージョンの項目が WARN になり、`uv run manage.py devenv migrate` が対処方法として表示され、終了コードは 0 になる

#### Scenario: ダッシュボードが停止している
- **WHEN** `serve` を実行していない状態で実行する
- **THEN** ダッシュボードのプロセスの項目とダッシュボードの HTTPS の項目は SKIP になり、共有インフラの項目は OK のままになり、終了コードは 0 になる

#### Scenario: ダッシュボードのドメインが hosts にない
- **WHEN** hosts のブロックにダッシュボードのドメインがない（migration 2 が未適用の）状態で実行する
- **THEN** ダッシュボードの名前解決の項目が FAIL になり、ダッシュボードの HTTP の項目は SKIP になる

#### Scenario: 操作履歴 API のトークンが一致しない
- **WHEN** wp-main の `.env` の `DASHBOARD_API_TOKEN` を書き換えて実行する
- **THEN** 判定と終了コードは書き換える前と変わらない（操作履歴 API の項目はない）

#### Scenario: プロキシからホストに届かない
- **WHEN** `serve` は実行しているが、Caddy がホストのダッシュボードへ転送できない状態で実行する
- **THEN** ダッシュボードのプロセスの項目は OK になり、ダッシュボードの HTTPS の項目が FAIL になり、`docker compose logs caddy` の確認が対処方法として表示される

#### Scenario: 停止中のサイト
- **WHEN** `serve --site=wp1` を実行している状態で実行する
- **THEN** wp2 の WordPress コンテナの項目と wp2 の HTTP と WordPress の項目は SKIP になり、理由として停止中であることが表示され、終了コードは 0 になる

#### Scenario: 共有 MySQL が停止している
- **WHEN** `docker stop wp-mysql` の後に実行する
- **THEN** 共有 MySQL の項目が FAIL になり、終了コードは 1 になる

### Requirement: 前提が満たされない項目のスキップ
ある項目の前提となる項目が FAIL または SKIP の場合、CLI はその項目を実行せずに SKIP と判定し、理由を表示しなければならない (MUST)。SKIP は失敗として数えてはならない (MUST NOT)。

#### Scenario: コンテナが停止している
- **WHEN** wp-main で `docker compose stop` した後に実行する
- **THEN** 共有インフラの項目が FAIL になり、サイトの HTTP と WordPress の項目は SKIP になり、理由としてコンテナが起動していないことが表示される

#### Scenario: サイトリポジトリがない
- **WHEN** `{root}/wp-wp1` が存在しない状態で実行する
- **THEN** wp-wp1 のリポジトリの項目が FAIL になり、wp-wp1 の `.env` の項目は SKIP になる
