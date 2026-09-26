## 1. Phase 0: CLI 基盤（wp-main）

- [x] 1.1 `pyproject.toml`（typer、pytest、`uv_build`、`[project.scripts] cli = "wp_main.cli:app"`）と `src/wp_main/` を作成し、`uv run cli --help` が終了コード 0 で終わることを確認する
- [x] 1.2 `help`・`version` コマンドと、`dev-env:install`・`dev-env:uninstall` の空実装を追加し、`uv run cli help` と `uv run cli version` の出力を確認する
- [x] 1.3 外部コマンドの runner（dry-run と差し替えに対応）と、`--root` の解決処理を実装し、pytest で既定値（wp-main の親ディレクトリ）と指定値を検証する
- [x] 1.4 `.gitignore` に `.env`・`.venv/`・`__pycache__/` を追加し、`git status` に表示されないことを確認する

## 2. Phase 1: 共通インフラ & ネーミング

- [x] 2.1 hosts のマーカーブロックを生成・除去する純粋関数を実装し、pytest で冪等性と、ほかの行が保持されることを検証する
- [x] 2.2 hosts を sudo で書き込む処理と DNS キャッシュのフラッシュ処理を実装し、dry-run で実行されるコマンド列を確認する
- [x] 2.3 `wp-global-net` の存在確認と作成処理を実装し、実行後に `docker network inspect wp-global-net` が成功することを確認する
- [x] 2.4 ポート 80/443 の事前チェックを実装し、使用中のときにエラーになることを pytest（runner の差し替え）で確認する

## 3. Phase 2A / 2B: サイトテンプレート（並行作業可能）

- [x] 3.1 `templates/wp-site/docker-compose.yml` を作成する（`wpN-wordpress`・`wpN-db`・`wpN-cli`、`wpN-internal` と外部 `wp-global-net`、DB のヘルスチェック、`wpN-html`・`wpN-db-data` ボリューム、`./wp-content` のバインドマウント）
- [x] 3.2 `templates/wp-site/.env.example` を作成する（`WP_IMAGE`・`MYSQL_*`・`WP_HOME`・`WP_DEBUG_PORT`・`WP_ADMIN_*`）
- [x] 3.3 `templates/wp-site/config/wp-config-proxy.php` を作成する（`HTTP_X_FORWARDED_PROTO` の判定、`WP_HOME`・`WP_SITEURL` の定義）
- [x] 3.4 `templates/wp-site/.gitignore`・`README.md`・`wp-content/` の雛形を作成する
- [x] 3.5 テンプレートのレンダリング処理を実装する（wp1: `7.1-apache`・ポート 8081、wp2: `6.7-apache`・ポート 8082）。スクラッチディレクトリへ出力し、両方で `docker compose config` が成功することを確認する
- [x] 3.6 [2A] レンダリングした wp1 を単体で `docker compose up -d` し、`curl -H 'X-Forwarded-Proto: https' localhost:8081` が応答すること、WordPress が 7.1 系であることを確認して停止する
- [x] 3.7 [2B] レンダリングした wp2 で 3.6 と同じ確認を行い、WordPress が 6.7 系であることを確認する

## 4. Phase 3: wp-main のプロキシと一括起動

- [x] 4.1 `Caddyfile` を作成する（`local_certs`、2 ドメインの `tls internal` と `reverse_proxy`）。`docker run caddy:2 caddy validate` が成功することを確認する
- [x] 4.2 `docker-compose.yml` を作成する（`caddy` サービス、80/443、`caddy_data`・`caddy_config`、`include: ../wp-wp1/docker-compose.yml, ../wp-wp2/docker-compose.yml`）と `.env.example`（`WP1_DOMAIN`・`WP2_DOMAIN`）を作成し、`docker compose config` が成功することを確認する
- [x] 4.3 サイトの clone と、空リポジトリの場合のテンプレート初期化・初回コミット処理を実装し、pytest で「clone 済みならスキップ」「無関係なディレクトリならエラー」を検証する
- [x] 4.4 `.env` 生成処理（ランダムな秘密値、既存ファイルは上書きしない）を実装し、pytest で検証する
- [x] 4.5 `dev-env:install` の処理を組み立てる（事前チェック、clone、.env、ネットワーク、hosts、`compose up`、CA 登録と state 記録、`wp core install`、`--no-start`・`--skip-trust`）
- [x] 4.6 `dev-env:uninstall` を実装する（未 push 変更の警告、確認プロンプト、`--yes`、D10 の順序、失敗しても続行し最後にまとめて報告）。pytest で拒否時に何も実行されないことを検証する
- [x] 4.7 `README.md` にセットアップ手順・コマンド集（起動、停止、単体起動、ログ、検証、破棄）を記載する

## 5. Phase 4: 統合テスト（sudo が必要なため、ユーザーの端末で実行する）

- [ ] 5.1 ユーザーの確認後に空の `{root}/wp-wp1/wp-site2` を削除し、`! uv run cli dev-env:install` を実行して、全ステップが成功することを確認する
- [ ] 5.2 wp-main で `docker compose ps` を実行し、5 つのコンテナが起動していることを確認する。`docker compose down` と `docker compose up -d` の後も CA が変わらないことを確認する
- [ ] 5.3 `curl -sI https://local.wp1.yamashita109.com/` と `curl -sI https://local.wp2.yamashita109.com/` が証明書エラーなしで 200 を返すこと、`http://` が HTTPS へリダイレクトされることを確認する
- [ ] 5.4 ブラウザで両サイトの証明書が信頼済みであること、`/wp-admin/` へのログインとリダイレクトがループしないことを確認する
- [ ] 5.5 サイトディレクトリで単体起動（`docker compose up -d`）し、wp-main を起動していない状態で `localhost:808N` が応答することを確認する
- [ ] 5.6 `! uv run cli dev-env:uninstall` を実行し、ディレクトリ・コンテナ・ボリューム・ネットワーク・hosts ブロック・CA が残っていないことを確認する。続けて install を再実行し、環境が再構築できることを確認する

## 6. リポジトリ公開（ユーザーの確認後）

- [ ] 6.1 wp-main に `origin`（trial-wp-main）を設定し、コミットと push を行う。`git ls-remote` で反映を確認する
- [ ] 6.2 install が作成した wp-wp1・wp-wp2 の初回コミットを push し、次回の install が clone 済みのコードで動作することを確認する
