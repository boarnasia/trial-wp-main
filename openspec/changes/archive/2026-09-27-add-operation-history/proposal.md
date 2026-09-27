## Why

`devenv install`・`devenv migrate`・`devenv check-health` を、いつ、どの結果で実行したかは、端末の履歴にしか残らない。環境が壊れたときに直前の操作を追えるよう、Django への移行（段階 1）で用意した DB を使い、操作の履歴を残してダッシュボードで見られるようにする。これは段階 2 の最初の DB 利用であり、「DB に書き込むのはダッシュボードだけ、CLI は Web API を呼ぶ」という方針を実装として確立する。

## What Changes

- ダッシュボードに操作履歴のモデルを持たせ、DB（SQLite）をダッシュボード専用の名前付きボリュームに置く。django:migration は、ダッシュボードのコンテナが起動するときに適用する。
- ダッシュボードに、操作履歴を記録する API と一覧を返す API を加える。どちらもトークンで認証する。トークンは wp-main の `.env` の `DASHBOARD_API_TOKEN` とする。
- CLI は、`devenv install`・`devenv migrate`・`devenv check-health` の終了時に、結果を API へ送る。送れなかった場合は警告を表示するだけにし、コマンドの結果と終了コードは変えない。`--dry-run` の実行、何も適用しなかった `devenv migrate`、`devenv uninstall` は記録しない。
- ダッシュボードのトップページに、直近の操作履歴を表示する。
- dev-env:migration 4 を追加する。`.env` に `DASHBOARD_API_TOKEN` を加え、プロキシが起動中ならダッシュボードを再ビルドする（sudo 不要なので pull 後に自動で適用される）。
- `devenv check-health` に、操作履歴 API に認証付きで接続できるかの確認を加える。
- `devenv uninstall` は DB のボリュームも削除する。

## Capabilities

### New Capabilities
- `dev-operation-history`: CLI の操作結果の記録（Web API 経由）、保存先と保持件数、ダッシュボードでの表示、API の認証

### Modified Capabilities
- `dev-env-versioning`: dev-env:migration と django:migration の区別の要件で、DB の場所を `.local/db.sqlite3` からダッシュボードのボリュームに変える
- `dev-env-health`: 確認項目に操作履歴 API への接続を加える

## Impact

- コード: `wp_main.dashboard` にモデル・django:migration・API・テンプレートの一覧を追加する。CLI（`devenv` コマンド）に記録処理を加える。`health.py` に確認項目を加える。`devenv/migrations/m0004_*.py` を追加する
- コンテナ: `docker-compose.yml` にボリューム `wp-dashboard-data` と環境変数を加える。`dashboard.Dockerfile` の起動時に `manage.py migrate` を実行する
- 設定: `.env.example` に `DASHBOARD_API_TOKEN=change-me` を加える
- 運用: 既存の環境は `git pull` 後の自動移行で環境バージョン 4 になる。履歴は導入後の操作から残る
