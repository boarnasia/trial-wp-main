## 1. バージョンの記録

- [x] 1.1 `trust.save_state` を、既存のキーを保つ `update_state(**values)` に置き換え、CA の SHA-1 と `env_version` が互いを消さないことを pytest で確認する
- [x] 1.2 `src/wp_main/versioning.py` に `installed_version()`（`env_version` → サイトのディレクトリがあれば 1 → `None`）を実装し、3 つの判定を pytest で確認する
- [x] 1.3 `src/wp_main/migrations/` パッケージと `discover()`、`latest_version()` を実装する。番号の重複・欠番・`VERSION` とファイル名の不一致がエラーになることを、テスト用の migration パッケージで確認する

## 2. migrate コマンド

- [x] 2.1 `dev-env:migrate`（`--auto`、`--yes`、`--dry-run`、`--root`）を実装する。未導入・最新・コードより新しい・未適用あり、の 4 つの状態の表示と終了コードを pytest で確認する
- [x] 2.2 migration を順に実行し、1 つ成功するごとに `env_version` を更新する。途中で失敗したときに手前のバージョンで止まることを pytest で確認する
- [x] 2.3 `--auto` の条件（sudo、破壊的な操作、`docker info`）を実装し、条件を満たさないときに何も実行せず終了コード 0 になることを pytest で確認する
- [x] 2.4 破壊的な migration の確認プロンプトと `--yes`、sudo が必要な migration を端末なしで実行したときの中断を実装し、pytest で確認する

## 3. install / uninstall / 警告 / check-health

- [x] 3.1 install の最初に導入済みのバージョンを判定し、新しく作る環境にだけ最新のバージョンを記録する。既存の環境で古い場合は migrate を促す。`tests/test_install.py` に両方のケースを追加する
- [x] 3.2 install での `core.hooksPath` の設定（未設定なら設定、`.githooks` ならそのまま、別の値なら警告）と、uninstall での解除（`.githooks` のときだけ）を実装し、pytest で 3 つの分岐と解除を確認する
- [x] 3.3 `@app.callback()` で古い環境の警告を標準エラー出力に出す。除外するコマンドでは出ないこと、警告が出てもコマンドが実行されることを CliRunner で確認する
- [x] 3.4 check-health に `config.version` を追加する（一致で OK、古ければ WARN、新しければ FAIL、未導入で FAIL）。`tests/test_health.py` に 4 ケースを追加する

## 4. git のフック

- [x] 4.1 `.githooks/post-merge` と `.githooks/post-rewrite` を作り、実行権限を付ける。`sh -n` で構文を確認し、`git ls-files -s .githooks` で mode が 100755 であることを確認する
- [x] 4.2 スクラッチの clone で、テスト用の migration（sudo なし）を含むコミットを `git pull`、`git pull --rebase` の両方で取り込み、フックによって `env_version` が更新されることを確認する。テスト用の migration はコミットしない

## 5. ドキュメントと実環境での確認

- [x] 5.1 README に、環境バージョン・`dev-env:migrate`・フック・migration の書き方（冪等に書く規約、`REQUIRES_SUDO`、`DESTRUCTIVE`）を追記する
- [x] 5.2 このマシンで `uv run cli dev-env:check-health` を実行し、`config.version` が OK（バージョン 1）になること、`uv run cli dev-env:migrate` が「最新」と表示して終了コード 0 になることを確認する
- [x] 5.3 `git config core.hooksPath .githooks` を設定した後（または install の再実行後）に `git pull` し、フックが動いてエラーにならないことを確認する
