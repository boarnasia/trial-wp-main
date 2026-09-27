## 1. ビルドの仕組み

- [x] 1.1 `.prototools` に bun の版を固定し、`package.json`（`packageManager`・`build`・`dev`・`test:e2e`）、`vite.config.js`、`frontend/main.css`・`main.js` を作る。`bun run build` で `static/dist/dashboard.css` と `dashboard.js` ができることを確かめる
- [x] 1.2 bun がある環境で、一時ディレクトリにビルドした結果と `static/dist/` が一致することを確かめる pytest を加える（bun がなければ skip）
- [x] 1.3 旧 `static/dashboard.css` と `dashboard.js` を削除し、テンプレートと静的ファイルのテストを `dist/` に合わせる

## 2. データと API

- [x] 2.1 `data.py` に DB 接続情報（ホスト・ポート・ユーザー・パスワードの有無・初期値のままか）の読み込みを加え、既定値・未設定・`change-me` をテストで確かめる
- [x] 2.2 `GET /api/db/{account}/password` を加え、`no-store`・未設定の 404・未知の account の 404・再読み込みをテストで確かめる
- [x] 2.3 共有 MySQL の状態（起動中・処理中・停止・取得不可）を求める関数を加え、inspect の結果ごとの表示をテストで確かめる
- [x] 2.4 GitHub の URL と環境バージョン（古いときの案内を含む）をテストで確かめる

## 3. 画面

- [x] 3.1 `index.html` を案 C で作り直す（ヘッダー・共有インフラ・サイト・操作履歴）。既存のテストが示す振る舞い（パスワードを HTML に含めない、`.env` がないサイト、操作履歴）が変わらないことを確かめる
- [x] 3.2 サイト名の絞り込み（`?site=` に保持）を `main.js` に実装する
- [x] 3.3 `POST /session/shutdown` と確認ダイアログを実装し、CSRF・LAN 公開中の 403 と非表示・子プロセスの起動方法をテストで確かめる

## 4. e2e とドキュメント

- [x] 4.1 `e2e/dashboard.test.ts` に 3 本（CSS の適用、DB パスワードの伏せ字と表示の切り替え、コピーのトースト）を書き、`bun run test:e2e` で通ることを確かめる
- [x] 4.2 README に、DB 接続情報・終了ボタン・見た目の変え方（`bun install` と `bun run dev` / `build`、成果物のコミット）・e2e の実行方法を書く
