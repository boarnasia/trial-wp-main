# dev-plugin-cross-list Specification

## Purpose
TBD - created by archiving change plugin-cross-list. Update Purpose after archive.

## Requirements

### Requirement: WordPress メニュー
ダッシュボードのヘッダーは、ダッシュボードと並べて大メニュー「WordPress」を表示しなければならない (MUST)。「WordPress」を選ぶと、その配下の最初のページ（プラグイン横断リスト）を開かなければならない (MUST)。WordPress の配下のページでは、ヘッダーの下にサブメニューを表示し、今のページを示さなければならない (MUST)。

#### Scenario: メニューから開く
- **WHEN** ダッシュボードで「WordPress」を選ぶ
- **THEN** `/wordpress/plugins` が開き、サブメニューの「プラグイン横断リスト」が選ばれた状態で表示される

### Requirement: プラグイン横断リストの表示
プラグイン横断リストは、全サイトのプラグインを 1 つのプラグインにつき 1 行で表示しなければならない (MUST)。各行には、プラグイン名、サイトが使っている WordPress のメジャーごとのプラグイン対応状況、サイトごとの版を含めなければならない (MUST)。プラグイン名は、wordpress.org に登録があればそのページへのリンクにしなければならない (MUST)。サイトに入っていないプラグインは `-` と表示しなければならない (MUST)。対象は active・inactive・must-use のプラグインとし、drop-in は含めてはならない (MUST NOT)。無効のプラグインは無効である旨を、must-use のプラグインはその旨を示さなければならない (MUST)。表示は保存した取得結果から行い、ページを開くたびに Docker や wordpress.org に問い合わせてはならない (MUST NOT)。一度も取得していない場合は、再取得を促す表示をしなければならない (MUST)。

#### Scenario: 一覧
- **WHEN** wp1（WordPress 7.1）に Query Monitor 3.17.2 が有効で入り、wp2（6.7）には入っていない状態で取得した後にページを開く
- **THEN** Query Monitor の行に、wordpress.org へのリンク、wp1 の列に `3.17.2`、wp2 の列に `-` が表示される

#### Scenario: 未取得
- **WHEN** 一度も再取得していない状態でページを開く
- **THEN** まだ取得していない旨と「再取得」のボタンが表示される

### Requirement: プラグイン対応状況の判定
プラグイン対応状況は、wordpress.org に載っているそのプラグインの最新版の `requires`（必要な WordPress の版）と `tested`（動作確認済みの版）から判定しなければならない (MUST)。メジャー M の列は、`requires` のメジャー ≤ M ≤ `tested` のメジャーなら OK、外れれば NG、wordpress.org に登録がないか値がなければ不明としなければならない (MUST)。サイトの列は、サイトの WordPress の版が `requires` 以上で、かつ (メジャー, マイナー) が `tested` の (メジャー, マイナー) 以下でなければ、対応外である旨を警告しなければならない (MUST)。判定が最新版の情報によることを画面に明記しなければならない (MUST)。

#### Scenario: メジャーでは対応
- **WHEN** `requires` が 6.3、`tested` が 7.0 のプラグインを表示する
- **THEN** WP 6 と WP 7 の列はどちらも OK になる

#### Scenario: サイトの版で対応外
- **WHEN** `requires` が 6.8 のプラグインが WordPress 6.7 の wp2 に入っている
- **THEN** wp2 の列に、6.7 では対応外である旨の警告が表示される

#### Scenario: 登録のないプラグイン
- **WHEN** wordpress.org に登録のない社内プラグインを表示する
- **THEN** 名前はリンクにならず、メジャーの列は不明になる

### Requirement: プラグイン情報の再取得
「再取得」は CSRF トークン付きの POST でだけ受け付けなければならない (MUST)。再取得は、サイトを起動・停止せずに、各サイトの WP-CLI のサービス（`{site}-cli`）でサイトの WordPress の版とプラグインの一覧を取得し、wordpress.org の API で active と inactive のプラグインの対応状況を取得しなければならない (MUST)。取得に成功したサイトの結果だけを置き換え、失敗したサイトは前回の結果を残し、失敗した時刻と理由を表示しなければならない (MUST)。wordpress.org から取得できなかったプラグインは前回の値を残さなければならない (MUST)。同時に 2 つの再取得を実行してはならない (MUST NOT)。再取得は操作履歴に `plugins-refresh` として記録し、一部でも失敗した場合は失敗として記録しなければならない (MUST)。LAN 公開中も再取得を受け付けなければならない (MUST)。

#### Scenario: 再取得する
- **WHEN** wp1 と wp2 がどちらも停止している開発セッション中に「再取得」を選ぶ
- **THEN** wp1 と wp2 は停止したままで、両サイトのプラグインが一覧に表示され、操作履歴に成功した `plugins-refresh` が残る

#### Scenario: 一度も起動していないサイト
- **WHEN** 一度も起動していない wp2 がある状態で「再取得」を選ぶ
- **THEN** wp1 の結果は更新され、wp2 の列には取得できなかった旨と、一度サイトを起動するよう案内が表示され、操作履歴には失敗として記録される

#### Scenario: wordpress.org に届かない
- **WHEN** 前回の取得で対応状況がある状態で、wordpress.org に届かない環境で「再取得」を選ぶ
- **THEN** 対応状況は前回の値のまま表示される

### Requirement: プラグイン横断リストの絞り込み
プラグイン横断リストは、プラグイン名（表示名と slug の部分一致）とサイト名（サイト ID の部分一致）で絞り込めなければならない (MUST)。サイト名で絞り込んだ場合は、一致しないサイトの列、残ったサイトが使っていないメジャーの列、残ったサイトのどれにも入っていないプラグインの行を隠さなければならない (MUST)。絞り込みの値は URL の `q`・`site` クエリに残さなければならない (MUST)。

#### Scenario: サイトで絞り込む
- **WHEN** サイト名の絞り込みに `wp2` を入れる
- **THEN** wp1 の列と WP 7 の列が隠れ、wp2 に入っていないプラグインの行が隠れ、URL に `site=wp2` が付く
