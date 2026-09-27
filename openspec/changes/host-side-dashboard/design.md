## Context

- ダッシュボード（Django + Django Ninja）は `dashboard.Dockerfile` のイメージで `wp-dashboard` コンテナとして動いている。SQLite は名前付きボリューム `wp-dashboard-data` にあり、サイトの `.env` は `../wp-wp1:/sites/wp1:ro` のマウントから読んでいる（`dashboard/data.py` の `DASHBOARD_SITES_DIR`）。
- CLI は `operations.call_api()` で HTTPS の API に履歴を送っている。トークンは `DASHBOARD_API_TOKEN`、証明書は `.local/caddy-root.crt` で検証している。
- 一括起動では、wp1 / wp2 のコンテナは `include` によって `wp-main` プロジェクトに属する（ラベル `com.docker.compose.project=wp-main`）。単体起動ではサイトのディレクトリ名のプロジェクトに属する。`container_name` は固定（`wp1-wordpress`、`wp1-db` など）。
- Docker は Docker Desktop（Engine 29.8、Compose v5.5）。コンテナから `host.docker.internal` 経由で、ホストの `127.0.0.1` だけで待ち受けるサーバーに届くことを確認済み。
- 調査の経緯は `docs/research/2026-09-27-dashboard-site-power-control.md` にある（OrbStack の頃の調査なので、エンジン固有の記述は古い）。

## Goals / Non-Goals

**Goals:**
- ダッシュボードをホストで動かし、Docker のソケットを渡さずにサイトを起動・停止できるようにする。
- vite などのホストのプロセスを、`devenv serve` の一覧に 1 項目加えるだけで足せる形にする。
- CLI とダッシュボードが同じ DB（`.local/db.sqlite3`）を直接使う。

**Non-Goals:**
- vite の導入、フロントエンドのビルド。
- launchd によるダッシュボードの常駐、ログイン時の自動起動。
- ダッシュボードへのログイン機能（利用者は 127.0.0.1 から使う開発者 1 人という前提は変えない）。
- プロキシ全体の起動・停止をダッシュボードから行うこと（プロキシを止めるとダッシュボード自身に届かなくなる）。

## Decisions

### 1. `devenv serve` は自作の小さなスーパーバイザーにする
`src/wp_main/processes.py` に `HostProcess(name, command, cwd, env)` の一覧を置き、`devenv serve` がそれを `subprocess.Popen` で起動する。各プロセスの標準出力と標準エラーはスレッドで読み、`dashboard | ` のように名前を付けて出す。SIGINT / SIGTERM を受けたら全プロセスに SIGTERM を送り、10 秒待っても残るものは SIGKILL する。どれか 1 つが終了したら残りを止めて、0 以外で終わる。
- 代替案: honcho（Procfile）。依存が増え、ポートの検査や django:migration の事前適用を挟むには結局ラッパーが要るので採らない。
- 代替案: launchd に常駐させる。起動・停止・ログの確認が端末から見えにくく、開発中の再起動も面倒なので、今回は前面で動かすだけにする（Non-Goals）。

### 2. ダッシュボードは gunicorn で 127.0.0.1 にだけ bind する
`python -m gunicorn wp_main.wsgi:application --bind 127.0.0.1:{DASHBOARD_PORT} --workers 2 --timeout 150` で動かす。起動の操作は最大 120 秒待つため、gunicorn の既定の timeout（30 秒）では worker が殺される。`gunicorn` と `whitenoise` は extras から通常の依存に移す。
- 代替案: `manage.py runserver`。自動リロードは便利だが、1 プロセスで同期的に起動を待つ間ほかのリクエストに応答できなくなるので採らない。

### 3. Caddy は `host.docker.internal:{$DASHBOARD_PORT}` に転送する
Caddyfile を `reverse_proxy host.docker.internal:{$DASHBOARD_PORT}` にし、compose の caddy に `DASHBOARD_PORT: ${DASHBOARD_PORT:-8000}` と `extra_hosts: ["host.docker.internal:host-gateway"]` を加える。`extra_hosts` は Docker Desktop 以外のエンジンでも名前を解決させるためのもの。環境変数と `extra_hosts` が変わるので、`docker compose up -d` で Caddy が作り直され、新しい Caddyfile が読まれる。

### 4. サイトの状態は `docker inspect`、操作は `docker compose` で行う
- 状態: `docker inspect wp1-wordpress wp1-db` の JSON から `State.Status`、`State.Health.Status`、ラベル `com.docker.compose.project` を読む。存在しないコンテナがあると終了コードは 0 以外になるが、見つかった分の JSON は出るのでそれを使う。
- どのプロジェクトで操作するか: WordPress または DB のコンテナのラベルが `wp-main` 以外なら、そのサイトのディレクトリを `cwd` にする。それ以外（コンテナがない場合を含む）は wp-main を `cwd` にする。
- 起動: `docker compose up -d --wait --wait-timeout 120 wp1-wordpress`（`depends_on` によって DB も起動し、healthy を待つ）。
- 停止: `docker compose stop wp1-wordpress wp1-db`。`down` は使わない（コンテナを消すと単体起動との切り替えで混乱する）。
- 実行は既存の `Runner` と `docker.compose()` を使う。ダッシュボードのリクエストの中で同期的に実行し、終わったら一覧にリダイレクトする（POST → Redirect → GET）。
- 代替案: バックグラウンドのスレッドで実行し、画面をポーリングする。worker が再起動すると結果が失われ、実装も増える。起動は 20 秒ほどなので同期で足りる。

### 5. 同時実行はファイルロックで防ぐ
`.local/locks/site-wp1.lock` を `fcntl.flock(LOCK_EX | LOCK_NB)` で取る。gunicorn の複数 worker の間でも効く。取れなければ操作せず「実行中」を返す。一覧の表示時にも取れるかを試し、取れなければボタンを無効にする。

