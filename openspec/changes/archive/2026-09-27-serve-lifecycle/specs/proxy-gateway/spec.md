## MODIFIED Requirements

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
