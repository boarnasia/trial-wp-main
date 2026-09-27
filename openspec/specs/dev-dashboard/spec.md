# dev-dashboard Specification

## Purpose
ローカル開発環境の各 WordPress サイトへの入口（サイト URL・ログイン画面）と、各サイトの `.env` にある管理者の認証情報を 1 画面で確認できるようにする。

## Requirements

### Requirement: サイト一覧の表示
ダッシュボードは `https://local.wp-main.yamashita109.com/` で、wp1 と wp2 をこの順に 1 行ずつ一覧表で表示しなければならない (MUST)。各行には、サイト ID、WordPress のバージョン、サイト URL へのリンク、`wp-login.php` へのログインリンク、デバッグ用ポート、管理者のユーザー名、管理者のパスワード欄を含めなければならない (MUST)。WordPress のバージョンは、そのサイトの `WP_IMAGE` のタグから求めなければならない (MUST)（例: `wordpress:7.1-apache` は `WordPress 7.1`）。

#### Scenario: 一覧の表示
- **WHEN** 両サイトの `.env` がある状態で `https://local.wp-main.yamashita109.com/` を開く
- **THEN** wp1 と wp2 の 2 行が表示され、wp1 の行に `WordPress 7.1`、`https://local.wp1.yamashita109.com/` へのリンク、`https://local.wp1.yamashita109.com/wp-login.php` へのリンク、`127.0.0.1:8081` が含まれる

#### Scenario: ログインリンク
- **WHEN** wp2 の行のログインリンクを選ぶ
- **THEN** `https://local.wp2.yamashita109.com/wp-login.php` が開く

### Requirement: .env からの動的な読み込み
ダッシュボードは、表示する値（`WP_HOME`、`WP_IMAGE`、`WP_DEBUG_PORT`、`WP_ADMIN_USER`、`WP_ADMIN_PASSWORD`）を、リクエストのたびに `{root}/wp-wp1/.env` と `{root}/wp-wp2/.env` から読み込まなければならない (MUST)。`{root}` は CLI と同じく wp-main の親ディレクトリとする。値を起動時だけ読み込んで保持してはならない (MUST NOT)。ダッシュボードはサイトディレクトリに書き込んではならない (MUST NOT)。

#### Scenario: .env の変更を再起動なしで反映する
- **WHEN** `{root}/wp-wp1/.env` の `WP_ADMIN_PASSWORD` を書き換えた後、`serve` を再起動せずにパスワードを表示する
- **THEN** 書き換え後の値が表示される

#### Scenario: 読み取り専用
- **WHEN** ダッシュボードで一覧の表示、パスワードの表示、サイトの起動・停止を行う
- **THEN** `{root}/wp-wp1` と `{root}/wp-wp2` の中のファイルは変更されない

### Requirement: .env がない・値が欠けているサイト
サイトの `.env` がない、または必要な値が欠けている場合、ダッシュボードはエラーページにせず、そのサイトの行に不足している内容を表示しなければならない (MUST)。他のサイトの行は通常どおり表示しなければならない (MUST)。

#### Scenario: .env がない
- **WHEN** `{root}/wp-wp2/.env` がない状態でダッシュボードを開く
- **THEN** HTTP 200 が返り、wp1 の行は通常どおり表示され、wp2 の行には `.env` が見つからない旨が表示される

#### Scenario: パスワードが未設定
- **WHEN** `{root}/wp-wp1/.env` に `WP_ADMIN_PASSWORD` がない状態でダッシュボードを開く
- **THEN** wp1 のパスワード欄に未設定である旨が表示され、表示切替とコピーは無効になる

### Requirement: パスワードの表示切替とコピー
パスワードは既定で伏せ字で表示しなければならない (MUST)。一覧ページの HTML にはパスワードの値を含めてはならない (MUST NOT)。利用者が表示を選んだとき、またはコピーを選んだときにだけ、パスワードを取得しなければならない (MUST)。パスワードを返すレスポンスはキャッシュさせてはならない (MUST NOT)。ユーザー名とパスワードは、それぞれクリップボードにコピーできなければならない (MUST)。コピーの後は、コピーしたことを画面に表示しなければならない (MUST)。

#### Scenario: 既定で伏せる
- **WHEN** ダッシュボードを開く
- **THEN** パスワード欄は伏せ字で表示され、ページの HTML にパスワードの値は含まれない

#### Scenario: 表示を切り替える
- **WHEN** wp1 のパスワードの表示ボタンを選び、もう一度選ぶ
- **THEN** 1 回目で `.env` の `WP_ADMIN_PASSWORD` の値が表示され、2 回目で伏せ字に戻る

#### Scenario: パスワードをコピーする
- **WHEN** wp2 のパスワードのコピーボタンを選ぶ
- **THEN** クリップボードに wp2 の `WP_ADMIN_PASSWORD` の値が入り、コピーした旨が表示される

#### Scenario: キャッシュさせない
- **WHEN** パスワードを返すエンドポイントにリクエストする
- **THEN** レスポンスに `Cache-Control: no-store` が付く

### Requirement: 既存の環境への導入
ダッシュボードを持たない環境バージョン 1 の環境は、migration 2 で導入されなければならない (MUST)。migration 2 は `/etc/hosts` のブロックにダッシュボードのドメインを加えなければならない (MUST)。プロキシが起動している場合は、ダッシュボードのイメージをビルドして起動し、プロキシを新しい構成で作り直さなければならない (MUST)。プロキシが停止している場合は、コンテナを起動してはならない (MUST NOT)。migration 2 は sudo を必要とし、データを失う操作を含まないものとして扱わなければならない (MUST)。何度実行しても結果が同じでなければならない (MUST)。

