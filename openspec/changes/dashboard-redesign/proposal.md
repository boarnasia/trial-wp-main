## Why

ホストの DB クライアントから共有 MySQL につなぐとき、ポートと root のパスワードを毎回 wp-main の `.env` から探している。また、ダッシュボードの CSS は手書きの 1 ファイルで、画面を増やすたびに書き足す必要がある。案 C（インフラ台帳）のデザインで画面を作り直し、DB 接続情報を表示し、見た目は Tailwind で組み立てられるようにする。

## What Changes

- 画面を案 C のデザインで作り直す。上から、ヘッダー、共有インフラ、サイト、操作履歴の順に並べる。
- ヘッダーに、開発セッションのサイト数、環境バージョン（`環境 v6`）、ダッシュボードへのナビ、開発セッションの終了ボタンを置く。
- 共有インフラの欄に、共有 MySQL の状態と **DB 接続情報**（ホスト:ポート、root のパスワード、共用ユーザーとそのパスワード）を表示する。パスワードは既定で伏せ字にし、表示とコピーのときだけ API で取得する。
- サイトの表に GitHub の列を加え、ログインのボタンの文言を「WP ログイン」にする。サイト名で絞り込む入力欄を置く。
- 開発セッションの終了ボタンは、確認の後に `serve down` を切り離したプロセスで実行する。LAN 公開中は表示せず、要求も拒否する。
- 静的ファイルを bun + Vite + Tailwind v4 でビルドする。ビルドした CSS と JS は固定のファイル名で git に入れ、利用者には Node も bun も要らないようにする。
- `Bun.WebView` と `bun test` で e2e テストを 3 本加える。

## Capabilities

### New Capabilities
（なし）

### Modified Capabilities
- `dev-dashboard`: サイト一覧の列と絞り込み、DB 接続情報の表示と取得、共有 MySQL の状態、環境バージョン、開発セッションの終了、静的ファイルのビルドと配布。

## Impact

- コード: `src/wp_main/dashboard/`（`views.py`、`data.py`、`urls.py`、`templates/index.html`、`frontend/` を新設、`static/dist/` を新設、`static/dashboard.css` と `static/dashboard.js` を削除）
- ツール: ルートに `package.json`、`bun.lock`、`vite.config.js`、`.prototools` を追加。`e2e/` に e2e テストを追加
- テスト: `tests/test_dashboard.py`、`tests/test_site_power_views.py`、ビルドのずれを確かめるテスト
- ドキュメント: `README.md`
- 利用者: 導入手順は変わらない。見た目を変える人だけが bun を使う
- 後続: WordPress メニューとプラグイン横断リストは別の change で扱う
