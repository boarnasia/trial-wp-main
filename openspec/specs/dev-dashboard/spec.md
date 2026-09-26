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
ダッシュボードは、表示する値（`WP_HOME`、`WP_IMAGE`、`WP_DEBUG_PORT`、`WP_ADMIN_USER`、`WP_ADMIN_PASSWORD`）を、リクエストのたびに各サイトディレクトリの `.env` から読み込まなければならない (MUST)。値をイメージに焼き込んだり、起動時だけ読み込んで保持したりしてはならない (MUST NOT)。ダッシュボードはサイトディレクトリに書き込めてはならない (MUST NOT)。

#### Scenario: .env の変更を再起動なしで反映する
- **WHEN** `{root}/wp-wp1/.env` の `WP_ADMIN_PASSWORD` を書き換えた後、コンテナを再起動せずにパスワードを表示する
- **THEN** 書き換え後の値が表示される

#### Scenario: 読み取り専用
- **WHEN** ダッシュボードのコンテナ内からサイトの `.env` に書き込もうとする
- **THEN** 書き込みは失敗する

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
