# dev-env-versioning Specification

## Purpose
開発者ごとの環境がどの構成で作られたかを記録し、wp-main を更新したときに必要な移行を安全に、できるだけ自動で適用する。

## Requirements

### Requirement: 環境バージョンの記録
CLI は、コードに含まれる migration の最大番号を最新のバージョンとして扱わなければならない (MUST)。導入済みのバージョンは `.local/dev-env-state.json` の `env_version` に記録しなければならない (MUST)。`env_version` がなく、サイトリポジトリのディレクトリが存在する環境は、バージョン 1 とみなさなければならない (MUST)。

#### Scenario: 既存の環境
- **WHEN** `env_version` のない state ファイルと `{root}/wp-wp1` がある状態で、バージョンを確認する
- **THEN** 導入済みのバージョンは 1 と判定される

#### Scenario: 新しく作る環境
- **WHEN** サイトリポジトリのディレクトリがない状態で `devenv install` を実行し、完了する
- **THEN** `env_version` には最新のバージョンが記録され、migration は実行されない

#### Scenario: 既存の環境での install の再実行
- **WHEN** 導入済みのバージョンが最新より古い環境で `devenv install` を再実行する
- **THEN** `env_version` は変更されず、`devenv migrate` の実行を促すメッセージが表示される

### Requirement: migration の実行
`devenv migrate` は、導入済みのバージョンより大きい番号の migration を番号順に実行し、1 つ成功するごとに `env_version` をその番号に更新しなければならない (MUST)。migration が失敗した場合は、以降の migration を実行せずに、失敗した migration と原因を表示し、0 以外の終了コードで終わらなければならない (MUST)。migration は環境のリソースだけを変更し、サイトリポジトリ内のファイルを変更してはならない (MUST NOT)。

#### Scenario: 未適用の migration を適用する
- **WHEN** 導入済みのバージョンが 1、最新のバージョンが 3 の状態で `devenv migrate` を実行する
- **THEN** migration 2 と 3 がこの順に実行され、`env_version` は 3 になる

#### Scenario: 途中で失敗する
- **WHEN** migration 2 は成功し、migration 3 が失敗する
- **THEN** `env_version` は 2 のままになり、migration 3 の名前と原因が表示され、終了コードは 1 になる

#### Scenario: 最新の状態
- **WHEN** 導入済みのバージョンが最新と同じ状態で実行する
- **THEN** 何も実行されず、最新であることが表示され、終了コード 0 で終わる

#### Scenario: コードより新しい環境
- **WHEN** 導入済みのバージョンがコードの最新のバージョンより大きい（古いコミットをチェックアウトした）状態で実行する
- **THEN** migration は実行されず、コードを更新するよう表示され、0 以外の終了コードで終わる

#### Scenario: 環境が未導入
- **WHEN** install していない状態で実行する
- **THEN** migration は実行されず、`devenv install` の実行を促すメッセージが表示される

### Requirement: 自動実行の条件
`devenv migrate --auto` は、次の条件をすべて満たす場合に限り、未適用の migration を実行しなければならない (MUST)。条件を満たさない場合は、何も変更せずに理由と手動で実行するコマンドを表示しなければならない (MUST)。`--auto` は常に終了コード 0 で終わらなければならない (MUST)。
- 環境が導入済みで、導入済みのバージョンが最新より古い。
- 未適用の migration のどれも、sudo を必要としない。
- 未適用の migration のどれも、データを失う操作（破壊的な操作）を含まない。
- Docker に接続できる。

#### Scenario: 自動で移行できる
- **WHEN** sudo も破壊的な操作も必要としない migration だけが未適用の状態で `devenv migrate --auto` を実行する
- **THEN** migration が実行され、`env_version` が最新になる

#### Scenario: sudo が必要な migration がある
- **WHEN** 未適用の migration の 1 つが sudo を必要とする状態で `devenv migrate --auto` を実行する
- **THEN** どの migration も実行されず、`uv run manage.py devenv migrate` を端末で実行するよう表示され、終了コードは 0 になる

#### Scenario: 破壊的な migration の手動実行
- **WHEN** 破壊的な migration が未適用の状態で、`--auto` なしで `devenv migrate` を実行する
- **THEN** 失われるものが表示され、確認プロンプトで承認された場合（または `--yes` 指定時）にのみ実行される

