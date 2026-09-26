## ADDED Requirements

### Requirement: 既存の環境への導入
ダッシュボードを持たない環境バージョン 1 の環境は、migration 2 で導入されなければならない (MUST)。migration 2 は `/etc/hosts` のブロックにダッシュボードのドメインを加えなければならない (MUST)。プロキシが起動している場合は、ダッシュボードのイメージをビルドして起動し、プロキシを新しい構成で作り直さなければならない (MUST)。プロキシが停止している場合は、コンテナを起動してはならない (MUST NOT)。migration 2 は sudo を必要とし、データを失う操作を含まないものとして扱わなければならない (MUST)。何度実行しても結果が同じでなければならない (MUST)。

#### Scenario: 起動中の環境に導入する
- **WHEN** 環境バージョン 1 で全コンテナが起動している状態で `dev-env:migrate` を実行する
- **THEN** `/etc/hosts` のブロックに `local.wp-main.yamashita109.com` が加わり、`wp-dashboard` が起動し、環境バージョンが 2 になる

#### Scenario: 停止中の環境に導入する
- **WHEN** 環境バージョン 1 でプロキシが停止している状態で `dev-env:migrate` を実行する
- **THEN** `/etc/hosts` のブロックは更新されるが、コンテナは起動されず、環境バージョンは 2 になる

#### Scenario: pull の後の自動実行
- **WHEN** 環境バージョン 1 の環境で、migration 2 を含むコミットを `git pull` で取り込む
- **THEN** migration は自動では実行されず、`uv run cli dev-env:migrate` を端末で実行するよう表示される

#### Scenario: 再実行
- **WHEN** hosts のブロックに既にダッシュボードのドメインがある状態で migration 2 を実行する
- **THEN** `/etc/hosts` は書き換えられない
