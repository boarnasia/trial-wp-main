## 1. migration

- [x] 1.1 `src/wp_main/migrations/m0002_dashboard.py` を追加する（`REQUIRES_SUDO = True`、`DESTRUCTIVE = False`）。`up` は hosts のブロックを `hosts_domains()` で書き直し、Caddy が起動中なら `docker compose up -d --build --wait` を実行する。`tests/test_versioning.py` で `discover()` が通り、最新のバージョンが 2 になることを確認する
- [x] 1.2 migration 2 のテストを追加する。起動中なら compose up が呼ばれること、停止中なら呼ばれないこと、ドメインが既にあれば hosts を書き換えないこと、`--auto` では sudo を理由に実行されないことを確認する

## 2. check-health

- [x] 2.1 `health.py` に、ダッシュボードの名前解決・`wp-dashboard` コンテナ（running かつ healthy）・HTTPS 200・HTTP → HTTPS の項目を加える。`tests/test_health.py` の正常系の件数を更新し、ダッシュボード停止時と名前解決の失敗時のテストを追加して通す

## 3. ドキュメントと確認

- [x] 3.1 README のダッシュボードの節の案内を `dev-env:migrate` に変え、check-health の確認項目の表にダッシュボードを加える
- [ ] 3.2 実環境で `uv run cli dev-env:migrate` と `uv run cli dev-env:check-health` を実行し、環境バージョンが 2 になり、ダッシュボードの項目を含めてすべて OK になることを確認する
