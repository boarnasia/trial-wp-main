# {{DIR_NAME}}

{{TITLE}} の開発用リポジトリ。公開 URL は https://{{DOMAIN}}/ （wp-main の Caddy 経由）。

このリポジトリが持つのは、サイトの中身（`wp-content/`）とサイト設定（`.env`）だけ。コンテナの定義は wp-main にあり、このディレクトリで `docker compose` は使わない。

## 起動

wp-main から開発セッションとして起動する（`uv run manage.py devenv install` 済みであること）。

```bash
cd ../wp-main && uv run manage.py serve --site={{SITE_ID}}   # Ctrl-C で終了し、サイトも止まる
```

デバッグ用ポートで直接確認する場合（ホスト名とポートが `WP_HOME` と違うため、ヘッダーを付ける）:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: {{DOMAIN}}' -H 'X-Forwarded-Proto: https' http://127.0.0.1:{{DEBUG_PORT}}/   # 200 なら正常
```

## 構成

| パス | 内容 |
| --- | --- |
| `.env` | サイト設定（WordPress のイメージ、デバッグ用ポート、URL、schema 名、管理者）。`.env.example` から生成する |
| `config/wp-config-proxy.php` | `X-Forwarded-Proto` による HTTPS 判定と `WP_HOME` / `WP_SITEURL` |
| `wp-content/` | テーマ・プラグイン（コンテナにバインドマウント） |

DB は wp-main の共有 MySQL の `WP_DB_NAME` の schema（既定 `{{SITE_ID}}`）。ホストからは `127.0.0.1:3306` で接続できる（ユーザーとパスワードは wp-main の `.env`）。

WP-CLI（サイトの起動中に wp-main で実行する）:

```bash
cd ../wp-main && docker compose run --rm {{SITE_ID}}-cli wp plugin list
```
