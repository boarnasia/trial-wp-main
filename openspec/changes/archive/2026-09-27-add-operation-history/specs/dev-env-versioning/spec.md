## MODIFIED Requirements

### Requirement: dev-env:migration と django:migration の区別
この仕様の migration（dev-env:migration）は、開発環境のリソースを移行するものであり、Django の DB スキーマを移行する django:migration とは別に扱わなければならない (MUST)。`uv run manage.py devenv migrate` は dev-env:migration だけを実行し、django:migration を実行してはならない (MUST NOT)。django:migration は、ダッシュボードのコンテナが起動するときに、コンテナ内の DB に対して実行しなければならない (MUST)。django:migration の実行や `env_version` の変更を、互いに相手が行ってはならない (MUST NOT)。環境バージョンは Django の DB ではなく `.local/dev-env-state.json` に記録しなければならない (MUST)。

#### Scenario: Django の migrate は環境バージョンを変えない
- **WHEN** 未適用の dev-env:migration がある状態で `uv run manage.py migrate` を実行する
- **THEN** dev-env:migration は実行されず、`env_version` は変わらない

#### Scenario: devenv migrate は DB を移行しない
- **WHEN** `uv run manage.py devenv migrate` を実行する
- **THEN** 未適用の dev-env:migration だけが実行され、ダッシュボードの DB のスキーマは変更されない

#### Scenario: コンテナの起動で DB を移行する
- **WHEN** 未適用の django:migration を含むダッシュボードのイメージでコンテナを起動する
- **THEN** コンテナが healthy になる前に django:migration が適用される
