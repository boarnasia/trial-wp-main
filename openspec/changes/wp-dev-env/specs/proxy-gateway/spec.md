## Purpose

wp-main が共通リバースプロキシとして各サイトへ HTTPS でルーティングし、1 回の `docker compose` 操作で全サイトとプロキシを一括制御できるようにする。

## ADDED Requirements

### Requirement: ドメイン別ルーティング
プロキシは `local.wp1.yamashita109.com` へのリクエストを wp-wp1 の WordPress へ、`local.wp2.yamashita109.com` へのリクエストを wp-wp2 の WordPress へ転送しなければならない (MUST)。転送時に `X-Forwarded-Proto` と `X-Forwarded-Host` を付与しなければならない (MUST)。

#### Scenario: wp1 へのルーティング
- **WHEN** `https://local.wp1.yamashita109.com/` にアクセスする
- **THEN** WordPress 7 系サイトのページが返る

#### Scenario: wp2 へのルーティング
- **WHEN** `https://local.wp2.yamashita109.com/` にアクセスする
- **THEN** WordPress 6 系サイトのページが返る

### Requirement: 内部 CA による HTTPS
プロキシは、両ドメインの証明書を内部 CA で自動発行し、ポート 443 で HTTPS を提供しなければならない (MUST)。ポート 80 への HTTP リクエストは HTTPS へリダイレクトしなければならない (MUST)。CA の鍵と証明書は再起動後も保持しなければならない (MUST)。

#### Scenario: HTTP から HTTPS へのリダイレクト
- **WHEN** `http://local.wp1.yamashita109.com/` にアクセスする
- **THEN** `https://local.wp1.yamashita109.com/` へのリダイレクトが返る

#### Scenario: 証明書の検証
- **WHEN** 内部 CA を信頼登録した後に `curl https://local.wp2.yamashita109.com/` を実行する
- **THEN** 証明書エラーなしでレスポンスが返る

#### Scenario: 再起動後も同じ CA
- **WHEN** wp-main で `docker compose down` の後に `docker compose up -d` を実行する
- **THEN** 内部 CA のルート証明書は変わらず、信頼登録をやり直す必要がない

### Requirement: 一括起動
wp-main ディレクトリで `docker compose up -d` を実行したとき、プロキシと両サイトの全コンテナが 1 つの Compose プロジェクトとして起動しなければならない (MUST)。各サイトは自身のディレクトリの `.env` を使って構成されなければならない (MUST)。

#### Scenario: 全コンテナの起動
- **WHEN** wp-main で `docker compose up -d` を実行する
- **THEN** `docker compose ps` にプロキシ、`wp1-wordpress`、`wp1-db`、`wp2-wordpress`、`wp2-db` が起動状態で表示される

#### Scenario: 一括停止
- **WHEN** wp-main で `docker compose down` を実行する
- **THEN** 5 つのコンテナがすべて停止・削除され、DB ボリュームは保持される
