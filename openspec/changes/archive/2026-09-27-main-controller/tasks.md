## 1. compose の構成

- [x] 1.1 `include` の `env_file` に存在しないファイルを渡したときの挙動と `required: false` の可否を、手元の Docker Compose で確かめ、結果を design.md の Risks に追記する
- [x] 1.2 `docker-compose.yml` に共有 MySQL（`wp-mysql`、`wp-mysql-data`、内部ネットワーク、`127.0.0.1:${MYSQL_PORT:-3306}`、ヘルスチェック、`DB_*` から `MYSQL_*` への写し）を加え、サイトの `include` を `compose/<site>.yml` + `project_directory` + `env_file` に替える。`docker compose config` が通ることを確かめる
- [x] 1.3 `compose/wp1.yml`・`compose/wp2.yml` に `wpN-wordpress`（`restart` なし、共有 MySQL の healthy を待つ、`WP_DB_NAME` の既定はサイト ID）と `wpN-cli` を書き、`docker compose config` で wp1 のイメージが wp1 の `.env` の値になることを確かめる
- [x] 1.4 `.env.example` に `DB_USER`・`DB_PASSWORD`・`DB_ROOT_PASSWORD`・`MYSQL_PORT` を加え、install の秘密値の生成対象にする。install のテストで wp-main の `.env` にランダム値が入ることを確かめる
- [x] 1.5 `SITES` と compose のサイト定義・`include` の対応を確かめるテストを追加し、wp3 を `SITES` に足すと失敗することを確かめる

## 2. サイトの操作

- [x] 2.1 schema の用意（`CREATE DATABASE IF NOT EXISTS`・`GRANT`、root のパスワードは `MYSQL_PWD`）を実装し、実行されるコマンドにパスワードが含まれないことをテストで確かめる
- [x] 2.2 サイトの起動・停止・状態・共有インフラの起動・起動中のサイトの一覧を、単体起動の判定なしで実装し直す（`power.py` から切り出す）。test_power を新しい状態の判定（起動中・停止中・一部停止）と停止対象（WordPress だけ）に合わせて更新し、通ることを確かめる
- [x] 2.3 サイトの `.env` がない場合は compose を呼ばずにそのサイトだけ失敗させ、テストで確かめる
- [x] 2.4 ダッシュボードの起動・停止を新しい操作に切り替え、履歴のオプションに出どころ（dashboard）を加える。test_site_power_views が通ることを確かめる

## 3. serve

- [x] 3.1 `cli/management/commands/serve.py` に `serve [--site=...] [--root]` を追加し、`--site` の解決（カンマ区切り、`all`、不正な ID のエラーと一覧）をテストで確かめる
- [x] 3.2 開始時の処理（ポート確認 → django:migration → 共有インフラ → 指定したサイト → `supervise`）を実装し、共有インフラの失敗で終了すること、サイトの失敗で続くことをテストで確かめる
- [x] 3.3 終了時に起動中のサイトをすべて止め、serve が起動・停止したサイトを出どころ `serve` で履歴に記録する。`supervise` が 0 と 0 以外を返す両方で停止が呼ばれることをテストで確かめる
- [x] 3.4 `devenv serve` を、何もせずに `uv run manage.py serve` を案内して終了コード 1 を返す形にし、テストで確かめる。`SERVE_COMMAND` の案内（install・uninstall・migration 5）を `serve` に替える

## 4. install・migration の起動の扱い

- [x] 4.1 `rebuild_if_running()` を、Caddy が起動しているときにプロキシだけを作り直す形に替え（migration 2 も同じ関数を使う）、テストでサイトの起動が呼ばれないことを確かめる
- [x] 4.2 `devenv install` を「共有インフラ → 各サイトの起動 → `wp core install` → 各サイトの停止」に替え、最後に `serve --site=all` を案内する。test_install が通ることを確かめる
- [x] 4.3 `devenv uninstall` の削除対象に `wp-mysql-data`・共有 MySQL の内部ネットワーク・旧 DB のボリュームを加え、サイトのディレクトリの compose を使う分岐をなくす。test_uninstall が通ることを確かめる

## 5. migration 6

- [x] 5.1 `m0006_shared_mysql.py` で `DB_*` の追加と共有インフラの起動を実装し、既存の値を変えないことをテストで確かめる
- [x] 5.2 サイトごとの移行（旧コンテナの削除 → 一時コンテナ → 写し先の確認 → dump/import → テーブルと行数の比較 → 削除）を実装し、一致・不一致・写し先にデータがある・旧ボリュームがない の 4 通りをテストで確かめる
- [x] 5.3 migration 6 を sudo 不要・非破壊として登録し、`devenv migrate --auto` の対象になることをテストで確かめる

## 6. check-health

- [x] 6.1 共有インフラの項目（Caddy・共有 MySQL の起動と healthy）を加え、サイトごとの DB の項目をなくす。共有 MySQL が停止しているとき FAIL になることをテストで確かめる
- [x] 6.2 WordPress コンテナが停止しているサイトの項目と、その HTTP と WordPress の項目を SKIP（理由: 停止中）にする。テストで確かめる
- [x] 6.3 ダッシュボードのプロセスが応答しないときを WARN から SKIP（理由: 開発セッションの外）に替え、案内のコマンドを `serve` にする。テストで確かめる
- [x] 6.4 期待する WordPress のメジャーバージョンをサイトの `.env` の `WP_IMAGE` だけから求める（`SITES` の既定値に頼らない）。テストで確かめる

## 7. テンプレートとサイトのリポジトリ

- [x] 7.1 `templates/wp-site/` から `docker-compose.yml` を削除し、`.env.example` から `MYSQL_*` を削除して `WP_DB_NAME` を加え、README から単体起動の節を削除する。テンプレートからの初期化のテストで compose が生成されないことを確かめる
- [x] 7.2 wp-wp1 リポジトリでブランチを切り、`docker-compose.yml` の削除、`.env.example` の `MYSQL_*` の削除と `WP_DB_NAME` の追加、README の単体起動の節の削除を行い、draft PR を作る（wp-main を先にマージする旨を本文に書く）
- [x] 7.3 wp-wp2 リポジトリで 7.2 と同じ変更を行い、draft PR を作る

## 8. ドキュメントと実環境での確認

- [x] 8.1 README を更新する（`serve --site`、開発セッション、共有 MySQL とホストからの接続、migration 6 と移行前のボリュームの保存方法、単体起動の記述の削除、マージの順序）
- [x] 8.2 `uv run pytest` がすべて通り、`openspec validate main-controller --strict` が通ることを確かめる
- [x] 8.3 実環境で `devenv migrate` を実行し、migration 6 の後に `serve --site=all` で wp1・wp2 の既存の投稿が表示されること、Ctrl-C で `wp1-wordpress`・`wp2-wordpress` が止まり `wp-mysql`・`wp-caddy` が残ることを確かめる
- [x] 8.4 実環境で、セッションの外の `check-health` がサイトとダッシュボードを SKIP にして終了コード 0 になること、`serve --site=wp1` 中のダッシュボードから wp2 を起動・停止できること、ホストから `127.0.0.1:3306` で共有 MySQL に接続できることを確かめる
