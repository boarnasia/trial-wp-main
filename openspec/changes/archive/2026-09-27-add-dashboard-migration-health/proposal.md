## Why

`add-dashboard` で追加したダッシュボードは、既存の環境に入れるには `dev-env:install` の再実行が必要で、`dev-env:check-health` もダッシュボードを確認しない。main に入った migration と check-health の仕組みにダッシュボードをつなぎ、pull だけで導入の案内が出て、健全性もまとめて確認できるようにする。

## What Changes

- migration `m0002_dashboard` を追加する。hosts のブロックにダッシュボードのドメインを加え、プロキシが起動中なら `docker compose up -d --build --wait` でダッシュボードの起動とプロキシの再作成（ポートの公開範囲の変更）を行う。hosts の書き換えに sudo が必要なので、`git pull` 後の自動実行ではなく `dev-env:migrate` の手動実行を促す。
- `dev-env:check-health` に次の項目を加える。
  - ダッシュボードのドメインの名前解決
  - `wp-dashboard` コンテナが起動していて healthy であること
  - ダッシュボードへの HTTPS が 200 を返すこと、HTTP が HTTPS へリダイレクトされること
- README の案内を、`dev-env:install` の再実行から `dev-env:migrate` に変える。

## Capabilities

### New Capabilities

なし

### Modified Capabilities
- `dev-env-health`: 確認項目にダッシュボードの名前解決・コンテナ・HTTP を加える
- `dev-dashboard`: 既存の環境へのダッシュボードの導入を migration で行う

## Impact

- 追加: `src/wp_main/migrations/m0002_dashboard.py`、テスト
- 変更: `src/wp_main/health.py`、`README.md`、`tests/test_health.py`
- 環境の最新バージョンが 2 になる。既存の環境では `dev-env:migrate` の実行が必要（sudo のパスワードを求められる）
