## MODIFIED Requirements

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
