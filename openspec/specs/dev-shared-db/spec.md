# dev-shared-db Specification

## Purpose
全サイトが共用する MySQL を共有インフラとして 1 台だけ動かし、サイトごとの schema でデータを分ける。サイトごとに DB を持っていた環境からの移行もここで定める。

## Requirements

### Requirement: 共有 MySQL
wp-main は MySQL 8.0 のコンテナを 1 台だけ定義しなければならない (MUST)。コンテナ名は `wp-mysql`、データのボリューム名は `wp-mysql-data` に固定しなければならない (MUST)。DB のユーザー名・パスワード・root のパスワードは wp-main の `.env`（`DB_USER`・`DB_PASSWORD`・`DB_ROOT_PASSWORD`）から読み込まなければならない (MUST)。ユーザーは全サイトで 1 つを共用しなければならない (MUST)。共有 MySQL は、各サイトの WordPress とだけ共有する内部ネットワークに参加し、`wp-global-net` に参加してはならない (MUST NOT)。ホストの `127.0.0.1` の `MYSQL_PORT`（既定 3306）に公開しなければならない (MUST)。`127.0.0.1` 以外のアドレスに公開してはならない (MUST NOT)。共有 MySQL にはヘルスチェックを定義しなければならない (MUST)。

#### Scenario: ホストから接続する
- **WHEN** 共有 MySQL が起動している状態で、ホストから `mysql -h 127.0.0.1 -P 3306 -u <DB_USER> -p` で接続する
- **THEN** 接続でき、`wp1` と `wp2` の schema が見える

#### Scenario: LAN からは接続できない
- **WHEN** 同じ LAN の他の端末から、ホストの 3306 番に接続する
- **THEN** 接続できない

#### Scenario: プロキシからは見えない
- **WHEN** `wp-global-net` 上の別コンテナから `wp-mysql` を名前解決する
- **THEN** 名前解決に失敗する

### Requirement: サイトごとの schema
各サイトの WordPress は、共有 MySQL の中の自分の schema だけを使わなければならない (MUST)。schema の名前はサイトの `.env` の `WP_DB_NAME` とし、未設定の場合はサイト ID としなければならない (MUST)。サイトを起動する前に、その schema がなければ作成し、共用ユーザーに権限を与えなければならない (MUST)。既にある schema の中身を変更してはならない (MUST NOT)。

#### Scenario: 初めて起動するサイト
- **WHEN** 共有 MySQL に `wp2` の schema がない状態で wp2 を起動する
- **THEN** `wp2` の schema が作成され、wp2 の WordPress はその schema に接続する

#### Scenario: schema が分かれている
- **WHEN** wp1 と wp2 を起動し、それぞれで投稿を作成する
- **THEN** wp1 の投稿は `wp1` の schema に、wp2 の投稿は `wp2` の schema にだけ保存される

#### Scenario: 名前を変える
- **WHEN** wp1 の `.env` に `WP_DB_NAME=wp1_dev` を書いて wp1 を起動する
- **THEN** wp1 の WordPress は `wp1_dev` の schema に接続する

### Requirement: サイトごとの DB からの移行
環境バージョン 5 の環境は、dev-env:migration 6 で共有 MySQL に移行されなければならない (MUST)。migration 6 は、wp-main の `.env` に `DB_USER`・`DB_PASSWORD`・`DB_ROOT_PASSWORD` がなければランダム値で追加しなければならない (MUST)。既にある値を変更してはならない (MUST NOT)。サイトごとの DB のボリューム（`wp1-db-data`・`wp2-db-data`）がある場合は、その中身をサイトの schema に写し、テーブルの一覧と各テーブルの行数が一致することを確かめてから、旧 DB のコンテナとボリュームを削除しなければならない (MUST)。確かめられなかった場合は、旧ボリュームを削除せずに migration を失敗させなければならない (MUST)。写し先の schema に既にテーブルがある場合は、上書きせずに migration を失敗させなければならない (MUST)。migration 6 はサイトのリポジトリ内のファイルを変更してはならない (MUST NOT)。migration 6 の後、サイトは停止していなければならない (MUST)。開発セッションの外で実行した場合は、migration 6 が起動した共有インフラも停止していなければならない (MUST)。開発セッション中に実行した場合は、共有インフラを停止してはならない (MUST NOT)。migration 6 の最後に、`uv run manage.py serve up --site=all` で開発セッションを始めるよう表示しなければならない (MUST)。migration 6 は sudo を必要とせず、データを失う操作を含まないものとして扱わなければならない (MUST)。何度実行しても結果が同じでなければならない (MUST)。

#### Scenario: pull の後に自動で移行する
- **WHEN** 環境バージョン 5 で wp1・wp2 に投稿がある環境に、migration 6 を含むコミットを `git pull` で取り込む
- **THEN** `wp1-db`・`wp2-db` のコンテナと `wp1-db-data`・`wp2-db-data` のボリュームがなくなり、`wp-mysql` は停止し、環境バージョンが 6 になり、`serve up --site=wp1,wp2` の後に移行前と同じ投稿が表示される

#### Scenario: 確認に失敗する
- **WHEN** 写した後の `wp1` の schema で、あるテーブルの行数が旧 DB と一致しない
- **THEN** `wp1-db-data` は削除されず、一致しないテーブルが表示され、migration 6 は失敗し、環境バージョンは 5 のままになる

#### Scenario: 写し先にデータがある
- **WHEN** 共有 MySQL の `wp1` の schema に既にテーブルがある状態で migration 6 を実行する
- **THEN** `wp1` の schema は変更されず、`wp1-db-data` は削除されず、migration 6 は失敗する

#### Scenario: 再実行
- **WHEN** 旧 DB のコンテナとボリュームがなく、共有 MySQL に移行済みの状態で migration 6 を実行する
- **THEN** エラーにならず、共有 MySQL の中身は変更されない
