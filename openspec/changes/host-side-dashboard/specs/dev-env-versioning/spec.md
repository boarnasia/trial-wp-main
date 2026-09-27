## ADDED Requirements

### Requirement: dev-env:migration と django:migration の区別と適用のタイミング
この仕様の migration（dev-env:migration）は、開発環境のリソースを移行するものであり、Django の DB スキーマを移行する django:migration とは別に扱わなければならない (MUST)。`uv run manage.py devenv migrate` の移行処理は dev-env:migration だけを実行し、django:migration を含めてはならない (MUST NOT)（移行の後に操作履歴を記録する際の適用は除く）。django:migration は、`devenv serve` がプロセスを起動する前、`devenv install` の実行時、CLI が操作履歴を記録する前に、`.local/db.sqlite3` に対して適用しなければならない (MUST)。django:migration の実行や `env_version` の変更を、互いに相手が行ってはならない (MUST NOT)。環境バージョンは Django の DB ではなく `.local/dev-env-state.json` に記録しなければならない (MUST)。

#### Scenario: Django の migrate は環境バージョンを変えない
- **WHEN** 未適用の dev-env:migration がある状態で `uv run manage.py migrate` を実行する
- **THEN** dev-env:migration は実行されず、`env_version` は変わらない

#### Scenario: devenv migrate は DB のスキーマを移行処理に含めない
- **WHEN** 未適用の dev-env:migration がある状態で `uv run manage.py devenv migrate` を実行する
- **THEN** 未適用の dev-env:migration が実行され、`.local/dev-env-state.json` の `env_version` が最新になり、dev-env:migration の中で django:migration は実行されない

#### Scenario: serve の起動で DB を移行する
- **WHEN** 未適用の django:migration がある状態で `devenv serve` を実行する
- **THEN** ダッシュボードが応答する前に django:migration が適用される

## REMOVED Requirements

### Requirement: dev-env:migration と django:migration の区別
**Reason**: django:migration を適用する場所がダッシュボードのコンテナからホスト（`devenv serve`・`devenv install`・操作履歴の記録）に移り、コンテナの起動を前提とする要件が成り立たなくなったため。
**Migration**: 「dev-env:migration と django:migration の区別と適用のタイミング」に置き換える。区別の方針（`devenv migrate` と `manage.py migrate` が互いの移行を行わない、環境バージョンは `.local/dev-env-state.json` に記録する）は変わらない。
