## MODIFIED Requirements

### Requirement: サイトの状態の表示
ダッシュボードのサイト一覧は、各サイトの行に、そのサイトの WordPress コンテナと共有 MySQL の状態から求めた「起動中」「停止中」「一部停止」のいずれかを表示しなければならない (MUST)。WordPress コンテナが起動して共有 MySQL が healthy なら「起動中」、WordPress コンテナが停止している（または存在しない）なら「停止中」、WordPress コンテナは起動しているが共有 MySQL が healthy でなければ「一部停止」としなければならない (MUST)。状態はページを開くたびに Docker から取得しなければならない (MUST)。Docker に接続できない場合は、エラーページにせず、状態を取得できないことを表示し、起動・停止のボタンを無効にしなければならない (MUST)。

#### Scenario: 起動中のサイト
- **WHEN** `wp1-wordpress` と `wp-mysql` が起動している状態でダッシュボードを開く
- **THEN** wp1 の行に「起動中」と停止のボタンが表示される

#### Scenario: 停止中のサイト
- **WHEN** `wp2-wordpress` が停止している（または存在しない）状態でダッシュボードを開く
- **THEN** wp2 の行に「停止中」と起動のボタンが表示される

#### Scenario: Docker に接続できない
- **WHEN** Docker Desktop が停止している状態でダッシュボードを開く
- **THEN** HTTP 200 が返り、各サイトの行に状態を取得できないことが表示され、起動・停止のボタンは無効になる

### Requirement: サイトの起動と停止
ダッシュボードは、起動のボタンで、そのサイトの schema を用意してから WordPress を起動し、WordPress が起動して共有 MySQL が healthy になるまで待たなければならない (MUST)。停止のボタンでそのサイトの WordPress を停止しなければならない (MUST)。停止では共有インフラ（プロキシと共有 MySQL）を停止してはならない (MUST NOT)。停止ではコンテナとボリュームを削除してはならない (MUST NOT)。操作は wp-main の Compose プロジェクトで行わなければならない (MUST)。他のサイトに影響を与えてはならない (MUST NOT)。操作が終わったら、結果（成功または失敗の理由）をサイト一覧に表示しなければならない (MUST)。起動は 120 秒以内に終わらなければ失敗として扱わなければならない (MUST)。

#### Scenario: 停止する
- **WHEN** wp1 と wp2 が起動している状態で、wp1 の停止のボタンを選ぶ
- **THEN** `wp1-wordpress` が停止し、`wp2-wordpress`・`wp-mysql`・`wp-caddy` は起動したままで、wp1 の行が「停止中」になる

#### Scenario: 起動する
- **WHEN** wp1 が停止している状態で、wp1 の起動のボタンを選ぶ
- **THEN** `wp1-wordpress` が起動し、wp1 の行が「起動中」になり、`https://local.wp1.yamashita109.com/` が応答する

#### Scenario: 単体起動したサイト
- **WHEN** `{root}/wp-wp2` に以前の `docker-compose.yml` が残っている状態で、ダッシュボードから wp2 を起動する
- **THEN** サイトのディレクトリの compose ファイルは使われず、wp-main のプロジェクトで `wp2-wordpress` が起動する

#### Scenario: 失敗する
- **WHEN** wp1 の `.env` がない状態で wp1 の起動のボタンを選ぶ
- **THEN** 起動は行われず、wp1 の行に失敗の理由が表示される
