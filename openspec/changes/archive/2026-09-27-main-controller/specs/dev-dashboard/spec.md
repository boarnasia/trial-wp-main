## MODIFIED Requirements

### Requirement: 既存の環境でのホストへの移行
環境バージョン 4 の環境は、dev-env:migration 5 でホストのダッシュボードに移行されなければならない (MUST)。migration 5 は、旧ダッシュボードのコンテナ `wp-dashboard` とイメージ `wp-main-dashboard` を削除しなければならない (MUST)。ボリューム `wp-dashboard-data` に DB があり、`.local/db.sqlite3` がない場合は、DB を `.local/db.sqlite3` に写してからボリュームを削除しなければならない (MUST)。写せなかった場合はボリュームを削除せずに migration を失敗させなければならない (MUST)。`.local/db.sqlite3` が既にある場合は、それを変更せずにボリュームを削除しなければならない (MUST)。プロキシが起動している場合は、新しい転送先でプロキシを作り直さなければならない (MUST)。停止している場合はコンテナを起動してはならない (MUST NOT)。wp-main の `.env` の `DASHBOARD_API_TOKEN` は変更してはならない (MUST NOT)。migration 5 は sudo を必要とせず、データを失う操作を含まないものとして扱わなければならない (MUST)。何度実行しても結果が同じでなければならない (MUST)。migration 5 の最後に、`uv run manage.py serve` で開発セッションを始めるよう表示しなければならない (MUST)。

#### Scenario: pull の後に自動で移行する
- **WHEN** 環境バージョン 4 で全コンテナが起動し、操作履歴がある環境に、migration 5 を含むコミットを `git pull` で取り込む
- **THEN** `wp-dashboard` のコンテナ、`wp-main-dashboard` のイメージ、`wp-dashboard-data` のボリュームがなくなり、プロキシが作り直され、環境バージョンが 5 になり、`serve` の後にダッシュボードを開くと移行前と同じ操作履歴が表示される

#### Scenario: 停止中の環境
- **WHEN** 環境バージョン 4 でプロキシが停止している状態で `devenv migrate` を実行する
- **THEN** 旧ダッシュボードのコンテナ・イメージ・ボリュームは削除されるが、コンテナは起動されず、環境バージョンは 5 になる

#### Scenario: 再実行
- **WHEN** 旧ダッシュボードのコンテナ・イメージ・ボリュームがない状態で migration 5 を実行する
- **THEN** エラーにならず、`.local/db.sqlite3` は変更されない
