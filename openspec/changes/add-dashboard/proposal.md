## Why

wp1 と wp2 を触るたびに、URL・ログイン画面・管理者の ID/PW を README や各サイトの `.env` から探している。wp-main の起動と同時に使える 1 枚のダッシュボードで、両サイトへの入口と認証情報をまとめて確認できるようにする（Asana: https://app.asana.com/1/1214853928077258/project/1217522554163352/task/1218885720956939）。

## What Changes

- wp-main の Compose に、ダッシュボードを配信する小さな Web サービスを追加する。
- Caddy に `local.wp-main.yamashita109.com` を追加し、内部 CA の HTTPS でダッシュボードへ転送する。
- ダッシュボードはサイトごとに 1 行の一覧表（デザイン案 B: https://claude.ai/artifact/5htivxt9G7bSt2tWfg2piG の `Compact.dc.html`）で、次を表示する。
  - サイト ID と WordPress のバージョン（`WP_IMAGE` のタグから求める）
  - サイト URL へのリンクと、`wp-login.php` へのログインリンク
  - デバッグ用ポート
  - 管理者のユーザー名とパスワード（パスワードは既定で伏せ、表示切替とコピーができる）
- ID/PW などの値は、リクエストのたびに `{root}/wp-wp1/.env` と `{root}/wp-wp2/.env` を読み取り専用で読み込んで表示する。`.env` を書き換えると、再起動せずに次の表示から反映される。
- Caddy が 80/443 を公開するアドレスを、既定で `127.0.0.1` に限定する。wp-main の `.env` または `docker compose up` 実行時の環境変数 `PROXY_BIND_ADDRESS` で `0.0.0.0` を指定したときだけ、全ネットワークインターフェースに公開する。ダッシュボードがパスワードを返すため、既定で LAN から届かないようにする。**BREAKING**: これまで LAN の他端末からアクセスしていた場合は、`PROXY_BIND_ADDRESS=0.0.0.0` の指定が必要になる。
- `dev-env:install` が `/etc/hosts` のブロックに新ドメインを追加する。`dev-env:uninstall` はダッシュボード用にビルドしたイメージも削除する。
- WordPress のニュースやセキュリティ情報の取得は行わない。

## Capabilities

### New Capabilities
- `dev-dashboard`: ローカル開発環境の各サイトへのリンクと、各サイトの `.env` から読み込んだ管理者の認証情報を 1 画面で表示するダッシュボード

### Modified Capabilities
- `proxy-gateway`: ダッシュボード用ドメインのルーティングを追加し、一括起動の対象にダッシュボードのコンテナを加える。プロキシのポートを既定で `127.0.0.1` だけに公開し、環境変数で全インターフェースへの公開に切り替えられるようにする
- `dev-env-cli`: hosts ブロックにダッシュボード用ドメインを加え、破棄の対象にダッシュボードのイメージを加える

## Impact

- 変更: `docker-compose.yml`、`Caddyfile`、`.env.example`、`src/wp_main/config.py`、`src/wp_main/devenv.py`、`pyproject.toml`、`README.md`
- 追加: ダッシュボードのアプリケーション（FastAPI）、テンプレート、Dockerfile、テスト
- 依存: FastAPI・uvicorn・Jinja2 を、CLI とは別の optional dependency としてコンテナにだけ入れる
- 既存環境: 反映には `dev-env:install` の再実行（hosts の更新）と `docker compose up -d --build` が必要
