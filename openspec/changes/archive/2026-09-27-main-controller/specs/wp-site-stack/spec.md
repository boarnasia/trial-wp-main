## ADDED Requirements

### Requirement: サイトのリポジトリが持つもの
各サイトのリポジトリは、サイトの中身（`wp-content/` など）と、サイト設定の例（`.env.example`）と、wp-config の追加コードだけを持たなければならない (MUST)。サイトのリポジトリはコンテナの定義（`docker-compose.yml`）を持ってはならない (MUST NOT)。サイト設定（WordPress のイメージ、デバッグ用ポート、サイト URL、タイトル、管理者、schema 名）の正本は、サイトの `.env` でなければならない (MUST)。サイトの `.env` は DB のユーザー名とパスワードを持ってはならない (MUST NOT)。

#### Scenario: サイトのバージョンを上げる
- **WHEN** `{root}/wp-wp1/.env` の `WP_IMAGE` を `wordpress:7.2-apache` に変えて wp1 を起動する
- **THEN** wp1 は WordPress 7.2 で起動し、wp-main のファイルは変更しなくてよい

#### Scenario: サイトのディレクトリでは起動しない
- **WHEN** `{root}/wp-wp1` で `docker compose up -d` を実行する
- **THEN** compose ファイルがないためエラーになり、コンテナは起動しない

### Requirement: WordPress コンテナの定義
wp-main は、各サイトの WordPress コンテナと WP-CLI 用のサービスを、サイト ID を接頭辞にした名前（`wp1-wordpress`・`wp1-cli` など）で定義しなければならない (MUST)。各サイトのサービスは、そのサイトの `.env` の値で構成されなければならない (MUST)。WordPress コンテナは共有 MySQL の自分の schema に接続し、共有 MySQL が healthy になってから起動しなければならない (MUST)。WordPress コンテナに再起動の方針（`restart`）を設定してはならない (MUST NOT)。wp-main の `SITES` にあるすべてのサイトについて、対応する WordPress と WP-CLI のサービスが定義されていなければならない (MUST)。

#### Scenario: バージョンの確認
- **WHEN** wp1 を起動し、WordPress コンテナで WordPress のバージョンを確認する
- **THEN** バージョンは wp1 の `.env` の `WP_IMAGE` のタグと同じ系列（7.1 系）である

#### Scenario: Docker Desktop を再起動する
- **WHEN** wp1 が起動している状態で Docker Desktop を再起動する
- **THEN** `wp1-wordpress` は自動では起動しない

#### Scenario: 定義の漏れ
- **WHEN** `SITES` に wp3 を加え、compose に `wp3-wordpress` を定義しない
- **THEN** テストが失敗し、定義のないサイトが示される

## MODIFIED Requirements

### Requirement: 共通ネットワークへの参加
WordPress コンテナは外部ネットワーク `wp-global-net` に参加し、サービス名でプロキシから到達可能でなければならない (MUST)。WordPress コンテナは共有 MySQL と同じ内部ネットワークにも参加しなければならない (MUST)。

#### Scenario: プロキシからの到達性
- **WHEN** `wp-global-net` 上の別コンテナから `http://wp1-wordpress/` にリクエストする
- **THEN** wp1 の WordPress が応答する

#### Scenario: DB の隔離
- **WHEN** `wp-global-net` 上の別コンテナから `wp-mysql` を名前解決する
- **THEN** 名前解決に失敗する

### Requirement: 設定値の分離
サイト URL・イメージタグ・デバッグ用ポート・schema 名はサイトの `.env` から、DB の認証情報は wp-main の `.env` から読み込まなければならない (MUST)。リポジトリには `.env.example` だけを含め、`.env` は git 管理から除外しなければならない (MUST)。

#### Scenario: 秘密値がコミットされない
- **WHEN** サイトリポジトリと wp-main で `git status` を確認する
- **THEN** `.env` は追跡対象にも未追跡一覧にも表示されない

## REMOVED Requirements

### Requirement: サイトごとの専用スタック
**Reason**: サイトのリポジトリはコンテナの定義を持たず、MySQL は共有インフラとして 1 台だけ動かすため。
**Migration**: WordPress のコンテナ定義は「WordPress コンテナの定義」、MySQL は `dev-shared-db` の「共有 MySQL」を参照。既存のデータは dev-env:migration 6 が共有 MySQL に移す。

### Requirement: 単体起動
**Reason**: wp-main をメインコントローラーとし、サイトは wp-main からだけ起動するため（`docs/adr/0001-main-controller-and-shared-mysql.md`）。
**Migration**: `uv run manage.py serve --site=<サイト ID>` で起動する。