#### Scenario: 起動中の環境に導入する
- **WHEN** 環境バージョン 1 で全コンテナが起動している状態で `devenv migrate` を実行する
- **THEN** `/etc/hosts` のブロックに `local.wp-main.yamashita109.com` が加わり、`wp-dashboard` が起動し、環境バージョンが 2 になる

#### Scenario: 停止中の環境に導入する
- **WHEN** 環境バージョン 1 でプロキシが停止している状態で `devenv migrate` を実行する
- **THEN** `/etc/hosts` のブロックは更新されるが、コンテナは起動されず、環境バージョンは 2 になる

#### Scenario: pull の後の自動実行
- **WHEN** 環境バージョン 1 の環境で、migration 2 を含むコミットを `git pull` で取り込む
- **THEN** migration は自動では実行されず、`uv run manage.py devenv migrate` を端末で実行するよう表示される

#### Scenario: 再実行
- **WHEN** hosts のブロックに既にダッシュボードのドメインがある状態で migration 2 を実行する
- **THEN** `/etc/hosts` は書き換えられない

### Requirement: 既存の環境での Django 版への切り替え
環境バージョン 2 の環境は、dev-env:migration 3 で Django 版のダッシュボードに切り替えられなければならない (MUST)。migration 3 は、wp-main の `.env` に `DJANGO_SECRET_KEY` がなければランダム値で加え、既存の値は変更してはならない (MUST NOT)。プロキシが起動している場合はダッシュボードのイメージを再ビルドして起動し直さなければならない (MUST)。停止している場合はコンテナを起動してはならない (MUST NOT)。migration 3 は sudo を必要とせず、データを失う操作を含まないものとして扱わなければならない (MUST)。何度実行しても結果が同じでなければならない (MUST)。切り替えの前後で、ダッシュボードの URL、表示内容、パスワード取得 API の応答は変わってはならない (MUST NOT)。

#### Scenario: pull の後に自動で切り替わる
- **WHEN** 環境バージョン 2 で全コンテナが起動している環境に、migration 3 を含むコミットを `git pull` で取り込む
- **THEN** migration 3 が自動で実行され、`.env` に `DJANGO_SECRET_KEY` が加わり、ダッシュボードが再ビルドされて起動し、環境バージョンが 3 になる

#### Scenario: 秘密鍵が既にある
- **WHEN** wp-main の `.env` に `DJANGO_SECRET_KEY` がある状態で migration 3 を実行する
- **THEN** `.env` は変更されない

#### Scenario: 切り替え後も同じ応答
- **WHEN** 切り替え後に `https://local.wp-main.yamashita109.com/` を開き、wp1 のパスワードを表示する
- **THEN** 切り替え前と同じ一覧が表示され、パスワードは `Cache-Control: no-store` 付きで返る

### Requirement: 既存の環境でのホストへの移行
環境バージョン 4 の環境は、dev-env:migration 5 でホストのダッシュボードに移行されなければならない (MUST)。migration 5 は、旧ダッシュボードのコンテナ `wp-dashboard` とイメージ `wp-main-dashboard` を削除しなければならない (MUST)。ボリューム `wp-dashboard-data` に DB があり、`.local/db.sqlite3` がない場合は、DB を `.local/db.sqlite3` に写してからボリュームを削除しなければならない (MUST)。写せなかった場合はボリュームを削除せずに migration を失敗させなければならない (MUST)。`.local/db.sqlite3` が既にある場合は、それを変更せずにボリュームを削除しなければならない (MUST)。プロキシが起動している場合は、新しい転送先でプロキシを作り直さなければならない (MUST)。停止している場合はコンテナを起動してはならない (MUST NOT)。wp-main の `.env` の `DASHBOARD_API_TOKEN` は変更してはならない (MUST NOT)。migration 5 は sudo を必要とせず、データを失う操作を含まないものとして扱わなければならない (MUST)。何度実行しても結果が同じでなければならない (MUST)。migration 5 の最後に、`uv run manage.py serve up` で開発セッションを始めるよう表示しなければならない (MUST)。

#### Scenario: pull の後に自動で移行する
- **WHEN** 環境バージョン 4 で全コンテナが起動し、操作履歴がある環境に、migration 5 を含むコミットを `git pull` で取り込む
- **THEN** `wp-dashboard` のコンテナ、`wp-main-dashboard` のイメージ、`wp-dashboard-data` のボリュームがなくなり、プロキシが作り直され、環境バージョンが 5 になり、`serve up` の後にダッシュボードを開くと移行前と同じ操作履歴が表示される

#### Scenario: 停止中の環境
- **WHEN** 環境バージョン 4 でプロキシが停止している状態で `devenv migrate` を実行する
- **THEN** 旧ダッシュボードのコンテナ・イメージ・ボリュームは削除されるが、コンテナは起動されず、環境バージョンは 5 になる

#### Scenario: 再実行
- **WHEN** 旧ダッシュボードのコンテナ・イメージ・ボリュームがない状態で migration 5 を実行する
- **THEN** エラーにならず、`.local/db.sqlite3` は変更されない
