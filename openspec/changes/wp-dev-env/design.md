## Context

- wp-main は OpenSpec の雛形だけがある空のリポジトリ。リモートは `git@github.com:boarnasia/trial-wp-main.git`。
- サイトのリモート `trial-wp-wp1`・`trial-wp-wp2` は作成済みだが、コミットはない。
- `{root}/wp-wp1` には空の `wp-site2/` ディレクトリが既にある。`{root}/wp-wp2` は空ディレクトリ。
- ホストは macOS（Apple Silicon）、Docker Compose v5.1.2、uv 0.11。ポート 80/443 は空いている。
- 実装で編集できるのは wp-main 配下だけ。サイトリポジトリの中身は wp-main のテンプレートから CLI が生成する。
- Docker Hub に `wordpress:7.1-apache`、`wordpress:6.7-apache`、`mysql:8.0`、`caddy:2` があることを確認済み。

## Goals / Non-Goals

**Goals:**
- install と uninstall が冪等で、途中で失敗しても再実行で収束する。
- サイトリポジトリは wp-main がなくても（ネットワークさえあれば）`docker compose up` で動く。
- sudo が必要な操作を hosts 編集と CA 信頼登録の 2 つに限定する。

**Non-Goals:**
- Linux・Windows のホスト対応（hosts のパスや証明書ストアは macOS 前提）。
- 本番デプロイ、DB のバックアップ・移行。
- リモートへの自動 push（初回 push は手動で確認してから行う）。

## Decisions

### D1. CLI 構成: typer + `[project.scripts]`
`pyproject.toml` に `cli = "wp_main.cli:app"` を定義し、`uv_build` バックエンドでパッケージ化する。`uv run cli` は scripts エントリを実行する。コマンド名のコロンは `@app.command("dev-env:install")` で指定する。`help` は typer 標準の `--help` と同じ内容を出すコマンドとして明示的に定義する。
- 代替: `python -m` 実行。要件のコマンド形式と合わないため不採用。

外部コマンド（git・docker・sudo）はすべて 1 つの runner 関数を経由して実行する。テストでは runner を差し替え、ホストを変更せずにコマンド列を検証する。

### D2. サイトリポジトリの取得: clone → 空ならテンプレートで初期化
`git clone <remote> {root}/wp-wpN` を実行し、`git rev-parse HEAD` が失敗する（空リポジトリ）場合は `templates/wp-site/` をレンダリングして初回コミットを作る。push はしない。テンプレートの変数はサイト ID（`wp1`/`wp2`）、ドメイン、イメージタグ、デバッグ用ポートだけで、`string.Template` で置換する。
- 代替: wp-main にサイトのファイルを持ち続けて毎回コピー。サイトリポジトリが独立して進化できなくなるため不採用。テンプレートは空リポジトリの初期化専用とする。
- 既存ディレクトリの扱い: 期待するリモートを持つ git リポジトリならスキップし、それ以外（`{root}/wp-wp1/wp-site2` がある現状を含む）はエラーで止める。ユーザーのファイルを CLI が勝手に消さない。

### D3. 共通ネットワークは `external: true`
各サイトと wp-main は `wp-global-net` を `external: true` で参照し、作成は CLI が行う。
- 代替: 各 Compose で `name: wp-global-net` の非 external 定義。検証では include 時に統合されて動いたが、単体起動したプロジェクトと wp-main のプロジェクトが同じネットワークの所有権を奪い合い、`down` でネットワーク削除が衝突する。要件も外部ネットワークを指定しているため不採用。
- DB はサイト専用ネットワーク（`wp1-internal`・`wp2-internal`）だけに参加させる。include 時に暗黙の `default` ネットワークが全サイトで共有されるのを避けるため、ネットワーク名は明示する。

### D4. 名前空間: サービス名・コンテナ名にサイト接頭辞
Compose の `include` はサービス名とボリューム名が衝突するとエラーになる。このため、サービス名を `wp1-wordpress`・`wp1-db` のようにし、`container_name` も同じ値に固定する。`container_name` を固定すると、単体起動中に wp-main から二重起動した場合に名前衝突エラーで止まる。これは意図した挙動で、同じ DB ボリュームを 2 つのコンテナが使う事故を防ぐ。

### D5. プロキシヘッダー処理: マウントした PHP ファイルを `WORDPRESS_CONFIG_EXTRA` で読み込む
公式イメージは `WORDPRESS_CONFIG_EXTRA` を `wp-config.php` 内で評価する。サイトリポジトリに `config/wp-config-proxy.php` を置いてコンテナへ読み取り専用でマウントし、`WORDPRESS_CONFIG_EXTRA` から `require_once` する。このファイルでは次の 2 つを行う。
- `HTTP_X_FORWARDED_PROTO` に `https` が含まれる場合、`$_SERVER['HTTPS'] = 'on'` を設定する。
- `WP_HOME`・`WP_SITEURL` を環境変数から定義する。