### Requirement: git のフック
wp-main は、`git pull` の後に `devenv migrate --auto` を実行する post-merge フックと post-rewrite フックを `.githooks/` に持たなければならない (MUST)。post-rewrite フックは rebase のときだけ実行しなければならない (MUST)。フックは、失敗しても git の操作を失敗させてはならない (MUST NOT)。`devenv install` は wp-main の `core.hooksPath` を `.githooks` に設定しなければならない (MUST)。ただし、別の値が既に設定されている場合は変更せずに警告を表示しなければならない (MUST)。`devenv uninstall` は、`core.hooksPath` が `.githooks` の場合に限り設定を削除しなければならない (MUST)。

#### Scenario: pull の後に自動で移行する
- **WHEN** 自動で実行できる migration を含むコミットを `git pull` で取り込む
- **THEN** pull の後に migration が実行され、`env_version` が最新になる

#### Scenario: rebase で pull する
- **WHEN** `git pull --rebase` で同じコミットを取り込む
- **THEN** post-rewrite フックによって同じように migration が実行される

#### Scenario: 独自の hooksPath を使っている
- **WHEN** `core.hooksPath` に別のディレクトリが設定された状態で install を実行する
- **THEN** 設定は変更されず、フックを手動で組み込む方法が警告として表示される

#### Scenario: uninstall でフックを外す
- **WHEN** install で `core.hooksPath` を設定した環境で uninstall を実行する
- **THEN** wp-main の `core.hooksPath` の設定が削除される

### Requirement: 古い環境での警告
導入済みのバージョンが最新より古い場合、`devenv` のサブコマンドのうち `migrate`・`check-health`・`version` 以外は、実行の最初に標準エラー出力へ警告と `uv run manage.py devenv migrate` の実行方法を表示しなければならない (MUST)。`manage.py help` と Django 本体のコマンドは警告を表示してはならない (MUST NOT)。警告はコマンドの実行を止めてはならない (MUST NOT)。

#### Scenario: 古い環境で uninstall する
- **WHEN** 導入済みのバージョンが古い状態で `devenv uninstall --dry-run` を実行する
- **THEN** 標準エラー出力に警告が表示され、その後に uninstall の dry-run が通常どおり実行される

### Requirement: dev-env:migration と django:migration の区別と適用のタイミング
この仕様の migration（dev-env:migration）は、開発環境のリソースを移行するものであり、Django の DB スキーマを移行する django:migration とは別に扱わなければならない (MUST)。`uv run manage.py devenv migrate` の移行処理は dev-env:migration だけを実行し、django:migration を含めてはならない (MUST NOT)（移行の後に操作履歴を記録する際の適用は除く）。django:migration は、`serve` がプロセスを起動する前、`devenv install` の実行時、CLI が操作履歴を記録する前に、`.local/db.sqlite3` に対して適用しなければならない (MUST)。django:migration の実行や `env_version` の変更を、互いに相手が行ってはならない (MUST NOT)。環境バージョンは Django の DB ではなく `.local/dev-env-state.json` に記録しなければならない (MUST)。dev-env:migration は、開発セッションの外でサイトを起動したままにしてはならない (MUST NOT)。

#### Scenario: Django の migrate は環境バージョンを変えない
- **WHEN** 未適用の dev-env:migration がある状態で `uv run manage.py migrate` を実行する
- **THEN** dev-env:migration は実行されず、`env_version` は変わらない

#### Scenario: devenv migrate は DB のスキーマを移行処理に含めない
- **WHEN** 未適用の dev-env:migration がある状態で `uv run manage.py devenv migrate` を実行する
- **THEN** 未適用の dev-env:migration が実行され、`.local/dev-env-state.json` の `env_version` が最新になり、dev-env:migration の中で django:migration は実行されない

#### Scenario: serve の起動で DB を移行する
- **WHEN** 未適用の django:migration がある状態で `serve` を実行する
- **THEN** ダッシュボードが応答する前に django:migration が適用される

#### Scenario: migration の後にサイトが残らない
- **WHEN** `serve` を実行していない状態で、プロキシを作り直す migration を実行する
- **THEN** migration の後、`wp1-wordpress` と `wp2-wordpress` は停止している
