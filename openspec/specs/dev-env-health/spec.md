# dev-env-health Specification

## Purpose
`devenv install` で構築した開発環境が正しく動いているかを 1 コマンドで確かめ、壊れている箇所と対処方法を示す。

## Requirements

### Requirement: 読み取りだけで確認する
`devenv check-health` は、ファイル・Docker リソース・ホスト OS の設定を変更してはならない (MUST NOT)。sudo を必要とするコマンドを実行してはならない (MUST NOT)。`--root <path>` を `devenv install` と同じ意味で受け付けなければならない (MUST)。

#### Scenario: 環境を変更しない
- **WHEN** 任意の状態で `uv run manage.py devenv check-health` を実行する
- **THEN** `/etc/hosts`・キーチェーン・Docker のコンテナ・ボリューム・ネットワーク・サイトディレクトリは実行前と変わらず、sudo のパスワードは求められない

### Requirement: 確認項目と判定
CLI は次の項目をサイトごと（該当するもの）に確認し、各項目を OK・WARN・FAIL・SKIP のいずれかで判定しなければならない (MUST)。WARN と FAIL には対処方法を添えなければならない (MUST)。
- 構成: サイトリポジトリが期待する origin を持つ clone であること（なければ FAIL）。導入済みの環境バージョンがコードの最新のバージョンと一致すること（古ければ WARN、コードより新しければ FAIL、環境が未導入なら FAIL）。wp-main と各サイトに `.env` があること（なければ FAIL）、`change-me` が残っていないこと（残っていれば WARN）。
- ホスト: 各サイトのドメインとダッシュボードのドメインが名前解決で `127.0.0.1` になること（ならなければ FAIL）。`wp-global-net` があること（なければ FAIL）。Caddy の現在のルート CA がキーチェーンに登録されていること（なければ WARN）。ホストのダッシュボードのプロセスが `127.0.0.1` の設定されたポートで応答すること（応答しなければ WARN）。
- コンテナ: Caddy と各サイトの WordPress・DB コンテナが起動していること、DB が healthy であること（そうでなければ FAIL）。
- HTTP と WordPress: 各サイトのドメインとダッシュボードのドメインへの HTTPS が 200 を返すこと（接続できなければ FAIL、証明書を検証できないだけなら WARN）。HTTP が HTTPS へリダイレクトされること（されなければ FAIL）。WordPress がインストール済みであること（インストール画面へリダイレクトされれば FAIL）。WordPress のメジャーバージョンがサイトの設定（wp1 は 7、wp2 は 6）と一致すること（しなければ WARN）。

ダッシュボードのドメインへの HTTPS の項目は、ホストのダッシュボードのプロセスの項目を前提としなければならない (MUST)。

#### Scenario: 正常な環境
- **WHEN** install が完了し、全コンテナが起動し、`devenv serve` を実行している状態で実行する
- **THEN** すべての項目が OK になり、終了コード 0 で終了する

#### Scenario: CA を信頼登録していない
- **WHEN** `--skip-trust` で install した環境で実行する
- **THEN** CA の項目と HTTPS の項目は WARN になり、キーチェーンへの登録手順が表示され、終了コードは 0 になる

#### Scenario: hosts のエントリがない
- **WHEN** `/etc/hosts` から wp-dev-env ブロックを削除した状態で実行する
- **THEN** 名前解決の項目が FAIL になり、`uv run manage.py devenv install` の再実行が対処方法として表示される

#### Scenario: WordPress が未インストール
- **WHEN** DB を初期化した直後で WordPress の初期セットアップが済んでいない状態で実行する
- **THEN** そのサイトのインストール済みの項目が FAIL になる

#### Scenario: 環境バージョンが古い
- **WHEN** 未適用の migration がある状態で実行する
- **THEN** 環境バージョンの項目が WARN になり、`uv run manage.py devenv migrate` が対処方法として表示され、終了コードは 0 になる

#### Scenario: ダッシュボードが停止している
- **WHEN** `devenv serve` を実行していない状態で実行する
- **THEN** ダッシュボードのプロセスの項目が WARN になり、`uv run manage.py devenv serve` が対処方法として表示され、ダッシュボードの HTTPS の項目は SKIP になり、各サイトの項目は OK のままになり、終了コードは 0 になる

#### Scenario: ダッシュボードのドメインが hosts にない
- **WHEN** hosts のブロックにダッシュボードのドメインがない（migration 2 が未適用の）状態で実行する
- **THEN** ダッシュボードの名前解決の項目が FAIL になり、ダッシュボードの HTTP の項目は SKIP になる

#### Scenario: 操作履歴 API のトークンが一致しない
- **WHEN** wp-main の `.env` の `DASHBOARD_API_TOKEN` を書き換えて実行する
- **THEN** 判定と終了コードは書き換える前と変わらない（操作履歴 API の項目はない）

#### Scenario: プロキシからホストに届かない
- **WHEN** `devenv serve` は実行しているが、Caddy がホストのダッシュボードへ転送できない状態で実行する
- **THEN** ダッシュボードのプロセスの項目は OK になり、ダッシュボードの HTTPS の項目が FAIL になり、`docker compose logs caddy` の確認が対処方法として表示される

### Requirement: 前提が満たされない項目のスキップ
ある項目の前提となる項目が FAIL または SKIP の場合、CLI はその項目を実行せずに SKIP と判定し、理由を表示しなければならない (MUST)。SKIP は失敗として数えてはならない (MUST NOT)。

#### Scenario: コンテナが停止している
- **WHEN** wp-main で `docker compose stop` した後に実行する
- **THEN** コンテナの項目が FAIL になり、HTTP と WordPress の項目は SKIP になり、理由としてコンテナが起動していないことが表示される

#### Scenario: サイトリポジトリがない
- **WHEN** `{root}/wp-wp1` が存在しない状態で実行する
- **THEN** wp-wp1 のリポジトリの項目が FAIL になり、wp-wp1 の `.env` の項目は SKIP になる

### Requirement: 出力と終了コード
CLI は既定で、グループごとに項目・判定・メッセージ・対処方法を人が読める形で表示し、最後に判定ごとの件数を表示しなければならない (MUST)。`--json` が指定された場合は、全項目（ID、グループ、判定、メッセージ、対処方法）と全体の結果を 1 つの JSON オブジェクトとして標準出力に出力し、それ以外を標準出力に出してはならない (MUST)。FAIL が 1 つ以上あれば終了コード 1、なければ 0 で終了しなければならない (MUST)。

#### Scenario: JSON 出力
- **WHEN** `uv run manage.py devenv check-health --json` を実行する
- **THEN** 標準出力は JSON として解析でき、`checks` 配列の各要素が `id`・`group`・`status`・`message`・`hint` を持ち、`ok` は FAIL がないときだけ `true` になる

#### Scenario: WARN だけのとき
- **WHEN** WARN の項目があり、FAIL の項目がない状態で実行する
- **THEN** 終了コードは 0 になる
