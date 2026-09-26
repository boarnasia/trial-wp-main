## MODIFIED Requirements

### Requirement: hosts エントリの管理
`dev-env:install` は `/etc/hosts` に `local.wp1.yamashita109.com`、`local.wp2.yamashita109.com`、`local.wp-main.yamashita109.com` を `127.0.0.1` に向けるエントリを、CLI 専用のマーカーで囲んだブロックとして追加しなければならない (MUST)。ブロックが既に存在する場合は重複させてはならない (MUST NOT)。既存のブロックにないドメインがある場合は、ブロックを置き換えて追加しなければならない (MUST)。`dev-env:uninstall` はそのブロックだけを削除しなければならない (MUST)。マーカーの開始と終了の対応が崩れている場合、CLI は `/etc/hosts` を変更してはならない (MUST NOT)。CLI は `/etc/hosts` を書き換える前に、元の内容をバックアップしなければならない (MUST)。

#### Scenario: 冪等な追加
- **WHEN** install を 2 回実行する
- **THEN** `/etc/hosts` のマーカーブロックは 1 つだけ存在する

#### Scenario: 既存ブロックへのドメイン追加
- **WHEN** wp1 と wp2 だけを含むマーカーブロックがある状態で install を実行する
- **THEN** マーカーブロックは 1 つだけで、`local.wp-main.yamashita109.com` を含む 3 ドメインのエントリがある

#### Scenario: 他のエントリを保持する
- **WHEN** uninstall を実行する
- **THEN** マーカーブロック以外の `/etc/hosts` の行は変更されない

#### Scenario: マーカーの対応が崩れている
- **WHEN** `/etc/hosts` に開始マーカーだけがあり終了マーカーがない状態で install または uninstall を実行する
- **THEN** CLI は `/etc/hosts` を変更せず、崩れている行を示してエラーにする

#### Scenario: 書き換え前のバックアップ
- **WHEN** install または uninstall が `/etc/hosts` を書き換える
- **THEN** 書き換え直前の内容が `/etc/hosts.wp-dev-env.bak` に保存される

### Requirement: 環境の破棄
`dev-env:uninstall` は、確認プロンプトで承認された場合、または `--yes` が指定された場合にのみ削除を実行しなければならない (MUST)。削除対象は、全コンテナ、install 由来のボリュームとイメージ（ダッシュボード用にビルドしたイメージを含む）、`wp-global-net`、hosts のマーカーブロック、記録済みの信頼済み CA 証明書、`{root}/wp-wp1`、`{root}/wp-wp2` とする。`/etc/hosts` のバックアップは復旧用に残し、削除方法を表示しなければならない (MUST)。サイトディレクトリに未コミットまたは未 push の変更がある場合、CLI は確認プロンプトの前に警告を表示しなければならない (MUST)。

#### Scenario: 確認を拒否する
- **WHEN** uninstall の確認プロンプトで `N` を入力する
- **THEN** 何も削除されずに終了する

#### Scenario: 未 push の変更を警告する
- **WHEN** `{root}/wp-wp1` に未 push のコミットがある状態で uninstall を実行する
- **THEN** 確認プロンプトの前に、変更が失われる旨の警告が表示される

#### Scenario: 完全な後片付け
- **WHEN** `--yes` を付けて uninstall を実行する
- **THEN** `{root}/wp-wp1` と `{root}/wp-wp2` が削除され、`wp-global-net`・関連ボリューム・ダッシュボードのイメージ・hosts ブロック・信頼済み CA が残らない

#### Scenario: hosts のバックアップは残して案内する
- **WHEN** `/etc/hosts.wp-dev-env.bak` がある状態で uninstall を実行する
- **THEN** バックアップは削除されず、最後に `sudo rm /etc/hosts.wp-dev-env.bak` による削除方法が表示される

#### Scenario: 部分的な状態でも完了する
- **WHEN** 一部のリソースが既に存在しない状態で uninstall を実行する
- **THEN** 存在しないリソースはスキップされ、残りのリソースの削除は続行される
