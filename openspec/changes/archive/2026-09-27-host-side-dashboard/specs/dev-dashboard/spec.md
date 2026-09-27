## MODIFIED Requirements

### Requirement: .env からの動的な読み込み
ダッシュボードは、表示する値（`WP_HOME`、`WP_IMAGE`、`WP_DEBUG_PORT`、`WP_ADMIN_USER`、`WP_ADMIN_PASSWORD`）を、リクエストのたびに `{root}/wp-wp1/.env` と `{root}/wp-wp2/.env` から読み込まなければならない (MUST)。`{root}` は CLI と同じく wp-main の親ディレクトリとする。値を起動時だけ読み込んで保持してはならない (MUST NOT)。ダッシュボードはサイトディレクトリに書き込んではならない (MUST NOT)。

#### Scenario: .env の変更を再起動なしで反映する
- **WHEN** `{root}/wp-wp1/.env` の `WP_ADMIN_PASSWORD` を書き換えた後、`devenv serve` を再起動せずにパスワードを表示する
- **THEN** 書き換え後の値が表示される

#### Scenario: 読み取り専用
- **WHEN** ダッシュボードで一覧の表示、パスワードの表示、サイトの起動・停止を行う
- **THEN** `{root}/wp-wp1` と `{root}/wp-wp2` の中のファイルは変更されない

## ADDED Requirements

### Requirement: 既存の環境でのホストへの移行
環境バージョン 4 の環境は、dev-env:migration 5 でホストのダッシュボードに移行されなければならない (MUST)。migration 5 は、旧ダッシュボードのコンテナ `wp-dashboard` とイメージ `wp-main-dashboard` を削除しなければならない (MUST)。ボリューム `wp-dashboard-data` に DB があり、`.local/db.sqlite3` がない場合は、DB を `.local/db.sqlite3` に写してからボリュームを削除しなければならない (MUST)。写せなかった場合はボリュームを削除せずに migration を失敗させなければならない (MUST)。`.local/db.sqlite3` が既にある場合は、それを変更せずにボリュームを削除しなければならない (MUST)。プロキシが起動している場合は、新しい転送先でプロキシを作り直さなければならない (MUST)。停止している場合はコンテナを起動してはならない (MUST NOT)。wp-main の `.env` の `DASHBOARD_API_TOKEN` は変更してはならない (MUST NOT)。migration 5 は sudo を必要とせず、データを失う操作を含まないものとして扱わなければならない (MUST)。何度実行しても結果が同じでなければならない (MUST)。migration 5 の最後に、`uv run manage.py devenv serve` でダッシュボードを起動するよう表示しなければならない (MUST)。

#### Scenario: pull の後に自動で移行する
- **WHEN** 環境バージョン 4 で全コンテナが起動し、操作履歴がある環境に、migration 5 を含むコミットを `git pull` で取り込む
- **THEN** `wp-dashboard` のコンテナ、`wp-main-dashboard` のイメージ、`wp-dashboard-data` のボリュームがなくなり、プロキシが作り直され、環境バージョンが 5 になり、`devenv serve` の後にダッシュボードを開くと移行前と同じ操作履歴が表示される

#### Scenario: 停止中の環境
- **WHEN** 環境バージョン 4 でプロキシが停止している状態で `devenv migrate` を実行する
- **THEN** 旧ダッシュボードのコンテナ・イメージ・ボリュームは削除されるが、コンテナは起動されず、環境バージョンは 5 になる

#### Scenario: 再実行
- **WHEN** 旧ダッシュボードのコンテナ・イメージ・ボリュームがない状態で migration 5 を実行する
- **THEN** エラーにならず、`.local/db.sqlite3` は変更されない
