## Why

WordPress 7 系（wp-wp1）と 6 系（wp-wp2）を並行開発するためのローカル環境を、手作業なしで再現・破棄できるようにしたい。各サイトは独立リポジトリとして単体起動でき、同時に wp-main から HTTPS 付きで一括起動できる必要がある。

## What Changes

- wp-main に Python（uv + typer）製 CLI を追加する。実行は `uv run cli <command>`。
  - `dev-env:install`: `{root}/wp-wp1`・`{root}/wp-wp2` の取得（GitHub リモートから clone、空リポジトリならテンプレートで初期化）、`.env` 生成、共通 Docker ネットワーク作成、`/etc/hosts` 登録、コンテナ起動、Caddy ローカル CA の macOS キーチェーン信頼登録を行う。
  - `dev-env:uninstall`: 確認プロンプトの後、install で導入したリソース（サイトディレクトリ、コンテナ・ボリューム・イメージ、ネットワーク、hosts エントリ、信頼済み CA）を削除する。
  - `help`・`version`。
- wp-main に Caddy リバースプロキシ（`tls internal`）と、Compose `include` で両サイトを取り込む `docker-compose.yml` を追加する。
- wp-main にサイト用テンプレート（`docker-compose.yml`・`.env.example`・プロキシヘッダー対応の wp-config 追加コード）を追加する。wp-wp1 は `wordpress:7.1-apache`、wp-wp2 は `wordpress:6.7-apache`、DB はそれぞれ専用の MySQL 8.0。
- 検証用コマンド集を README に記載する。

## Capabilities

### New Capabilities
- `dev-env-cli`: 開発環境の install / uninstall / help / version を提供する CLI の振る舞い（冪等性、確認プロンプト、ホスト OS への変更と後片付け）。
- `wp-site-stack`: 各 WordPress サイトリポジトリの Compose スタックの振る舞い（単体起動、共通ネットワーク参加、リバースプロキシ配下での HTTPS 判定、環境変数による設定分離）。
- `proxy-gateway`: wp-main の Caddy と一括起動の振る舞い（ドメイン別ルーティング、内部 CA による HTTPS、`include` による全サイト一括制御）。

### Modified Capabilities
<!-- 既存 spec なし -->

## Impact

- 新規ファイル（wp-main）: `pyproject.toml`、`src/wp_main/`、`templates/wp-site/`、`Caddyfile`、`docker-compose.yml`、`.env.example`、`README.md`、`tests/`。
- 生成先（wp-main の外）: `{root}/wp-wp1`、`{root}/wp-wp2`（リモート `git@github.com:boarnasia/trial-wp-wp1.git` / `trial-wp-wp2.git`）。
- ホスト OS: `/etc/hosts`、macOS System キーチェーン（どちらも sudo が必要）。
- Docker: 外部ネットワーク `wp-global-net`、ポート 80/443 の占有。
- 依存: Python 3.12+、uv、typer、Docker Compose v2.20+（`include` 対応）。