### 6. 結果の表示は Django の messages（CookieStorage）で行う
セッションの DB を増やさないように、`MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"` にする。操作の結果は messages でサイト一覧の上に出し、同じ内容を操作履歴にも残す。

### 7. CSRF と LAN への公開
`CsrfViewMiddleware` と `MessageMiddleware` を加え、`CSRF_TRUSTED_ORIGINS = ["https://local.wp-main.yamashita109.com"]`、`CSRF_COOKIE_SECURE = True` にする。起動・停止は通常の Django のビュー（`require_POST`）にして、フォームに `{% csrf_token %}` を入れる。Ninja の API は GET（パスワード）だけになるので影響しない。
wp-main の `.env` の `PROXY_BIND_ADDRESS` が `127.0.0.1` 以外なら、ボタンを無効にしてビューも 403 を返す。Docker Desktop ではコンテナから届く接続の送信元が区別できないので、送信元の IP での制限は採らない。

### 8. CLI は ORM で直接書く
`operations.record()` の中身を、API への送信から `Operation.objects.create()` と `prune()` に替える（トランザクション内）。記録の前に `call_command("migrate", verbosity=0)` でスキーマを最新にする。失敗したら今と同じく警告だけ出す。`call_api`、`ca_file`、`ApiError`、API のビューと `TokenAuth` は削除する。ダッシュボードの起動・停止も同じ `record()` を使う。`OperationIn` の `command` の選択肢はなくなるので、モデルの `command` は自由な文字列のままにする。
`devenv` コマンドの `requires_system_checks = []` は残す。システムチェックは今回の機能に不要で、DB がない状態でも CLI を速く動かすため。

### 8a. SECRET_KEY は wp-main の `.env` からも読む
コンテナでは compose が `DJANGO_SECRET_KEY` を環境変数で渡していたが、ホストの gunicorn には渡らない。未設定のままだと worker ごとにランダムな値になり、署名付き Cookie（messages）が別の worker で読めない。そのため `settings.py` は環境変数になければ wp-main の `.env` の値を使う。`DASHBOARD_PORT`・`PROXY_BIND_ADDRESS` を読む関数は、`config.py` から `sites.py` を読むと循環 import になるため `sites.py` に置く。

### 9. サイトの `.env` は `{root}` から読む
`data.py` の読み込み元を `resolve_root(...) / site.dir_name / ".env"` にする。`devenv serve --root` を受け付け、`WP_MAIN_ROOT` 環境変数でダッシュボードのプロセスに渡す。`DASHBOARD_SITES_DIR` は廃止する。

### 10. check-health
`container.wp-dashboard` の項目を削除し、`host.dashboard`（`http://127.0.0.1:{DASHBOARD_PORT}/healthz` に 2 秒で GET、応答しなければ WARN）を加える。`http.https.dashboard` は `host.dashboard` を前提にする。`http.api.dashboard` は削除する。項目数は 28 から 27 になる。

### 11. dev-env:migration 5
1. `docker rm -f wp-dashboard`（なければ何もしない）。
2. `wp-dashboard-data` があり、`.local/db.sqlite3` がなければ、`docker run --rm -v wp-dashboard-data:/data:ro -v {LOCAL_DIR}:/out caddy:2 sh -c 'cp /data/db.sqlite3* /out/'` で DB と WAL のファイルを写す。写した DB を `sqlite3` で開いて `PRAGMA integrity_check` を通す。失敗したら例外にする（ボリュームは消さない）。`caddy:2` はプロキシ用に必ずあるイメージなので、新しい pull が起きない。
3. `docker volume rm wp-dashboard-data`、`docker image rm wp-main-dashboard`（なければ何もしない）。
4. プロキシが起動中なら `docker compose up -d --wait --remove-orphans` で作り直す（既存の `rebuild_if_running` を使う）。
5. `uv run manage.py devenv serve` の実行を案内する。
データを写してから消すので `DESTRUCTIVE = False`、`REQUIRES_SUDO = False` とし、pull 後に自動で適用される。

## Risks / Trade-offs

- [ダッシュボードを使うには端末で `devenv serve` を動かし続ける必要がある] → install と migration 5 の最後に案内を出す。check-health は WARN で知らせる。常駐は別の変更で launchd を検討する。
- [ホストのダッシュボードは利用者の権限で Docker を操作できる] → 127.0.0.1 だけで待ち受け、CSRF を検証し、LAN への公開時は操作を無効にする。操作はサービス名を固定した `start` / `stop` だけに限る。
- [起動を同期で待つ間、gunicorn の worker が 1 つふさがる] → worker を 2 つにする。同じサイトへの同時操作はロックで弾く。
- [ボリュームから写した DB が壊れている] → integrity_check を通るまではボリュームを消さない。
- [8000 番を他のツールが使っている] → `DASHBOARD_PORT` で変えられるようにし、Caddy も同じ値を使う。変えた後は Caddy を作り直す必要があることを README に書く。
- [`PROXY_BIND_ADDRESS` を実行時の環境変数だけで指定した場合は検出できない] → `.env` での指定を正とし、README に書く。

## Migration Plan

1. 既存の環境は `git pull` の後、フックで migration 5 が自動適用される（sudo 不要、非破壊）。
2. 利用者は `uv run manage.py devenv serve` を実行してダッシュボードを使う。
3. 戻すときは、このコミットより前に戻して `docker compose up -d --build` を実行する。`.local/db.sqlite3` の履歴は旧ダッシュボードのボリュームには戻らない（履歴は失われてもよい情報として扱う）。
