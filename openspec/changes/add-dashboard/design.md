## Context

- wp-main の `docker-compose.yml` は Caddy だけを持ち、`include` で `../wp-wp1` と `../wp-wp2` の Compose を取り込む。Caddy は `wp-global-net` 上で各 WordPress に転送する。
- 管理者の認証情報は各サイトの `.env`（`WP_ADMIN_USER` / `WP_ADMIN_PASSWORD`）にだけある。`.env` は `dev-env:install` が `.env.example` から生成し、Git の管理外。
- `src/wp_main/sites.py` に `.env` のパーサー（`parse_env`）があり、`src/wp_main/config.py` の `SITES` がサイトの ID・ディレクトリ名・ドメインを持つ。
- hosts ブロックは `hosts.with_block()` が毎回作り直すので、ドメインを増やしても既存ブロックは置き換わる。
- デザインは案 B（一覧表）: https://claude.ai/artifact/5htivxt9G7bSt2tWfg2piG の `Compact.dc.html`。

## Goals / Non-Goals

**Goals:**
- `docker compose up -d` だけで、プロキシやサイトと一緒にダッシュボードが起動する。
- CLI（typer だけに依存）の依存を増やさない。
- `.env` の値をイメージや起動時の状態に残さない。

**Non-Goals:**
- ダッシュボード自体の認証。ローカル開発専用のため付けない。
- コンテナの稼働状況の表示や、コンテナの起動・停止の操作。
- サイトの追加に合わせて自動で行を増やすこと。表示するサイトは設定で列挙する。

## Decisions

### 1. FastAPI と Jinja2 のサーバーサイドレンダリング
一覧ページは Jinja2 のテンプレートで HTML を返す。表示切替とコピーのためだけに、素の JavaScript を少し使う。
- 代替: 標準ライブラリの `http.server`。依存はないが、ルーティング・テンプレート・テストクライアントを自前で書くことになる。
- 代替: SPA（React など）。1 画面の表示にはビルド工程が過剰。

### 2. コードは `wp_main` パッケージの中に置き、依存は optional にする
`src/wp_main/dashboard/`（`app.py`、`templates/`、`static/`）に置き、既存の `parse_env` と `SITES` を再利用する。FastAPI・uvicorn・Jinja2 は `[project.optional-dependencies] dashboard` に入れ、CLI の実行環境には入れない。テストのために、dev グループには `wp-main[dashboard]` と `httpx2`（Starlette の TestClient が推奨する HTTP クライアント）を加える。
- 代替: `dashboard/` に別プロジェクトを作る。`.env` のパーサーとサイト定義が二重になる。

### 3. イメージは wp-main のルートからビルドする
`dashboard.Dockerfile` を `python:3.12-slim` ベースで作り、`uv` で `.[dashboard]` だけを入れる。`.dockerignore` で `.git`、`.local`、`.venv`、`.env`、`openspec` などを除く。Compose では `build:` と固定のイメージ名 `wp-main-dashboard` を指定し、`dev-env:uninstall` がその名前で削除できるようにする。`dev-env:install` の `docker compose up -d --wait` がビルドも行う。

### 4. `.env` はサイトディレクトリごと読み取り専用でマウントする
`../wp-wp1:/sites/wp1:ro` のようにディレクトリでマウントし、アプリは `/sites/<id>/.env` をリクエストのたびに読む。
- 代替: `.env` ファイルだけをマウントする。エディタが別ファイルに書いてから置き換える保存方式だと、コンテナ側は古い inode を見続けて変更が反映されない。
- ディレクトリごと見えるが `:ro` なので書き込みはできない。

### 5. サイト一覧は `SITES` を使い、値は `.env` から取る
行の順序・ID・`.env` の場所は `SITES` で決める。URL・イメージ・ポート・ユーザー名・パスワードは `.env` の `WP_HOME`・`WP_IMAGE`・`WP_DEBUG_PORT`・`WP_ADMIN_USER`・`WP_ADMIN_PASSWORD` から取る。ログインリンクは `WP_HOME` + `/wp-login.php`。バージョンは `WP_IMAGE` のタグの先頭の数字部分（`7.1-apache` → `7.1`）から作る。タグが数字で始まらない場合（`latest` など）は、タグをそのまま表示する。サイトディレクトリのコンテナ内の場所は環境変数 `DASHBOARD_SITES_DIR`（既定 `/sites`）で変えられるようにし、テストで一時ディレクトリを使う。

