## MODIFIED Requirements

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
