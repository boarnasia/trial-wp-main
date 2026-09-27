# proxy-gateway Specification

## Purpose
wp-main が共通リバースプロキシとして各サイトとダッシュボードへ HTTPS でルーティングし、プロキシ・共有 MySQL・各サイトを 1 つの Compose プロジェクトとして定義する。

## Requirements

### Requirement: ドメイン別ルーティング
プロキシは `local.wp1.yamashita109.com` へのリクエストを wp-wp1 の WordPress へ、`local.wp2.yamashita109.com` へのリクエストを wp-wp2 の WordPress へ、`local.wp-main.yamashita109.com` へのリクエストをホストの `127.0.0.1` で待ち受けるダッシュボードへ転送しなければならない (MUST)。ダッシュボードの転送先のポートは、wp-main の `.env` の `DASHBOARD_PORT`（既定 8000）に従わなければならない (MUST)。転送時に `X-Forwarded-Proto` と `X-Forwarded-Host` を付与しなければならない (MUST)。ダッシュボードまたは転送先のサイトが起動していない場合は、502 を返さなければならない (MUST)。

#### Scenario: wp1 へのルーティング
- **WHEN** wp1 を起動した状態で `https://local.wp1.yamashita109.com/` にアクセスする
- **THEN** WordPress 7 系サイトのページが返る

#### Scenario: wp2 へのルーティング
- **WHEN** wp2 を起動した状態で `https://local.wp2.yamashita109.com/` にアクセスする
- **THEN** WordPress 6 系サイトのページが返る

#### Scenario: ダッシュボードへのルーティング
- **WHEN** 開発セッション中に `https://local.wp-main.yamashita109.com/` にアクセスする
- **THEN** ダッシュボードのページが返る

#### Scenario: ダッシュボードが起動していない
- **WHEN** 開発セッション中にダッシュボードのプロセスだけが応答しない状態で `https://local.wp-main.yamashita109.com/` にアクセスする
- **THEN** 502 が返り、各サイトへのルーティングは影響を受けない

#### Scenario: サイトが停止している
- **WHEN** wp2 が停止している状態で `https://local.wp2.yamashita109.com/` にアクセスする
- **THEN** 502 が返り、wp1 とダッシュボードへのルーティングは影響を受けない

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
wp-main ディレクトリの Compose プロジェクトは、プロキシ・共有 MySQL・各サイトの WordPress を 1 つのプロジェクトとして定義しなければならない (MUST)。ダッシュボードはコンテナとして起動してはならない (MUST NOT)。各サイトの WordPress は、そのサイトのディレクトリの `.env` を使って構成されなければならない (MUST)。wp-main で `docker compose up -d` を実行したときは、これらすべてが起動しなければならない (MUST)。

#### Scenario: 全コンテナの起動
- **WHEN** wp-main で `docker compose up -d` を実行する
- **THEN** `docker compose ps` にプロキシ、`wp-mysql`、`wp1-wordpress`、`wp2-wordpress` が起動状態で表示され、ダッシュボードのコンテナとサイトごとの DB のコンテナは表示されない

#### Scenario: 一括停止
- **WHEN** wp-main で `docker compose down` を実行する
- **THEN** 4 つのコンテナがすべて停止・削除され、共有 MySQL のボリュームは保持される

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
