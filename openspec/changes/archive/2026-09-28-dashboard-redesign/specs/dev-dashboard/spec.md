## MODIFIED Requirements

### Requirement: サイト一覧の表示
ダッシュボードは `https://local.wp-main.yamashita109.com/` で、wp1 と wp2 をこの順に 1 行ずつ一覧表で表示しなければならない (MUST)。各行には、サイト ID、WordPress のバージョン、状態と起動・停止のボタン、サイト URL へのリンク、デバッグ用ポート、管理者のユーザー名、管理者のパスワード欄、`wp-login.php` を開く「WP ログイン」のボタン、サイトのリポジトリを GitHub で開くリンクを含めなければならない (MUST)。WordPress のバージョンは、そのサイトの `WP_IMAGE` のタグから求めなければならない (MUST)（例: `wordpress:7.1-apache` は `WordPress 7.1`）。GitHub のリンクは、wp-main が持つサイトのリモート（`git@github.com:<owner>/<repo>.git`）から `https://github.com/<owner>/<repo>` を求め、新しいタブで開かなければならない (MUST)。

#### Scenario: 一覧の表示
- **WHEN** 両サイトの `.env` がある状態で `https://local.wp-main.yamashita109.com/` を開く
- **THEN** wp1 と wp2 の 2 行が表示され、wp1 の行に `WordPress 7.1`、`https://local.wp1.yamashita109.com/` へのリンク、`https://local.wp1.yamashita109.com/wp-login.php` を開く「WP ログイン」、`127.0.0.1:8081`、`https://github.com/boarnasia/trial-wp-wp1` へのリンクが含まれる

#### Scenario: ログインリンク
- **WHEN** wp2 の行の「WP ログイン」を選ぶ
- **THEN** `https://local.wp2.yamashita109.com/wp-login.php` が新しいタブで開く

## ADDED Requirements

### Requirement: サイト名の絞り込み
サイトの一覧は、サイト ID の部分一致（大文字・小文字を区別しない）で行を絞り込めなければならない (MUST)。絞り込みの値は URL の `site` クエリに残し、再読み込みしても保たれなければならない (MUST)。一致するサイトがない場合は、その旨を表示しなければならない (MUST)。

#### Scenario: 絞り込む
- **WHEN** 絞り込みの入力欄に `2` を入れる
- **THEN** wp2 の行だけが表示され、URL に `?site=2` が付く

#### Scenario: 一致しない
- **WHEN** 絞り込みの入力欄に `wp9` を入れる
- **THEN** サイトの行は表示されず、一致するサイトがない旨が表示される

### Requirement: DB 接続情報の表示
ダッシュボードは、共有インフラの欄に DB 接続情報（ホスト:ポート、root のパスワード、共用ユーザー名とそのパスワード）を表示しなければならない (MUST)。値は wp-main の `.env` からリクエストのたびに読み込まなければならない (MUST)。ホストは `127.0.0.1`、ポートは `MYSQL_PORT`（未設定なら 3306）、共用ユーザー名は `DB_USER`（未設定なら `wordpress`）としなければならない (MUST)。パスワードは既定で伏せ字にし、一覧ページの HTML に値を含めてはならない (MUST NOT)。表示またはコピーを選んだときにだけ `GET /api/db/{account}/password`（`account` は `root` または `user`）で取得し、レスポンスをキャッシュさせてはならない (MUST NOT)。`DB_ROOT_PASSWORD` または `DB_PASSWORD` が未設定の場合は、その欄に未設定と表示し、表示とコピーを無効にしなければならない (MUST)。値が `change-me` のままの場合は、初期値のままである旨を警告しなければならない (MUST)。LAN 公開中もパスワードの取得は有効としなければならない (MUST)。

#### Scenario: 既定で伏せる
- **WHEN** wp-main の `.env` に `DB_ROOT_PASSWORD` がある状態でダッシュボードを開く
- **THEN** `127.0.0.1:3306` が表示され、root のパスワードは伏せ字で、ページの HTML にその値は含まれない

#### Scenario: root のパスワードを表示する
- **WHEN** root のパスワードの表示ボタンを選ぶ
- **THEN** `.env` の `DB_ROOT_PASSWORD` の値が表示され、API のレスポンスに `Cache-Control: no-store` が付く

#### Scenario: ポートを変えている
- **WHEN** wp-main の `.env` に `MYSQL_PORT=13306` がある状態でダッシュボードを開く
- **THEN** `127.0.0.1:13306` が表示される

