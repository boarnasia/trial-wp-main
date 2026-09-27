# dev-operation-history Specification

## Purpose
CLI で行った開発環境の操作（構築、移行、健全性の確認）の結果を記録し、ダッシュボードで後から確認できるようにする。記録はダッシュボードの Web API を通して行い、DB に書き込むのはダッシュボードだけにする。

## Requirements

### Requirement: 記録する操作と内容
CLI は、`devenv install`・`devenv migrate`・`devenv check-health` の実行が終わったときに、その操作を 1 件の履歴として記録しなければならない (MUST)。履歴には、コマンド名、指定されたオプション、開始日時、終了日時、終了コード、成否、結果の要約を含めなければならない (MUST)。結果の要約は、`devenv migrate` では移行前と移行後の環境バージョン、`devenv check-health` では判定ごとの件数、失敗した場合はエラーの内容としなければならない (MUST)。`--dry-run` を指定した実行、何も適用しなかった `devenv migrate`（`--auto` で条件を満たさなかった場合を含む）、`devenv uninstall` は記録してはならない (MUST NOT)。履歴に `.env` の値（パスワード、トークンなど）を含めてはならない (MUST NOT)。

#### Scenario: migrate を記録する
- **WHEN** 環境バージョン 3 の環境で、migration 4 を適用する `devenv migrate` が成功する
- **THEN** コマンド名 `migrate`、終了コード 0、成功、要約 `3 → 4` の履歴が 1 件記録される

#### Scenario: check-health を記録する
- **WHEN** FAIL が 1 件ある状態で `devenv check-health` を実行する
- **THEN** 終了コード 1、失敗、判定ごとの件数を要約に持つ履歴が 1 件記録される

#### Scenario: 何もしなかった migrate は記録しない
- **WHEN** 環境バージョンが最新の状態で `devenv migrate --auto` を実行する
- **THEN** 履歴は記録されない

#### Scenario: dry-run は記録しない
- **WHEN** `devenv install --dry-run` を実行する
- **THEN** 履歴は記録されない

### Requirement: 記録の送信と失敗時の扱い
CLI は、履歴をダッシュボードの Web API に HTTPS で送らなければならない (MUST)。証明書は、wp-main が書き出した Caddy のルート証明書で検証しなければならない (MUST)（キーチェーンへの信頼登録の有無に左右されない）。送信は数秒以内に打ち切らなければならない (MUST)。送信に失敗した場合、CLI は標準エラー出力に警告を表示し、コマンド本来の出力と終了コードを変えてはならない (MUST NOT)。CLI は DB のファイルを直接開いてはならない (MUST NOT)。

#### Scenario: ダッシュボードが停止している
- **WHEN** `wp-dashboard` を停止した状態で `devenv check-health` を実行する
- **THEN** 確認の結果と終了コードは記録を試みない場合と同じで、標準エラー出力に履歴を記録できなかった旨の警告が表示される

#### Scenario: CA を信頼登録していない環境
- **WHEN** `--skip-trust` で install した環境で `devenv check-health` を実行する
- **THEN** 履歴は記録される

### Requirement: API の認証
履歴を記録する API と一覧を返す API は、wp-main の `.env` の `DASHBOARD_API_TOKEN` と一致するトークンを持つリクエストだけを受け付けなければならない (MUST)。トークンがない、または一致しない場合は 401 を返し、DB を変更してはならない (MUST NOT)。`DASHBOARD_API_TOKEN` が設定されていない場合、API はすべてのリクエストを拒否しなければならない (MUST)。

#### Scenario: トークンがない
- **WHEN** トークンを付けずに履歴を記録する API を呼ぶ
- **THEN** 401 が返り、履歴は増えない

#### Scenario: トークンが未設定
- **WHEN** ダッシュボードのコンテナに `DASHBOARD_API_TOKEN` が渡されていない状態で、任意のトークンを付けて API を呼ぶ
- **THEN** 401 が返る

### Requirement: 保存先と保持件数
履歴は、ダッシュボードのコンテナだけがマウントする名前付きボリューム `wp-dashboard-data` 上の SQLite に保存しなければならない (MUST)。DB のスキーマは、ダッシュボードのコンテナが起動するときに最新にしなければならない (MUST)。ダッシュボードは、履歴が 1000 件を超えた場合、古いものから削除しなければならない (MUST)。ダッシュボードのコンテナを作り直しても、履歴は残らなければならない (MUST)。`devenv uninstall` はこのボリュームを削除しなければならない (MUST)。

#### Scenario: コンテナを作り直す
- **WHEN** 履歴がある状態で `docker compose up -d --build dashboard` を実行する
- **THEN** 作り直した後も同じ履歴が表示される

#### Scenario: 上限を超える
- **WHEN** 履歴が 1000 件ある状態で 1 件記録する
- **THEN** 最も古い 1 件が削除され、件数は 1000 件のままになる

#### Scenario: uninstall で削除する
- **WHEN** `devenv uninstall --yes` を実行する
- **THEN** ボリューム `wp-dashboard-data` が残らない

### Requirement: ダッシュボードでの表示
ダッシュボードのトップページは、サイト一覧の下に、直近 20 件の履歴を新しい順に表示しなければならない (MUST)。各行には、終了日時、コマンド名、成否、結果の要約を含めなければならない (MUST)。失敗した操作は、成功した操作と見分けられなければならない (MUST)。履歴がない場合は、履歴がないことを表示しなければならない (MUST)。

#### Scenario: 履歴を表示する
- **WHEN** 成功した migrate と失敗した check-health の履歴がある状態でダッシュボードを開く
- **THEN** check-health が上、migrate が下に表示され、check-health の行は失敗として区別して表示される

#### Scenario: 履歴がない
- **WHEN** 履歴が 1 件もない状態でダッシュボードを開く
- **THEN** HTTP 200 が返り、履歴がないことが表示され、サイト一覧は通常どおり表示される
