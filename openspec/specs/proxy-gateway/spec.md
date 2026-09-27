# proxy-gateway Specification

## Purpose
wp-main が共通リバースプロキシとして各サイトへ HTTPS でルーティングし、1 回の `docker compose` 操作で全サイトとプロキシを一括制御できるようにする。

## Requirements

### Requirement: ドメイン別ルーティング
プロキシは `local.wp1.yamashita109.com` へのリクエストを wp-wp1 の WordPress へ、`local.wp2.yamashita109.com` へのリクエストを wp-wp2 の WordPress へ、`local.wp-main.yamashita109.com` へのリクエストをホストの `127.0.0.1` で待ち受けるダッシュボードへ転送しなければならない (MUST)。ダッシュボードの転送先のポートは、wp-main の `.env` の `DASHBOARD_PORT`（既定 8000）に従わなければならない (MUST)。転送時に `X-Forwarded-Proto` と `X-Forwarded-Host` を付与しなければならない (MUST)。ダッシュボードが起動していない場合は、502 を返さなければならない (MUST)。

#### Scenario: wp1 へのルーティング
- **WHEN** `https://local.wp1.yamashita109.com/` にアクセスする
- **THEN** WordPress 7 系サイトのページが返る

#### Scenario: wp2 へのルーティング
- **WHEN** `https://local.wp2.yamashita109.com/` にアクセスする
- **THEN** WordPress 6 系サイトのページが返る

#### Scenario: ダッシュボードへのルーティング
- **WHEN** `devenv serve` を実行している状態で `https://local.wp-main.yamashita109.com/` にアクセスする
- **THEN** ダッシュボードのページが返る

#### Scenario: ダッシュボードが起動していない
- **WHEN** `devenv serve` を実行していない状態で `https://local.wp-main.yamashita109.com/` にアクセスする
- **THEN** 502 が返り、各サイトへのルーティングは影響を受けない

### Requirement: 内部 CA による HTTPS
プロキシは、全ドメイン（`local.wp1.yamashita109.com`、`local.wp2.yamashita109.com`、`local.wp-main.yamashita109.com`）の証明書を内部 CA で自動発行し、ポート 443 で HTTPS を提供しなければならない (MUST)。ポート 80 への HTTP リクエストは HTTPS へリダイレクトしなければならない (MUST)。CA の鍵と証明書は再起動後も保持しなければならない (MUST)。

#### Scenario: HTTP から HTTPS へのリダイレクト
- **WHEN** `http://local.wp1.yamashita109.com/` にアクセスする
- **THEN** `https://local.wp1.yamashita109.com/` へのリダイレクトが返る

#### Scenario: 証明書の検証
- **WHEN** 内部 CA を信頼登録した後に `curl https://local.wp2.yamashita109.com/` を実行する
- **THEN** 証明書エラーなしでレスポンスが返る

#### Scenario: ダッシュボードの証明書
- **WHEN** 内部 CA を信頼登録した後に `curl https://local.wp-main.yamashita109.com/` を実行する
- **THEN** 証明書エラーなしでレスポンスが返る

#### Scenario: 再起動後も同じ CA
- **WHEN** wp-main で `docker compose down` の後に `docker compose up -d` を実行する
- **THEN** 内部 CA のルート証明書は変わらず、信頼登録をやり直す必要がない

### Requirement: 一括起動
wp-main ディレクトリで `docker compose up -d` を実行したとき、プロキシと両サイトの全コンテナが 1 つの Compose プロジェクトとして起動しなければならない (MUST)。ダッシュボードはコンテナとして起動してはならない (MUST NOT)。各サイトは自身のディレクトリの `.env` を使って構成されなければならない (MUST)。

#### Scenario: 全コンテナの起動
- **WHEN** wp-main で `docker compose up -d` を実行する
- **THEN** `docker compose ps` にプロキシ、`wp1-wordpress`、`wp1-db`、`wp2-wordpress`、`wp2-db` が起動状態で表示され、ダッシュボードのコンテナは表示されない

#### Scenario: 一括停止
- **WHEN** wp-main で `docker compose down` を実行する
- **THEN** 5 つのコンテナがすべて停止・削除され、DB ボリュームは保持される

### Requirement: 公開するネットワークインターフェース
プロキシはポート 80 と 443 を、既定では `127.0.0.1` だけに公開しなければならない (MUST)。wp-main の `.env` または `docker compose` 実行時の環境変数で `PROXY_BIND_ADDRESS` が指定された場合は、そのアドレスに公開しなければならない (MUST)。両方で指定された場合は、実行時の環境変数を優先しなければならない (MUST)。

#### Scenario: 既定はループバックだけ
- **WHEN** `PROXY_BIND_ADDRESS` を指定せずに wp-main で `docker compose up -d` を実行する
- **THEN** ポート 80 と 443 は `127.0.0.1` にだけ公開され、同じ LAN の他の端末からは接続できない

#### Scenario: .env で全インターフェースに公開する
- **WHEN** wp-main の `.env` に `PROXY_BIND_ADDRESS=0.0.0.0` を書いて `docker compose up -d` を実行する
- **THEN** ポート 80 と 443 が全ネットワークインターフェースに公開される

#### Scenario: 実行時の環境変数で公開する
- **WHEN** `.env` に指定がない状態で `PROXY_BIND_ADDRESS=0.0.0.0 docker compose up -d` を実行する
- **THEN** ポート 80 と 443 が全ネットワークインターフェースに公開される