#### Scenario: パスワードが未設定
- **WHEN** wp-main の `.env` に `DB_PASSWORD` がない状態でダッシュボードを開く
- **THEN** 共用ユーザーのパスワード欄に未設定と表示され、表示とコピーは無効になり、`GET /api/db/user/password` は 404 を返す

### Requirement: 共有 MySQL の状態の表示
ダッシュボードは、共有インフラの欄に `wp-mysql` の状態を、ページを開くたびに Docker から取得して表示しなければならない (MUST)。healthy なら「起動中」、起動しているが healthy でなければ「処理中」、停止しているか存在しなければ「停止中」、Docker に接続できなければ「取得不可」としなければならない (MUST)。共有 MySQL の起動・停止のボタンを置いてはならない (MUST NOT)。

#### Scenario: 起動中
- **WHEN** `wp-mysql` が healthy の状態でダッシュボードを開く
- **THEN** 共有インフラの欄に「起動中」が表示され、起動・停止のボタンはない

#### Scenario: Docker に接続できない
- **WHEN** Docker Desktop が停止している状態でダッシュボードを開く
- **THEN** HTTP 200 が返り、共有インフラの欄に「取得不可」が表示される

### Requirement: 環境バージョンの表示
ダッシュボードは、ヘッダーにインストール済みの環境バージョンを表示しなければならない (MUST)。最新の環境バージョンより古い場合は、`uv run manage.py devenv migrate` が必要な旨を添えなければならない (MUST)。

#### Scenario: 最新
- **WHEN** 環境バージョン 6 で、最新の migration も 6 の状態でダッシュボードを開く
- **THEN** ヘッダーに `環境 v6` が表示される

#### Scenario: 古い
- **WHEN** 環境バージョン 5 で、最新の migration が 6 の状態でダッシュボードを開く
- **THEN** ヘッダーに `環境 v5` と、migrate が必要な旨が表示される

### Requirement: 開発セッションの終了
ダッシュボードは、ヘッダーの右端に開発セッションの終了ボタンを表示しなければならない (MUST)。ボタンを選ぶと確認を表示し、確認した場合にだけ `POST /session/shutdown` を送らなければならない (MUST)。要求は CSRF トークンを検証しなければならない (MUST)。サーバーは `uv run manage.py serve down` と同じ処理を、ダッシュボードのプロセスから切り離した子プロセスで始め、終わりを待たずに応答しなければならない (MUST)。wp-main の `.env` の `PROXY_BIND_ADDRESS` が `127.0.0.1` 以外の場合は、ボタンを表示してはならず (MUST NOT)、要求を 403 で拒否しなければならない (MUST)。

#### Scenario: 確認して終了する
- **WHEN** 終了ボタンを選び、確認で「終了する」を選ぶ
- **THEN** `serve down` が切り離したプロセスで始まり、画面に開発セッションを終了した旨と `uv run manage.py serve up` の案内が表示される

#### Scenario: 確認で取り消す
- **WHEN** 終了ボタンを選び、確認で「キャンセル」を選ぶ
- **THEN** 要求は送られず、開発セッションは続く

#### Scenario: LAN に公開している
- **WHEN** wp-main の `.env` に `PROXY_BIND_ADDRESS=0.0.0.0` がある状態でダッシュボードを開く
- **THEN** 終了ボタンは表示されず、`POST /session/shutdown` は 403 を返し、`serve down` は始まらない

### Requirement: 静的ファイルのビルドと配布
ダッシュボードの CSS と JS は、`src/wp_main/dashboard/frontend/` のソースから bun・Vite・Tailwind CSS でビルドし、`src/wp_main/dashboard/static/dist/` に固定のファイル名（`dashboard.css`・`dashboard.js`）で出力しなければならない (MUST)。出力は git で管理し、ダッシュボードを動かすだけの利用者に Node や bun を要求してはならない (MUST NOT)。

#### Scenario: bun のない環境
- **WHEN** bun も Node もない環境で `uv sync` の後に `uv run manage.py serve up` を実行し、ダッシュボードを開く
- **THEN** スタイルの当たった画面が表示される

#### Scenario: ソースを変えてビルドする
- **WHEN** `frontend/main.css` を変えて `bun run build` を実行する
- **THEN** `static/dist/dashboard.css` が書き換わり、ソースと出力のずれを確かめるテストが通る
