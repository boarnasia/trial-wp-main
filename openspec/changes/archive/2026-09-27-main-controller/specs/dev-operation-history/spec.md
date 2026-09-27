## MODIFIED Requirements

### Requirement: 記録する操作と内容
CLI は、`devenv install`・`devenv migrate`・`devenv check-health` の実行が終わったときに、その操作を 1 件の履歴として記録しなければならない (MUST)。ダッシュボードは、サイトの起動・停止が終わったときに、その操作を 1 件の履歴として記録しなければならない (MUST)。`serve` は、開発セッションの開始時と終了時に行ったサイトの起動・停止を、サイトごとに 1 件の履歴として記録しなければならない (MUST)。履歴には、コマンド名、指定されたオプション、開始日時、終了日時、終了コード、成否、結果の要約を含めなければならない (MUST)。サイトの起動・停止のコマンド名は `site-start`・`site-stop` とし、オプションにサイト ID と操作の出どころ（ダッシュボードまたは `serve`）を含めなければならない (MUST)。結果の要約は、`devenv migrate` では移行前と移行後の環境バージョン、`devenv check-health` では判定ごとの件数、失敗した場合はエラーの内容としなければならない (MUST)。`--dry-run` を指定した実行、何も適用しなかった `devenv migrate`（`--auto` で条件を満たさなかった場合を含む）、`devenv uninstall`、`serve` の実行そのものは記録してはならない (MUST NOT)。履歴に `.env` の値（パスワード、トークンなど）を含めてはならない (MUST NOT)。

#### Scenario: migrate を記録する
- **WHEN** 環境バージョン 4 の環境で、migration 5 を適用する `devenv migrate` が成功する
- **THEN** コマンド名 `migrate`、終了コード 0、成功、要約 `4 → 5` の履歴が 1 件記録される

#### Scenario: check-health を記録する
- **WHEN** FAIL が 1 件ある状態で `devenv check-health` を実行する
- **THEN** 終了コード 1、失敗、判定ごとの件数を要約に持つ履歴が 1 件記録される

#### Scenario: サイトの停止を記録する
- **WHEN** ダッシュボードから wp1 を停止する
- **THEN** コマンド名 `site-stop`、オプションにサイト ID `wp1` と出どころのダッシュボード、成功の履歴が 1 件記録される

#### Scenario: serve によるサイトの起動と停止を記録する
- **WHEN** `serve --site=wp1` を実行し、wp1 が起動した後に Ctrl-C を押す
- **THEN** 出どころが `serve` の `site-start` と `site-stop` の履歴が wp1 について 1 件ずつ記録され、`serve` の実行そのものの履歴は記録されない

#### Scenario: 何もしなかった migrate は記録しない
- **WHEN** 環境バージョンが最新の状態で `devenv migrate --auto` を実行する
- **THEN** 履歴は記録されない

#### Scenario: dry-run は記録しない
- **WHEN** `devenv install --dry-run` を実行する
- **THEN** 履歴は記録されない
