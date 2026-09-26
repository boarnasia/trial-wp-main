# {{DIR_NAME}}

{{TITLE}} の開発用リポジトリ。公開 URL は https://{{DOMAIN}}/ （wp-main の Caddy 経由）。

## 起動

通常は wp-main から一括起動する（`uv run cli dev-env:install` 済みであること）。

```bash
cd ../wp-main && docker compose up -d
```

単体で起動する場合:

```bash
docker network inspect wp-global-net >/dev/null 2>&1 || docker network create wp-global-net
cp -n .env.example .env   # 初回のみ。change-me を書き換える
docker compose up -d
# デバッグ用ポートはホスト名とポートが WP_HOME と違うため、そのままだと WordPress がポートを外した URL へ 301 を返す
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: {{DOMAIN}}' -H 'X-Forwarded-Proto: https' http://127.0.0.1:{{DEBUG_PORT}}/   # 200 なら正常
```

単体起動と一括起動はコンテナ名が同じなので同時には動かない。切り替えるときは片方を `docker compose down` する。

## 構成

| パス | 内容 |
| --- | --- |
| `docker-compose.yml` | `{{SITE_ID}}-wordpress` / `{{SITE_ID}}-db` / `{{SITE_ID}}-cli`（profile: cli） |
| `config/wp-config-proxy.php` | `X-Forwarded-Proto` による HTTPS 判定と `WP_HOME` / `WP_SITEURL` |
| `wp-content/` | テーマ・プラグイン（コンテナにバインドマウント） |

WP-CLI:

```bash
docker compose run --rm {{SITE_ID}}-cli wp plugin list
```
