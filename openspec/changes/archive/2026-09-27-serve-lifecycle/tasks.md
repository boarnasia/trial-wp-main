## 1. 開発セッションの記録と共有インフラの停止

- [x] 1.1 `.local/serve.pid` の flock による開発セッションの判定（取得・状態の書き込み・非ブロッキングの確認・古いファイルの削除）を実装し、別プロセスが flock を持つ間は「動いている」、プロセスが死んだ後は「動いていない」と判定されることをテストで確かめる
- [x] 1.2 `power.stop_infra`（`docker compose down --remove-orphans`、`-v` なし）を追加し、実行されるコマンドに `-v` が含まれないことをテストで確かめる
- [x] 1.3 `session.end` に「共有インフラも止めるか」を加え、サイトを `operate` で止めた後に `stop_infra` が呼ばれること、入れ替えのときは呼ばれないことを test_session で確かめる

## 2. ログ

- [x] 2.1 `processes.supervise` の出力の中継を、`.local/logs/<名前>.log` への追記と、前面のときだけの端末への表示に分ける。ログが書かれ、端末に出ないモードがあることを test_processes で確かめる
- [x] 2.2 セッション開始時に `*.log` を `*.log.1` に置き換える処理を実装し、2 回目の開始で前回の内容が `.log.1` に残ることをテストで確かめる
- [x] 2.3 監督プロセス自身の出力（サイトの起動・停止・エラー）を `serve.log` にも書き、`session.begin` の出力が `serve.log` に残ることをテストで確かめる

## 3. serve のサブコマンド

- [x] 3.1 `serve` を `up` / `down` / `logs` のサブコマンドに分け、サブコマンドなし（`serve --site=wp1` を含む）では何も起動せずに `serve up` を案内して終了コード 1 になることをテストで確かめる
- [x] 3.2 前面の `serve up` を、監督の本体（flock の取得 → ポート確認 → django:migration → 共有インフラ → サイト → ホストのプロセス → `ready` の書き込み → 終了で `session.end`）を呼ぶ形にする。Ctrl-C と異常終了で `stop_infra` が呼ばれ、共有インフラの失敗で起動したものが止まることをテストで確かめる
- [x] 3.3 SIGTERM（全体の終了）と SIGUSR1（共有インフラを残す入れ替え）を監督プロセスで区別し、それぞれ `stop_infra` が呼ばれる・呼ばれないことをテストで確かめる
- [x] 3.4 `serve up` の開始時に既存のセッションがあれば SIGUSR1 を送り、flock の解放を待ってから始める。既存のセッションがあるときにシグナルが送られて待つことを、偽の PID ファイルと flock を使うテストで確かめる
- [x] 3.5 `serve up --detach` を、隠しサブコマンドで自分を `start_new_session=True` で起動し直す形で実装する。親は `ready` で URL を表示して 0、子の終了で `serve.log` の末尾を表示して 1 を返す。子の起動方法と両方の結果をテストで確かめる
- [x] 3.6 監督プロセスで、ホストのプロセスの起動後にダッシュボードのポートの応答を最大 120 秒待ち、応答しなければセッションを終えて 1 で終わることをテストで確かめる。デタッチの完了時に、失敗したサイトを表示することも確かめる
- [x] 3.7 `serve down` を実装する。手順は次のとおり。
  1. セッションがあれば SIGTERM を送り、flock の解放を最大 300 秒待つ。超えたら SIGKILL を送る。
  2. 残っているサイトを止め、`stop_infra` を呼ぶ。
  3. 古い PID ファイルを消す。
  4. 何もなければ「開発セッションはありません」と表示する。

  4 つの状態（セッションあり・古いファイル・コンテナだけ残る・何もない）がいずれも 0 で終わることをテストで確かめる。
- [x] 3.8 `serve logs [-f] [--tail N] [名前...]` を実装する。ホストのプロセスのログファイルと `docker compose logs --no-log-prefix` を束ね、`名前 | 行` で出す。名前の対応（`wp1` を `wp1-wordpress` に）、`--tail` の受け渡し、存在しない名前のエラーと一覧をテストで確かめる
- [x] 3.9 `devenv serve` の案内を `serve up` に替え、test_cli_legacy などの既存のテストが通ることを確かめる

## 4. check-health・install・migration・uninstall

- [x] 4.1 `check-health` に開発セッションの判定を加え、セッションの外では共有インフラとダッシュボードのプロセスの項目を SKIP にする（理由に `serve up` を添える）。セッション中に応答しないダッシュボードは FAIL にする。test_health で「セッションの外で exit 0、共有インフラは SKIP」「セッション中に `wp-mysql` 停止で FAIL」を確かめる
- [x] 4.2 `devenv install` の最後に、開発セッションの外なら `stop_infra` を呼ぶ（失敗しても止める）。案内を `serve up --site=all` にする。test_install で、セッションの外なら止まり、セッション中なら止まらないことを確かめる
- [x] 4.3 migration 6 の最後に、開発セッションの外なら `stop_infra` を呼び、案内を `serve up --site=all` にする。test_m0006 の `ups` の確認に `down` の呼び出しを加えて確かめる。migration 5 の案内を `serve up` にする
- [x] 4.4 `devenv uninstall` の「serve が動いている」判定を開発セッションの判定に替え、`serve down` を案内する。test_uninstall が通ることを確かめる

## 5. ドキュメント

- [x] 5.1 `README.md` と `templates/wp-site/README.md` の `serve --site` を `serve up` / `serve down` / `serve logs` に直す。`--detach` と、既存の環境の残った共有インフラを `serve down` で片付けられることを書く。`grep -rn "serve --site" README.md templates src` で旧表記が残らないことを確かめる
- [x] 5.2 wp-wp1・wp-wp2 の README の `serve --site` を `serve up --site` に直してコミットする。`main-controller` の PR は既にマージされていたため、`serve-lifecycle` ブランチで新しい PR にする

## 6. 確認

- [x] 6.1 `uv run pytest` が全件通ることを確かめる
- [x] 6.2 実環境で次の順に確かめる。
  1. `serve up --detach --site=wp1` を実行し、URL が出て戻ることを確かめる。
  2. `serve logs -f` で `dashboard` と `wp1` のログが流れることを確かめる。
  3. `check-health` がすべて OK になることを確かめる。
  4. `serve up --detach --site=wp2` で入れ替えても `wp-mysql` が止まらないことを確かめる。
  5. `serve down` で `docker ps` に wp 系のコンテナが残らないことを確かめる。
  6. `check-health` が SKIP だけで exit 0 になることを確かめる。
  7. 前面の `serve up --site=wp1` を Ctrl-C で止め、共有インフラも止まることを確かめる。
  8. もう一度 `serve up --site=wp1` を実行し、投稿が残っていることを確かめる。
