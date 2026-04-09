# visibility / 認証 / RBAC テーマ 完了メモ

## 1. 今回の結論

visibility / 認証 / RBAC テーマは、Prompt 1〜6 の範囲について一旦完了扱いとする。
現時点では必須の追加修正は不要であり、今後は「実装追加」ではなく「整理状態の維持」を優先する。

## 2. 完了済みとして確定する範囲

- 認証・RBAC 基盤
  - User モデル
  - `master / special / general`
  - JWT / dependencies
  - register / login / me / logout / change-password / users 系

- 更新系操作の backend 強制
  - `WriteOperationGuardMiddleware`
  - write 系の master 限定
  - `force_refresh GET` の master 限定維持

- 読み取り visibility 制御
  - `public / special / master` の導入
  - frontend 側 visibility 基盤
  - backend 側 `ReadVisibilityGuardMiddleware`
  - `/api/*` は未ログイン GET も認証必須

- UI 側の補助制御
  - 未ログイン時 `/login` 強制リダイレクト
  - `useCanView` は role 無しなら常に false
  - menu 非表示
  - コンポーネント非描画
  - 空 category / 空 country の drop

- 個別機能の権限制御
  - ヘッドライン編集 CRUD の master 限定
  - スクリーンショット機能の権限制御
  - `/static/screenshots/*` は認証必須
  - `/static/seasonality/*` は公開継続

- 将来 OCI を見据えた整理
  - Playwright / Selenium の runner / service 層整理

## 3. この時点で成立している重要事項

- Prompt 1〜6 は完了扱い
- Claude による完了判定レビューでも必須要件は充足
- `backend/tests` は `201 passed, 3 skipped`
- `401 / 403` の責務分離は成立
  - `401`: token 無し / 不正 / 期限切れ / revoke 等
  - `403`: role 不足 / visibility 違反等
- `public` は未認証公開ではなく「ログイン後 general 以上」で固定
- frontend / backend の visibility 階層は一致
- scheduler / RSS / Discord など既存自動処理は無影響
- OpenAPI の security 表示も担保済み
- frontend だけで守る設計には戻さない

## 4. 現時点での判断

現時点では、visibility / 認証 / RBAC テーマについて**追加実装を急ぐ必要はない**。
優先すべきなのは、新しい実装を足すことではなく、完了済み状態を崩さないことである。

そのため、このフェーズでは以下をもって十分とする。

- 現状固定メモの整備
- 回帰防止チェックリストの整備
- 実装は必要が出るまで凍結

## 5. 将来対応でよい事項

以下は未解決ではあるが、現フェーズの完了判定を崩すものではない。

- `/api/scheduler/status` の権限再確認
- `path_resolver` substring マッチの将来誤爆リスク管理
- read 系 `403` の `audit_log` 強化
- `write_guard` の refresh 系 query 名追加対応
- BrowserRunner 残り 2 サービス移行

## 6. 今後このテーマでコードを触る条件

今後、visibility / 認証 / RBAC テーマでコード変更してよいのは、以下のいずれかに該当する場合のみとする。

- 新規 API endpoint を追加する時
- 新規 static path を追加する時
- visibility 設定を追加・変更する時
- `401 / 403 / visibility` 不整合の実バグが出た時
- 将来対応項目について仕様確定が入った時

それ以外では、このテーマは**完了済み前提を維持して一旦クローズ**とする。

## 7. 運用上の扱い

今後この領域に着手する場合は、必ず以下を先に参照する。

1. 現状固定メモ
2. 回帰防止チェックリスト
3. 本完了メモ

この順序を守り、最小差分でのみ再開すること。
