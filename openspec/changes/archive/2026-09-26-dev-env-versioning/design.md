## Context

- マシンごとの状態は `.local/dev-env-state.json` にある（`trust.load_state` / `save_state`）。今は `ca_sha1` だけを持ち、`--skip-trust` で install した場合はファイル自体がない。
- 今動いている環境（このマシン）は `env_version` を持たない。wp-main の `core.hooksPath` は未設定で、`.git/hooks` に独自のフックもない。
- 外部コマンドは `Runner` を通り、テストでは `FakeRunner` に置き換えられる。check-health は `health.Check` の一覧で項目を組み立てる。
- `git pull --rebase`（または `pull.rebase=true`）では post-merge フックが動かず、post-rewrite フックが引数 `rebase` で動く。

## Goals / Non-Goals

**Goals:**
- pull しただけで、安全な migration が自動で適用される。
- 自動で実行できない migration があるときは、何もせずに実行方法を知らせる。
- migration を追加する手順が、ファイルを 1 つ置くだけで済む。

**Non-Goals:**
- migration の後戻り（down）。困ったときは uninstall してから install し直す。
- サイトリポジトリ（wp-wp1 / wp-wp2）の中身の移行。サイトの変更は、各リポジトリのコミットとして配る。
- 実際の migration の追加。この change では仕組みと基準のバージョン 1 だけを入れる。

## Decisions

### D1. migration は `src/wp_main/migrations/mNNNN_<名前>.py` の 1 ファイル 1 つ
各モジュールは、次の定数と関数を持つ。

```python
VERSION = 2                  # ファイル名の番号と一致させる
DESCRIPTION = "..."          # 実行時に表示する説明
REQUIRES_SUDO = False
DESTRUCTIVE = False          # True のときは失われるものを LOSES に書く
LOSES = ""
def up(ctx: MigrationContext) -> None: ...
```

`versioning.discover()` は `pkgutil.iter_modules` でパッケージを走査し、番号順に並べる。番号の重複、欠番、`VERSION` とファイル名の不一致は、読み込みの時点でエラーにする。この検査はテストでも確かめる。最新のバージョンは `max(1, 最大の番号)`。バージョン 1 は基準なので、ファイルを持たない。
- 代替: YAML などで宣言的に書く。migration の中身は Docker やファイルの操作で、Python で書くほうが自然で、`Runner` とテストの仕組みもそのまま使えるため、採用しない。
- `MigrationContext` は、`runner`、`root`、`main_dir`、`sites` を持つ。migration の中で `ctx.root` の下にある各サイトのディレクトリへ書き込まないことは、レビューで確認する。書き込みをコードで禁止することはしない。

### D2. 導入済みのバージョンの判定
`installed_version()` は次の順に判定する。
1. state ファイルに `env_version` があれば、その値
2. なければ、どちらかのサイトのディレクトリがあれば 1（既存の環境）
3. どちらもなければ `None`（未導入）

`save_state` は既存のキーを保ったまま書き込む。今は trust が state ファイル全体を上書きしているので、バージョンと CA の SHA-1 が互いを消さないよう、`update_state(**values)` にまとめる。

### D3. install での記録
`devenv.install` の最初（clone より前）に `installed_version()` を呼ぶ。
- 結果が `None` なら、install が完了した時点で `env_version = latest` を記録する。
- 値があれば記録しない。その値が最新より古い場合は、install の最後に migrate を促すメッセージを出す。

install の途中で失敗したときは記録しない。この場合、サイトのディレクトリが残るので、次に実行したときは既存の環境（バージョン 1）とみなされる。latest が 1 である間はこれで問題ない。latest が 2 以上になった後に、install の途中で失敗して再実行すると、未適用の migration が走ることになる。migration は冪等に書くことを規約にし、README に明記する。

