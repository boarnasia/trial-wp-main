# wp-site-stack Specification

## Purpose
各 WordPress サイト（wp-wp1: WordPress 7 系、wp-wp2: WordPress 6 系）について、サイトのリポジトリが持つもの（サイトの中身とサイト設定）と、wp-main が定義するサイトの WordPress コンテナがプロキシ配下で正しく動作するための振る舞いを定める。

## Requirements

### Requirement: 共通ネットワークへの参加
WordPress コンテナは外部ネットワーク `wp-global-net` に参加し、サービス名でプロキシから到達可能でなければならない (MUST)。WordPress コンテナは共有 MySQL と同じ内部ネットワークにも参加しなければならない (MUST)。

#### Scenario: プロキシからの到達性
- **WHEN** `wp-global-net` 上の別コンテナから `http://wp1-wordpress/` にリクエストする
- **THEN** wp1 の WordPress が応答する

#### Scenario: DB の隔離
- **WHEN** `wp-global-net` 上の別コンテナから `wp-mysql` を名前解決する
- **THEN** 名前解決に失敗する

### Requirement: リバースプロキシ配下の HTTPS 判定
WordPress は、リクエストヘッダー `X-Forwarded-Proto` に `https` が含まれる場合、そのリクエストを HTTPS として扱わなければならない (MUST)。サイト URL（`WP_HOME`・`WP_SITEURL`）は環境変数から設定しなければならない (MUST)。

#### Scenario: 無限リダイレクトしない
- **WHEN** プロキシが `X-Forwarded-Proto: https` を付けて `/wp-admin/` にリクエストする
- **THEN** WordPress は HTTPS へのリダイレクトを繰り返さず、ログイン画面またはダッシュボードを返す

#### Scenario: 管理画面の URL
- **WHEN** プロキシ経由で管理画面にログインする
- **THEN** 生成されるリンクとリダイレクト先はすべて `https://` のサイト URL になる

### Requirement: 設定値の分離
サイト URL・イメージタグ・デバッグ用ポート・schema 名はサイトの `.env` から、DB の認証情報は wp-main の `.env` から読み込まなければならない (MUST)。リポジトリには `.env.example` だけを含め、`.env` は git 管理から除外しなければならない (MUST)。

#### Scenario: 秘密値がコミットされない
- **WHEN** サイトリポジトリと wp-main で `git status` を確認する
- **THEN** `.env` は追跡対象にも未追跡一覧にも表示されない

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
