# dev-operation-history Specification

## Purpose
CLI で行った開発環境の操作（構築、移行、健全性の確認）と、ダッシュボードからのサイトの起動・停止の結果を記録し、ダッシュボードで後から確認できるようにする。CLI とダッシュボードはどちらもホストで動き、同じ DB に直接書き込む。

## Requirements

### Requirement: 記録する操作と内容
CLI は、`devenv install`・`devenv migrate`・`devenv check-health` の実行が終わったときに、その操作を 1 件の履歴として記録しなければならない (MUST)。ダッシュボードは、サイトの起動・停止が終わったときに、その操作を 1 件の履歴として記録しなければならない (MUST)。`serve up` と `serve down`（前面の `serve up` の Ctrl-C を含む）は、開発セッションの開始時と終了時に行ったサイトの起動・停止を、サイトごとに 1 件の履歴として記録しなければならない (MUST)。履歴には、コマンド名、指定されたオプション、開始日時、終了日時、終了コード、成否、結果の要約を含めなければならない (MUST)。サイトの起動・停止のコマンド名は `site-start`・`site-stop` とし、オプションにサイト ID と操作の出どころ（ダッシュボードまたは `serve`）を含めなければならない (MUST)。結果の要約は、`devenv migrate` では移行前と移行後の環境バージョン、`devenv check-health` では判定ごとの件数、失敗した場合はエラーの内容としなければならない (MUST)。`--dry-run` を指定した実行、何も適用しなかった `devenv migrate`（`--auto` で条件を満たさなかった場合を含む）、`devenv uninstall`、`serve up`・`serve down`・`serve logs` の実行そのもの、共有インフラの起動・停止は記録してはならない (MUST NOT)。履歴に `.env` の値（パスワード、トークンなど）を含めてはならない (MUST NOT)。

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
- **WHEN** `serve up --site=wp1` を実行し、wp1 が起動した後に Ctrl-C を押す
- **THEN** 出どころが `serve` の `site-start` と `site-stop` の履歴が wp1 について 1 件ずつ記録され、`serve` の実行そのものと共有インフラの停止の履歴は記録されない

#### Scenario: serve down によるサイトの停止を記録する
- **WHEN** `serve up --detach --site=wp1` の後に `serve down` を実行する
- **THEN** 出どころが `serve` の `site-stop` の履歴が wp1 について 1 件記録される

#### Scenario: 何もしなかった migrate は記録しない
- **WHEN** 環境バージョンが最新の状態で `devenv migrate --auto` を実行する
- **THEN** 履歴は記録されない

#### Scenario: dry-run は記録しない
- **WHEN** `devenv install --dry-run` を実行する
- **THEN** 履歴は記録されない

### Requirement: 記録の送信と失敗時の扱い
CLI は、履歴をダッシュボードを経由せずに DB へ直接書き込まなければならない (MUST)。ダッシュボードが起動していなくても記録できなければならない (MUST)。DB のスキーマが最新でない場合、CLI は記録の前に django:migration を適用しなければならない (MUST)。記録に失敗した場合、CLI は標準エラー出力に警告を表示し、コマンド本来の出力と終了コードを変えてはならない (MUST NOT)。

#### Scenario: ダッシュボードが停止している
- **WHEN** `serve` を実行していない状態で `devenv check-health` を実行する
- **THEN** 履歴が記録され、次に `serve` でダッシュボードを開くと表示される

#### Scenario: DB がまだない
- **WHEN** `.local/db.sqlite3` がない状態で `devenv check-health` を実行する
- **THEN** `.local/db.sqlite3` が作られ、履歴が記録される

#### Scenario: CA を信頼登録していない環境
- **WHEN** `--skip-trust` で install した環境で `devenv check-health` を実行する
- **THEN** 履歴は記録される

#### Scenario: 記録できない
- **WHEN** `.local/db.sqlite3` に書き込めない状態で `devenv check-health` を実行する
- **THEN** 確認の結果と終了コードは記録できる場合と同じで、標準エラー出力に履歴を記録できなかった旨の警告が表示される

### Requirement: 保存先と保持件数
履歴は、wp-main の `.local/db.sqlite3` に保存しなければならない (MUST)。ダッシュボードの複数のプロセスと CLI が同時に書き込んでも、記録が失われてはならない (MUST NOT)。履歴が 1000 件を超えた場合、古いものから削除しなければならない (MUST)。`serve` を再起動しても、履歴は残らなければならない (MUST)。`devenv uninstall` は `.local/db.sqlite3` を削除しなければならない (MUST)。

#### Scenario: 再起動しても残る
- **WHEN** 履歴がある状態で `serve` を止めて、もう一度実行する
- **THEN** 同じ履歴が表示される

#### Scenario: コンテナを作り直す
- **WHEN** 履歴がある状態で wp-main で `docker compose up -d --force-recreate` を実行する
- **THEN** 履歴は変わらない

#### Scenario: 上限を超える
- **WHEN** 履歴が 1000 件ある状態で 1 件記録する
- **THEN** 最も古い 1 件が削除され、件数は 1000 件のままになる

#### Scenario: uninstall で削除する
- **WHEN** `devenv uninstall --yes` を実行する
- **THEN** `.local/db.sqlite3` が残らない

### Requirement: ダッシュボードでの表示
ダッシュボードのトップページは、サイト一覧の下に、直近 20 件の履歴を新しい順に表示しなければならない (MUST)。各行には、終了日時、コマンド名、成否、結果の要約を含めなければならない (MUST)。失敗した操作は、成功した操作と見分けられなければならない (MUST)。履歴がない場合は、履歴がないことを表示しなければならない (MUST)。

#### Scenario: 履歴を表示する
- **WHEN** 成功した migrate と失敗した check-health の履歴がある状態でダッシュボードを開く
- **THEN** check-health が上、migrate が下に表示され、check-health の行は失敗として区別して表示される

#### Scenario: 履歴がない
- **WHEN** 履歴が 1 件もない状態でダッシュボードを開く
- **THEN** HTTP 200 が返り、履歴がないことが表示され、サイト一覧は通常どおり表示される
