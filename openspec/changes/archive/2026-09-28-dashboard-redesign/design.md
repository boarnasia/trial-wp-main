## Context

ダッシュボードは Django のテンプレート 1 枚と、手書きの `dashboard.css`・`dashboard.js` で動いている。静的ファイルは whitenoise が app の `static/` から直接配り、`collectstatic` はしていない。利用者は `uv sync` だけで導入し、Node は使っていない。デザインは Artifact のキャンバス「wp-main ダッシュボード 3 案」の案 C を正とする。

## Goals / Non-Goals

**Goals:**
- 案 C の画面（ダッシュボードのページ）を実装する。
- DB 接続情報を、サイトの管理者パスワードと同じ扱いで表示する。
- 見た目を Tailwind で書けるようにし、利用者には Node と bun を要求しない。

**Non-Goals:**
- WordPress メニューとプラグイン横断リスト（別の change）。
- HMR や django-vite による開発サーバーの統合。
- 認証の追加。

## Decisions

### ビルド
- bun をパッケージマネージャーと実行環境に使う。`bun run build` は `vite build`、`bun run dev` は `vite build --watch`。どちらも `--bun` で bun の実行環境で動かす。
- Tailwind v4 を `@tailwindcss/vite` で組み込み、設定は `frontend/main.css` の `@theme` に書く。ライト・ダークの色は `:root` の CSS 変数に置き、`@theme inline` から参照する。
- 出力は `src/wp_main/dashboard/static/dist/dashboard.css` と `dashboard.js` の固定の名前にする。ハッシュも manifest も使わない。キャッシュは whitenoise の既定（ハッシュなしは `max-age=60`）で足りる。
- 出力は git に入れる。ソースとのずれは、bun がある環境でだけ動く pytest（一時ディレクトリにビルドして比べる）で確かめる。

### DB 接続情報
- 値は wp-main の `.env` からリクエストのたびに読む。`MYSQL_PORT` の既定は 3306、`DB_USER` の既定は `wordpress`（compose と同じ）。
- パスワードの API は `GET /api/db/{account}/password`（`account` は `root` か `user`）。`Cache-Control: no-store` を付ける。値が `change-me` のままなら画面に警告を出す。
- wp-main の置き場所は、e2e で一時ディレクトリを使えるよう、環境変数 `WP_MAIN_DIR` で差し替えられるようにする（既定は `MAIN_DIR`）。

### 開発セッションの終了
- `POST /session/shutdown`（CSRF 必須）。`serve down` はダッシュボードの gunicorn 自身も止めるため、`start_new_session=True` の子プロセスで起動し、終わりを待たずに 202 を返す。出力は `serve.log` に追記する。
- LAN 公開中（`proxy_is_public()`）はボタンを出さず、要求は 403 にする。
- 確認は `<dialog>` で行い、終了後は画面を「開発セッションを終了しました」の表示に置き換える。

### その他
- GitHub のリンクは `config.SITES` の `remote`（`git@github.com:owner/repo.git`）から `https://github.com/owner/repo` を作る。
- 環境バージョンは `versioning.installed_version()`。最新より古ければ、バッジに migrate が必要な旨を添える。
- サイトの絞り込みはブラウザで行い、値は URL の `?site=` に残す。

### e2e
- `e2e/dashboard.test.ts` を `bun test` で動かす。`beforeAll` で一時ディレクトリにサイトと wp-main の `.env` を作り、`DJANGO_DB_PATH` を一時ファイルにして `migrate` と `runserver --noreload` を起動する。Docker には触れない（状態は取れなくても画面は出る）。

## Risks / Trade-offs

- ビルドした成果物のコミットを忘れる → ずれの pytest で検出する。bun がない環境ではそのテストは skip になる。
- `serve down` の子プロセスが失敗しても画面には出ない → `serve.log` に残し、画面の文言で `serve logs` を案内する。
- `Bun.WebView` は bun 1.4 系の新しい API → e2e はリポジトリの `bun` の版を `.prototools` で固定する。