### 6. パスワードは別のエンドポイントで返す
- `GET /`: 一覧 HTML。パスワードの値は含めない。
- `GET /api/sites/{id}/password`: `{"password": "..."}` を `Cache-Control: no-store` 付きで返す。サイトがない場合は 404、値がない場合は 404。
- 表示ボタンとコピーボタンは、押されたときにこの API を `fetch` する。コピーは `navigator.clipboard.writeText` を使う（HTTPS なので使える）。ユーザー名は HTML に含めてよい。
- `GET /healthz`: Compose の healthcheck 用。

### 7. プロキシとドメイン
`.env.example` に `DASHBOARD_DOMAIN=local.wp-main.yamashita109.com` を追加し、Caddy の環境変数と Caddyfile のサイトブロックに加える。既存の `.env` は上書きされないため、Compose では `${DASHBOARD_DOMAIN:-local.wp-main.yamashita109.com}` と既定値を持たせる。`config.py` に `DASHBOARD_DOMAIN` を持たせ、`dev-env:install` の hosts ブロックに加える。ダッシュボードのコンテナは `wp-global-net` にだけ参加し、ホストにポートは公開しない。

### 8. プロキシのポートは既定で 127.0.0.1 にだけ公開する
Compose の Caddy のポートを `"${PROXY_BIND_ADDRESS:-127.0.0.1}:80:80"`、`"${PROXY_BIND_ADDRESS:-127.0.0.1}:443:443"`、`"${PROXY_BIND_ADDRESS:-127.0.0.1}:443:443/udp"` にする。Compose の変数展開は、シェルの環境変数を wp-main の `.env` より優先するので、`.env` と実行時の指定の両方に対応できる。`dev-env:install` の `docker compose up` も CLI の環境変数を引き継ぐ。`.env.example` には `# PROXY_BIND_ADDRESS=0.0.0.0` をコメントで載せる。
- 代替: Caddy の `remote_ip` でダッシュボードだけを制限する。Docker Desktop for Mac では、ホストからも LAN からも送信元がゲートウェイのアドレスに見えるため区別できない。
- 代替: ダッシュボードだけ別ポートで `127.0.0.1` に公開する。URL が他のサイトと揃わず、WordPress 管理画面の露出も残る。
- `dev-env:install` の空きポート確認は `0.0.0.0` での bind を試すため、どちらの設定でも既存の確認のままで足りる。

## Risks / Trade-offs

- [既定の変更で、これまで LAN の他端末（実機スマホなど）から確認していた使い方ができなくなる] → README に `PROXY_BIND_ADDRESS=0.0.0.0` の指定方法を書く。
- [`PROXY_BIND_ADDRESS=0.0.0.0` にすると、LAN の端末が Host ヘッダーを偽ればパスワード API に届く] → 明示的に選んだ場合だけ起きる。README に注意を書く。
- [`.env` を読むたびにファイルを開く] → サイトは 2 つで、アクセスするのは開発者 1 人なので負荷は無視できる。
- [バージョン表示はイメージのタグで、実際にインストールされた WordPress と異なることがある（コアの自動更新など）] → 表示はイメージのバージョンとして扱う。
- [既存環境では hosts にダッシュボードのドメインがない] → README に `dev-env:install` の再実行を書く。hosts ブロックは置き換えなので重複しない。

## Migration Plan

1. `git pull` の後、`uv run cli dev-env:install` を再実行する（hosts の更新とイメージのビルド・起動）。既存の `.env` に `DASHBOARD_DOMAIN` がなくても、Compose の既定値で動く。
2. ロールバックは、この変更を戻して `docker compose up -d --remove-orphans` を実行する。hosts に残る 1 行は害がなく、次の install で消える。