### D4. `dev-env:migrate` の流れ
1. 導入済みのバージョンと最新のバージョンを比べる。未導入、最新、コードより新しい、の 3 つの場合はそれぞれメッセージを出して終わる（spec のとおり）。
2. `--auto` の場合は、自動実行の条件を満たしているかを判定する。Docker への接続は `docker info` の終了コードで確かめる。満たしていなければ、理由とコマンドを表示して終了コード 0 で終わる。
3. `--auto` でなく、破壊的な migration が含まれる場合は、`LOSES` を表示して `typer.confirm` で確認する（`--yes` で省略できる）。
4. migration を順に `up(ctx)` し、1 つ成功するごとに `update_state(env_version=N)` を書く。
5. `--dry-run` のときは、実行する migration の一覧を表示するだけにし、state は更新しない。

sudo を必要とする migration を `--auto` なしで実行する場合は、`sys.stdin.isatty()` を確認する。端末がなければ、`up` を呼ぶ前に「端末で実行してください」と表示して止める。以前 `!` で install を実行したときの失敗を繰り返さないためである。

### D5. git のフック
`.githooks/post-merge` と `.githooks/post-rewrite` は POSIX sh で書き、実行権限を付けてコミットする。

```sh
#!/bin/sh
# post-rewrite は amend でも呼ばれるため、rebase のときだけ動かす
[ "$1" = "rebase" ] || exit 0          # post-rewrite のみ
cd "$(git rev-parse --show-toplevel)" || exit 0
command -v uv >/dev/null 2>&1 || exit 0
uv run --quiet cli dev-env:migrate --auto || true
exit 0
```

- install は、`git config --local --get core.hooksPath` が未設定なら `.githooks` を設定する。既に `.githooks` なら何もしない。別の値なら警告を出す。
- uninstall は、値が `.githooks` のときだけ `git config --local --unset core.hooksPath` を実行する。
- 代替: `.git/hooks/` にフックをコピーする。コピーした後にフックを更新しても反映されないため、採用しない。`core.hooksPath` にすると `.git/hooks` の独自フックが無効になるが、現状は独自フックがないことを確認済みで、既に値がある場合は変更しない。

### D6. 古い環境での警告
typer の `@app.callback()` で、`ctx.invoked_subcommand` が除外対象（`dev-env:migrate`、`dev-env:check-health`、`help`、`version`）でなければ `installed_version()` と最新を比べる。古ければ `typer.secho(..., err=True)` で警告を出す。state ファイルを読むだけなので、コストは無視できる。コールバックの時点ではサブコマンドの `--root` を解析していないため、判定には既定のルート（wp-main の親）を使う。`env_version` が記録されていれば、ルートは判定に影響しない。判定自体が失敗した場合（migration のファイルが壊れているなど）は、その旨を警告として出し、コマンドは続ける。

### D7. check-health の項目
`config` グループに `config.version` を追加する。前提の項目はない。未導入のときは SKIP にせず、FAIL（「未導入。dev-env:install を実行」）とする。

## Risks / Trade-offs

- [フックの中の `uv run` が遅い、または失敗する] → `--quiet` で出力を抑える。失敗しても `|| true` と `exit 0` で pull を妨げない。
- [GUI の git クライアントからの pull] → フックは端末なしで動く。`--auto` は sudo を必要とする migration を実行しないので、パスワード待ちで止まることはない。
- [migration が冪等でない] → 途中で失敗して再実行するとおかしくなる可能性がある。規約として README に書き、各 migration のテストで 2 回実行しても結果が同じことを確かめる。
- [コードより新しい環境（古いコミットをチェックアウトしたとき）] → migrate は実行を拒否する。check-health はこの状態を FAIL にする。
- [複数のターミナルで同時に migrate] → 開発者 1 人のマシンの操作なので、ロックは入れない。

## Migration Plan

- このマシンの環境は `env_version` を持たないため、D2 のとおりバージョン 1 になり、最新（1）と一致する。
- 導入後に `uv run cli dev-env:install` を一度実行するか、手動で `git config core.hooksPath .githooks` を設定して、フックを有効にする。README に記載する。
