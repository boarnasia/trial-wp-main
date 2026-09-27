## Why

ダッシュボードから wp1 / wp2 を起動・停止したいが、ダッシュボードはコンテナで動いているため、ホストの Docker を操作するには Docker のソケットを渡す（ホストの root 相当の権限を与える）か、ホスト側に別のエージェントを置く必要がある（`docs/research/2026-09-27-dashboard-site-power-control.md`）。今後は vite などのビルドツールもホストで動かすことになるため、コンテナに残すのは Caddy と WordPress などの実行環境だけにし、ダッシュボードのような開発用の道具はホストのプロセスとして動かす構成に切り替える。

## What Changes

- **BREAKING** ダッシュボードをコンテナ（`wp-dashboard`）からホストのプロセスに移す。新しいサブコマンド `uv run manage.py devenv serve` が、ダッシュボードを `127.0.0.1` だけで待ち受けて起動し、Ctrl-C で止める。`devenv serve` は複数のホストのプロセスを束ねて起動する作りにし、vite などを後から加えられるようにする（vite 自体の導入はこの変更に含めない）。
- Caddy は `local.wp-main.yamashita109.com` を `host.docker.internal` 経由でホストのダッシュボードへ転送する。
- ダッシュボードは、サイトの `.env` をコンテナのマウントではなく `{root}/wp-wp1`・`{root}/wp-wp2` から直接読む。
- ダッシュボードに、各サイトの状態（起動中・停止中）の表示と、起動・停止のボタンを加える。操作は wp-main のプロジェクト（単体起動されている場合はそのサイトのプロジェクト）の `docker compose` で行い、結果を操作履歴に残す。
- ダッシュボードの状態を変える操作（POST）に CSRF 対策を入れる。プロキシを LAN に公開している場合は、起動・停止を無効にする。
- **BREAKING** CLI は操作履歴を Web API ではなく DB（`.local/db.sqlite3`）に直接書き込む。操作履歴の記録 API・一覧 API と、そのトークン（`DASHBOARD_API_TOKEN`）を廃止する。
- `devenv check-health` の確認項目を、ダッシュボードのコンテナから、ホストのダッシュボードのプロセスに置き換え、操作履歴 API の確認をなくす。
- dev-env:migration 5 を追加する。旧ダッシュボードのコンテナとイメージを削除し、ボリュームの操作履歴を `.local/db.sqlite3` へ移してからボリュームを削除し、プロキシが起動中なら新しい設定で作り直す。
- `devenv install` は django:migration を適用し、最後に `devenv serve` の実行方法を表示する。`devenv uninstall` は `.local/db.sqlite3` を削除する。

## Capabilities

### New Capabilities
- `dev-host-processes`: ホストで動かす開発用プロセス（ダッシュボード、将来の vite など）を `devenv serve` でまとめて起動・停止する仕組み
- `dev-site-power`: ダッシュボードからのサイトの状態表示と起動・停止、その安全策（CSRF、LAN 公開時の無効化、同時実行の防止）

### Modified Capabilities
- `dev-dashboard`: `.env` の読み込み元をホストのサイトディレクトリに変える。ホストへの移行（dev-env:migration 5）の要件を加える
- `dev-operation-history`: 記録の方法を Web API から DB への直接書き込みに変える。API の認証の要件を削除する。保存先をボリュームから `.local/db.sqlite3` に変える。記録する操作にサイトの起動・停止を加える
- `dev-env-health`: ダッシュボードの確認をコンテナからホストのプロセスに変え、操作履歴 API の確認をなくす
- `dev-env-versioning`: django:migration を適用する場所を、コンテナの起動時から `devenv serve`・`devenv install` の実行時に変える
- `dev-env-cli`: `serve` サブコマンドを加える。install と uninstall の対象を変える
- `proxy-gateway`: ダッシュボードへの転送先をホストに変え、一括起動の対象からダッシュボードのコンテナを外す

## Impact

- コード: `devenv serve` とプロセスの一覧を追加する。`operations.py` を API 呼び出しから ORM への書き込みに変える。ダッシュボードにサイトの状態・起動・停止のビューを加え、`data.py` の読み込み元を変える。`health.py` のダッシュボードの項目を変える。`devenv/migrations/m0005_*.py` を追加する
- 設定: `settings.py` に `CsrfViewMiddleware` などを加える。`Caddyfile` の転送先を変える。`.env.example` から `DASHBOARD_API_TOKEN` を外す
- コンテナ: `docker-compose.yml` から `dashboard` サービスとボリューム `wp-dashboard-data` を外し、Caddy に `host.docker.internal` を解決させる。`dashboard.Dockerfile` を削除する
- 依存: `gunicorn`・`whitenoise` を extras からホストの通常の依存に移す
- 運用: 既存の環境は `git pull` 後の自動移行で環境バージョン 5 になる。以後、ダッシュボードを使うには `uv run manage.py devenv serve` を端末で動かしておく必要がある