代替として、コードを `WORDPRESS_CONFIG_EXTRA` にインラインで書く方法がある。この方法は YAML と `$` のエスケープが読みにくく、差分レビューもしにくいため不採用。

### D6. wp-content はバインドマウント、コアは名前付きボリューム
`./wp-content` をバインドマウントし、テーマやプラグインをサイトリポジトリで git 管理する。`/var/www/html` 本体は名前付きボリューム `wpN-html` に置く。`uploads/` は `.gitignore` で除外する。

### D7. Caddy: `local_certs` + `caddy_data` ボリューム
Caddyfile のグローバルオプションに `local_certs` を設定し、各サイトブロックでは `tls internal` と `reverse_proxy wpN-wordpress:80` を指定する。ドメインは `{$WP1_DOMAIN}` のように wp-main の `.env` から渡す。Caddy は `X-Forwarded-Proto` と `X-Forwarded-Host` を自動で付与する。CA は `caddy_data` ボリュームに永続化し、`down` しても信頼登録が有効なまま残るようにする。

### D8. CA の信頼登録
install では、Caddy がルート証明書を生成するまで待つ。その後、`docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt` で証明書を取り出す。取り出した証明書を `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain` で登録する。証明書の SHA-1 は `.local/dev-env-state.json` に記録する。uninstall では、記録した SHA-1 を使い `sudo security delete-certificate -Z <sha1>` で削除する。
- 代替: `caddy trust`。この方法はコンテナ内で動くため、ホストのキーチェーンに届かず不採用。

### D9. hosts はマーカーブロックで管理
`# >>> wp-dev-env >>>` から `# <<< wp-dev-env <<<` までのブロックを、Python で生成・除去する。書き込みは一時ファイルを経由し、`sudo cp` で行う。反映後に `dscacheutil -flushcache` と `sudo killall -HUP mDNSResponder` を実行する。ブロックの生成・除去は純粋関数にして、テストで検証する。開始マーカーと終了マーカーの対応が崩れている場合は、除去範囲が無関係な行に及ぶのを防ぐため、書き換えずにエラーにする。書き込み前に `sudo cp -p` で `/etc/hosts.wp-dev-env.bak` へバックアップする。このバックアップは uninstall 後も復旧用に残し、uninstall の最後に削除コマンドを案内する。

### D10. uninstall の順序
1. 未コミット・未 push の変更を検出して警告し、確認する。
2. wp-main で `docker compose down --volumes --rmi all --remove-orphans` を実行する。
3. `wp-global-net` を削除する。
4. CA を削除する。
5. hosts ブロックを削除する。
6. サイトディレクトリを削除する。
7. state ファイルを削除する。

各ステップは失敗しても警告を出して次へ進む。最後に、失敗したステップの一覧を表示し、1 件でも失敗があれば 0 以外の終了コードで終わる。`--rmi all` は、ほかのプロジェクトが使用中のイメージを削除できずに警告になるだけなので許容する。

### D11. WordPress の初期セットアップ（Phase 4 の検証用）
各サイトの Compose に、`profiles: [cli]` を付けた `wpN-cli`（`wordpress:cli`）サービスを置く。install の最後に、未インストールのサイトだけに対して `wp core install` を実行する。管理者の資格情報は各サイトの `.env`（`WP_ADMIN_USER`・`WP_ADMIN_PASSWORD`、パスワードはランダム生成）で管理する。

## Risks / Trade-offs

- [sudo プロンプト] → hosts 編集と CA 登録は対話的に sudo パスワードを求める。Claude からは入力できないため、統合テストはユーザーが `! uv run cli dev-env:install` の形で実行する。
- [ポート 80/443 の競合] → install の前に使用中かどうかを確認し、使用中なら使っているプロセスを表示して止める。
- [`wordpress:cli` と本体の PHP バージョン差] → cli はファイルと DB を操作するだけなので、影響は小さい。
- [既存の `{root}/wp-wp1/wp-site2`] → D2 のとおり、install は止まる。ユーザーが空ディレクトリを手動で削除してから実行する（tasks に記載）。
- [バインドマウントの I/O 速度（macOS）] → 開発用途として許容する。遅い場合は後で VirtioFS の設定を見直す。
- [`--rmi all` による共有イメージの削除] → 使用中のイメージは削除されない。未使用の `mysql:8.0` なども削除されるが、次回は pull し直すだけで済む。

## Migration Plan

新規構築のため、移行はない。ロールバックは `uv run cli dev-env:uninstall --yes` で行う。wp-main 本体とサイトリモートへの初回 push は、ユーザーが確認した後に手動で行う。

## Open Questions

- WordPress 7 系の追従方針（`7.1-apache` に固定するか、`7-apache` の浮動タグにするか）。イメージは `.env` の `WP_IMAGE` で切り替えられるため、後で決めても設計は変わらない。
