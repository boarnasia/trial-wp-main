## MODIFIED Requirements

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

### Requirement: 一括起動
wp-main ディレクトリで `docker compose up -d` を実行したとき、プロキシと両サイトの全コンテナが 1 つの Compose プロジェクトとして起動しなければならない (MUST)。ダッシュボードはコンテナとして起動してはならない (MUST NOT)。各サイトは自身のディレクトリの `.env` を使って構成されなければならない (MUST)。

#### Scenario: 全コンテナの起動
- **WHEN** wp-main で `docker compose up -d` を実行する
- **THEN** `docker compose ps` にプロキシ、`wp1-wordpress`、`wp1-db`、`wp2-wordpress`、`wp2-db` が起動状態で表示され、ダッシュボードのコンテナは表示されない

#### Scenario: 一括停止
- **WHEN** wp-main で `docker compose down` を実行する
- **THEN** 5 つのコンテナがすべて停止・削除され、DB ボリュームは保持される
