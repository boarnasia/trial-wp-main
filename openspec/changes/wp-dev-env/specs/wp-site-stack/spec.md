## Purpose

各 WordPress サイトリポジトリ（wp-wp1: WordPress 7 系、wp-wp2: WordPress 6 系）が、単体でもプロキシ配下でも同じ Compose 定義で正しく動作するための振る舞いを定める。

## ADDED Requirements

### Requirement: サイトごとの専用スタック
各サイトリポジトリの `docker-compose.yml` は、WordPress コンテナと専用 MySQL 8.0 コンテナを定義しなければならない (MUST)。wp-wp1 は `wordpress:7.1-apache`、wp-wp2 は `wordpress:6.7-apache` を既定のイメージとしなければならない (MUST)。サービス名・コンテナ名・ボリューム名はサイト接頭辞（`wp1-`・`wp2-`）で一意にしなければならない (MUST)。

#### Scenario: バージョンの確認
- **WHEN** wp-wp1 のスタックを起動し、WordPress コンテナで WordPress のバージョンを確認する
- **THEN** バージョンは 7.1 系である

#### Scenario: 名前の衝突がない
- **WHEN** wp-wp1 と wp-wp2 の Compose ファイルを 1 つのプロジェクトに `include` する
- **THEN** サービス名・ボリューム名の衝突エラーが発生しない

### Requirement: 単体起動
各サイトリポジトリのディレクトリで `docker compose up -d` を実行したとき、`wp-global-net` が存在すれば、そのサイトのコンテナだけが起動し正常状態にならなければならない (MUST)。WordPress は DB のヘルスチェック成功後に起動しなければならない (MUST)。

#### Scenario: wp-wp2 単体起動
- **WHEN** `{root}/wp-wp2` で `docker compose up -d` を実行する
- **THEN** `wp2-db` がヘルシーになり、`wp2-wordpress` が起動し、ローカルのデバッグ用ポートへの HTTP リクエストに WordPress が応答する

### Requirement: 共通ネットワークへの参加
WordPress コンテナは外部ネットワーク `wp-global-net` に参加し、サービス名でプロキシから到達可能でなければならない (MUST)。DB コンテナはサイト内部ネットワークだけに参加しなければならない (MUST)。

#### Scenario: プロキシからの到達性
- **WHEN** `wp-global-net` 上の別コンテナから `http://wp1-wordpress/` にリクエストする
- **THEN** wp-wp1 の WordPress が応答する

#### Scenario: DB の隔離
- **WHEN** `wp-global-net` 上の別コンテナから `wp1-db` を名前解決する
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
DB 認証情報・サイト URL・イメージタグ・デバッグ用ポートは `.env` から読み込まなければならない (MUST)。リポジトリには `.env.example` だけを含め、`.env` は git 管理から除外しなければならない (MUST)。

#### Scenario: 秘密値がコミットされない
- **WHEN** サイトリポジトリで `git status` を確認する
- **THEN** `.env` は追跡対象にも未追跡一覧にも表示されない
