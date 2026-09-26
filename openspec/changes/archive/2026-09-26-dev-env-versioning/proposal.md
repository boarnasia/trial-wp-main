## Why

wp-main の変更には、コードを pull するだけでは反映されないものがある（例: ボリューム名の変更、`.env` への変数の追加、hosts のエントリの追加）。今は、各開発者の環境がどの時点の構成で作られたかが分からず、必要な作業を手で伝えるか、uninstall して install し直すしかない。環境にバージョンを持たせ、pull した後に必要な移行を自動で実行できるようにする。

## What Changes

- 環境バージョンを導入する。
  - 最新のバージョン: コードに含まれる migration の最大番号（整数。pyproject のバージョンとは独立）。
  - 導入済みのバージョン: マシンごとの `.local/dev-env-state.json` の `env_version`（git の管理外）。
  - `env_version` がない既存の環境はバージョン 1 とみなす。現在の構成をバージョン 1（基準）とする。
- `uv run cli dev-env:migrate` を追加する。未適用の migration を番号順に実行し、1 つ終わるごとに `env_version` を更新する。失敗したら、その migration の手前で止まる。migration は前進のみで、後戻りは用意しない。
  - `--auto`: 自動で実行できる場合だけ実行し、できない場合は手動で実行するコマンドを表示する。常に終了コード 0 で終わる（git のフックから使う）。
- migration は、環境のリソース（ボリューム、ネットワーク、hosts、`.env` への変数の追加、CA、コンテナ）だけを変更する。サイトリポジトリの中身は変更しない。
- git のフック `.githooks/post-merge` と `.githooks/post-rewrite` を追加する。`git pull`（merge と rebase の両方）の後に `dev-env:migrate --auto` を実行する。`dev-env:install` は `core.hooksPath` を設定し、`dev-env:uninstall` は設定を戻す。
- `dev-env:install` は、新しく作る環境に最新のバージョンを記録する。migration は実行しない。
- 導入済みのバージョンが古い場合、CLI の各コマンドは実行の最初に警告を表示する。
- `dev-env:check-health` に環境バージョンの項目を加える（古ければ WARN、コードより新しければ FAIL）。

## Capabilities

### New Capabilities
- `dev-env-versioning`: 環境バージョンの記録と比較、migration の実行と自動実行の条件、git のフックの導入と解除、古い環境での警告。

### Modified Capabilities
- `dev-env-cli`: 「CLI エントリポイント」要件に `dev-env:migrate` を追加する。
- `dev-env-health`: 「確認項目と判定」要件に環境バージョンの項目を追加する。

## Impact

- 新規: `src/wp_main/versioning.py`、`src/wp_main/migrations/`（基準のバージョン 1 のみ。実際の migration はこの change では追加しない）、`.githooks/post-merge`、`.githooks/post-rewrite`、`tests/test_versioning.py`
- 変更: `src/wp_main/cli.py`（コマンドの追加、古い環境での警告）、`src/wp_main/devenv.py`（install と uninstall でのバージョンとフックの扱い）、`src/wp_main/health.py`（項目の追加）、`README.md`
- wp-main の git 設定 `core.hooksPath` を変更する（リポジトリ単位の設定のみ。グローバル設定は変更しない）。
