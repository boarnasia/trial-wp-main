# wp-main

WordPress 7 系（wp-wp1）と 6 系（wp-wp2）のローカル開発環境を管理するリポジトリ。
Caddy リバースプロキシ（内部 CA による HTTPS）と、両サイトを一括起動する Compose 定義、環境を構築・破棄する CLI を持つ。

| サイト | リポジトリ | URL | イメージ | デバッグ用ポート |
| --- | --- | --- | --- | --- |
| wp1 | `../wp-wp1`（trial-wp-wp1） | https://local.wp1.yamashita109.com/ | `wordpress:7.1-apache` | 127.0.0.1:8081 |
| wp2 | `../wp-wp2`（trial-wp-wp2） | https://local.wp2.yamashita109.com/ | `wordpress:6.7-apache` | 127.0.0.1:8082 |

```
{root}/
├── wp-main/   Caddyfile, docker-compose.yml（include で両サイトを取り込む）, CLI
├── wp-wp1/    wp1-wordpress + wp1-db
└── wp-wp2/    wp2-wordpress + wp2-db
        └── wp-global-net（外部ネットワーク）で Caddy と WordPress を接続。DB はサイト内ネットワークだけ
```

## 前提

- macOS、Docker Desktop（Compose v2.20 以上）、uv
- GitHub に SSH で接続できること（サイトリポジトリを clone する）
- ポート 80 / 443 が空いていること

## CLI

```bash
uv run cli help                      # コマンド一覧
uv run cli version
uv run cli dev-env:check-health      # 環境が正常か確認（読み取りのみ）
uv run cli dev-env:install           # 構築して起動（sudo のパスワードを求められる）
uv run cli dev-env:install --dry-run # 実行内容の確認だけ
uv run cli dev-env:uninstall         # 確認後にすべて削除（--yes で確認を省略）
```

`dev-env:install` が行うこと:

1. `{root}/wp-wp1`、`{root}/wp-wp2` を clone する（リモートが空ならテンプレートから初期化してローカルにコミットする。push はしない）
2. wp-main と各サイトの `.env` を `.env.example` から生成する（`change-me` はランダム値に置き換える。既存の `.env` は上書きしない）
3. `wp-global-net` ネットワークを作る
4. `/etc/hosts` に `# >>> wp-dev-env >>>` ブロックを追加する（sudo）。書き換え前の内容は `/etc/hosts.wp-dev-env.bak` に保存する。マーカーの対応が崩れている場合は書き換えずに止まる
5. `docker compose up -d --wait` で全サービスを起動し、WordPress を初期セットアップする
6. Caddy の内部 CA を System キーチェーンに信頼済みとして登録する（sudo）。`--skip-trust` で省略

主なオプション: `--root <dir>`（既定は wp-main の親）、`--no-start`、`--skip-trust`。

`dev-env:uninstall` は、コンテナ・ボリューム・イメージ・ネットワーク・hosts ブロック・CA・サイトディレクトリ・`.local/` の状態ファイルを削除する。サイトに未コミットや未 push の変更があれば警告する。`/etc/hosts.wp-dev-env.bak` は復旧用に残し、削除コマンド（`sudo rm /etc/hosts.wp-dev-env.bak`）を最後に案内する。

管理者のユーザー名とパスワードは各サイトの `.env`（`WP_ADMIN_USER` / `WP_ADMIN_PASSWORD`）にある。

## 日常の操作（wp-main で実行）

```bash
docker compose up -d                 # 一括起動
docker compose ps
docker compose logs -f caddy wp1-wordpress
docker compose stop                  # 停止（コンテナを残す）
docker compose down                  # 停止して削除（DB と CA のボリュームは残る）
docker compose run --rm wp1-cli wp plugin list   # WP-CLI
```

単体起動（wp-main の Caddy を使わない）:

```bash
cd ../wp-wp2 && docker compose up -d
# デバッグ用ポートはホスト名とポートが WP_HOME と違うため、そのままだと WordPress がポートを外した URL へ 301 を返す
curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: local.wp2.yamashita109.com' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8082/   # 200 なら正常
```

単体起動と一括起動はコンテナ名が同じなので同時には動かない。切り替えるときは先に片方を `docker compose down` する。
ボリューム名は固定なので、どちらで起動しても同じ DB を使う。切り替え時に出る `volume ... already exists but was created for project ...` の警告はこのためで、無視してよい。

## 検証

```bash
uv run cli dev-env:check-health          # 各項目を OK / WARN / FAIL / SKIP で表示
uv run cli dev-env:check-health --json   # 機械向け（CI やスクリプトから使う）
```

sudo は使わず、環境も変更しない。確認する項目は次のとおり。

| グループ | 項目 |
| --- | --- |
| 構成 | サイトリポジトリの origin、各 `.env` の有無と `change-me` の残り |
| ホスト | 各ドメインの名前解決（127.0.0.1）、`wp-global-net`、Caddy の CA がキーチェーンに登録されているか |
| コンテナ | Caddy と各サイトの WordPress・DB が running か（DB は healthy か） |
| HTTP と WordPress | HTTPS の応答と証明書の検証、HTTP から HTTPS へのリダイレクト、インストール済みか、メジャーバージョン |

- 前提の項目が FAIL なら、その項目は SKIP になる（例: Caddy が止まっていれば HTTP の項目はすべて SKIP）。WARN と FAIL には対処方法が表示される。
- FAIL が 1 つでもあれば終了コード 1、WARN だけなら 0。
- 管理画面へのログインは確認しない。ブラウザで `/wp-admin/` にログインし、リダイレクトがループしないことを確認する。

## 開発

```bash
uv run pytest
```

サイトの雛形は `templates/wp-site/` にある（`{{SITE_ID}}` などをサイトごとに置換する）。雛形は空のリモートを初期化するときだけ使う。初期化した後は、各サイトリポジトリ側を直接編集する。
