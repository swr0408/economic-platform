# visibility / 認証 / RBAC 回帰防止チェックリスト

## 1. このチェックリストの目的

このチェックリストは、Prompt 1〜6 完了時点で確定した visibility / 認証 / RBAC の整理状態を、今後の変更で壊さないための運用確認用チェックリストである。
対象は、新規 API endpoint 追加、新規 static path 追加、visibility 設定変更、frontend 側表示制御変更、path_resolver / middleware 変更時の回帰防止確認とする。
本チェックリストは実装変更案ではなく、既存の完了状態を維持するための確認基準である。

## 2. 使用タイミング

- 新規 `/api/...` endpoint を追加する前後
- 新規 `/static/...` 配信パスを追加する前後
- `visibility` の付与・変更・移設を行う前後
- frontend の menu / category / country / component 表示条件を変更する前後
- `path_resolver` / `ReadVisibilityGuardMiddleware` / `WriteOperationGuardMiddleware` / `require_role` 周辺を変更する前後
- `force_refresh` / `refresh` 系の扱いを変更する前後
- 401 / 403 の責務に影響しうる認証・認可変更の前後

## 3. 全体共通チェック

- [ ] この変更が Prompt 1〜6 完了済み前提を崩していない
  - 確認内容: 完了済み実装のやり直し、大規模整理、再分類、設計方針の反転を含んでいないこと。
  - NG例: visibility の意味を再定義する、全画面ログイン必須を外す、frontend 主体の制御へ戻す。

- [ ] 最小差分方針を維持している
  - 確認内容: 今回の変更に不要な周辺リファクタや横展開を含めていないこと。
  - NG例: endpoint 追加だけの作業で `countryData.tsx` 全体構造を再編する。

- [ ] `role` 定義を変更していない
  - 確認内容: `master / special / general` の 3 ロール構成を維持していること。
  - NG例: `member` ロールを追加する、`master` が `special` を暗黙内包する前提に書き換える。

- [ ] `visibility` 定義を変更していない
  - 確認内容: `public / special / master` の 3 段階を維持し、意味を変えていないこと。
  - NG例: `public` を未ログイン公開として扱う、`special` を `general` に開放する。

- [ ] backend 強制が主、frontend 非表示が補助、という原則を維持している
  - 確認内容: 認可の最終責務が backend に残っていること。
  - NG例: frontend で隠しているから backend ガードを外す。

- [ ] 全画面ログイン必須を維持している
  - 確認内容: 未ログインで閲覧できる経路を増やしていないこと。
  - NG例: `/api/*` を一部 anonymous 許可する、App.tsx の `/login` リダイレクトを外す。

- [ ] 例外公開パスが意図せず増えていない
  - 確認内容: 明示された例外以外を未認証公開していないこと。
  - NG例: `/static/new-assets/*` を慣例でそのまま公開する。

- [ ] 既存テストグリーンを維持している
  - 確認内容: `backend/tests` が少なくとも現状同等水準でグリーンであること。
  - NG例: 権限制御変更後に未実行のままマージする。

## 4. 新規 API endpoint 追加時のチェック

- [ ] `/api/*` の未ログイン GET が 401 になることを確認した
  - 確認内容: 新規 read endpoint でも未認証アクセスが素通りしないこと。
  - NG例: 新しい `/api/foo/bar` が token 無しで 200 を返す。

- [ ] 認証済みだが権限不足のケースが 403 になることを確認した
  - 確認内容: 認証失敗と権限不足を混同していないこと。
  - NG例: `general` が `special` 専用 API にアクセスした時に 401 を返す。

- [ ] endpoint の visibility / role 条件が既存定義に収まっている
  - 確認内容: `public / special / master` または `require_role(...)` による既存ルール内で表現されていること。
  - NG例: 独自の `vip_only` のような新しい概念を導入する。

- [ ] 読み取り系か更新系かの判定が明確である
  - 確認内容: GET でも `force_refresh` / `refresh` を伴うものは write 扱いにしていること。
  - NG例: `GET /api/x?force_refresh=true` を read 扱いのままにする。

- [ ] router 側の個別制御と middleware 側の全体制御の役割分担を崩していない
  - 確認内容: 必要な箇所では `require_role(...)` を残し、middleware を併用していること。
  - NG例: 「middleware があるから」として router 側 master 制御を外す。

- [ ] 認証 router の passthrough 対象を誤って拡大していない
  - 確認内容: `/api/auth/*` のみが認証系例外であることを維持していること。
  - NG例: 便宜上 `/api/user/profile` も passthrough に追加する。

- [ ] OpenAPI 表示と実際の保護状態が矛盾していない
  - 確認内容: security 表示と実装が整合していること。
  - NG例: docs 上は保護対象に見えるが実際は未認証で叩ける。

- [ ] 新規 endpoint 追加に伴う negative test 観点を整理した
  - 確認内容: 未ログイン 401、role 不足 403、許可ロール 200 の最低限確認があること。
  - NG例: 正常系だけ確認し、境界ケースを見ていない。

## 5. 新規 static path 追加時のチェック

- [ ] その static path が公開継続か認証必須かを明示した
  - 確認内容: `/static/seasonality/*` のような例外公開か、`/static/screenshots/*` のような認証必須かを事前に決めていること。
  - NG例: static だからという理由で何も決めずに配信する。

- [ ] 未認証公開にする場合、既存例外の拡張ではなく仕様確認を通している
  - 確認内容: 新たな公開 static path は自動採用せず、明示判断として扱うこと。
  - NG例: `/static/export/*` を `/static/seasonality/*` と同じ扱いに独断でする。

- [ ] 認証必須 static path が header / cookie 両経路で成立することを確認した
  - 確認内容: `<img src>` 等でも httpOnly Cookie フォールバックで保護できること。
  - NG例: Authorization ヘッダ前提でしか守れず、画像読み込みで漏れる。

- [ ] static path の追加が既存 path に誤爆していない
  - 確認内容: `path_resolver` 変更で別ディレクトリまで巻き込んでいないこと。
  - NG例: `/static/screenshot-summary/*` が `/static/screenshots/*` と誤判定される。

- [ ] frontend 上の参照先変更と backend 側保護状態が一致している
  - 確認内容: 参照パスを変えた場合でも認証前提が崩れていないこと。
  - NG例: frontend だけ別パスへ向けて backend 側保護を外してしまう。

## 6. visibility 設定変更時のチェック

- [ ] `public` の意味を広げていない
  - 確認内容: `public = ログイン後 general 以上` を維持していること。
  - NG例: public を anonymous 公開として扱う。

- [ ] `special` を `general` に誤って開放していない
  - 確認内容: `special = special / master` のみであること。
  - NG例: menu 表示だけ general に出して backend では塞いでいるつもりになる。

- [ ] `master` 限定を緩めていない
  - 確認内容: master 専用項目が special や general に落ちていないこと。
  - NG例: 一時対応で `master` を `special` まで広げ、そのまま残す。

- [ ] backend と frontend の visibility 階層を同時に確認した
  - 確認内容: `_can_view_visibility` と frontend の `canViewVisibility` の論理が一致していること。
  - NG例: frontend だけ更新して backend を据え置く。

- [ ] 未登録 indicator_code の扱いを変更していない
  - 確認内容: 未登録は `public` 扱いだが未ログイン公開ではない、という前提を維持していること。
  - NG例: 未登録を完全公開扱いにする。

- [ ] visibility 変更が menu / category / country drop に反映されるか確認した
  - 確認内容: 表示階層の変更で空カテゴリや空国が残らないこと。
  - NG例: backend では見えないが frontend メニューには残る。

## 7. frontend 側表示制御変更時のチェック

- [ ] 未ログイン時 `/login` 強制リダイレクトを維持している
  - 確認内容: App.tsx のログイン前遮断を外していないこと。
  - NG例: 一部画面だけ未ログインで開けるようにする。

- [ ] `useCanView` が role 無しなら常に false のままである
  - 確認内容: 未ログイン時に visibility 判定を通さないこと。
  - NG例: role 無しでも public なら true を返す。

- [ ] menu 非表示・コンポーネント非描画・空 category / 空 country drop の三層が崩れていない
  - 確認内容: UI 上の見え方が backend 側制御と一致していること。
  - NG例: メニューは出るが中身が 403、または空カテゴリが残る。

- [ ] frontend 側変更だけで権限制御を成立させた気になっていない
  - 確認内容: backend 側ガードを前提に補助制御として扱っていること。
  - NG例: 「表示されないから安全」として API 制御確認を省く。

- [ ] role / visibility の分岐条件を独自実装していない
  - 確認内容: 既存の判定関数と整合した条件分岐になっていること。
  - NG例: コンポーネントごとに独自 if 文で権限判定を書き散らす。

## 8. path_resolver / middleware 変更時のチェック

- [ ] `ReadVisibilityGuardMiddleware` の read 強制範囲を壊していない
  - 確認内容: `/api/*` の未ログイン GET を引き続き遮断できること。
  - NG例: middleware 条件を緩めて read が一部素通りする。

- [ ] `WriteOperationGuardMiddleware` の write 強制範囲を壊していない
  - 確認内容: POST/PUT/PATCH/DELETE と refresh 系 GET が引き続き master 限定になること。
  - NG例: `refresh=true` を見落として一般ユーザーが更新できる。

- [ ] `force_refresh` / `refresh` の query 名判定を崩していない
  - 確認内容: 既存の更新系 query 名が有効なままであること。
  - NG例: `force_refresh` だけ残して `refresh` が抜ける。

- [ ] revoke チェック 3 経路を維持している
  - 確認内容: dependencies / write_guard / read_visibility_guard のすべてで revoke 系確認が有効であること。
  - NG例: middleware 側だけ revoke 確認を外す。

- [ ] `path_resolver` の追加変更で substring 誤爆を起こしていない
  - 確認内容: 既存 endpoint や static path に予期しないマッチが発生していないこと。
  - NG例: `nab` を足したら `nab-business-confidence` まで巻き込む。

- [ ] 例外プレフィックスを独断で増やしていない
  - 確認内容: `/api/auth/*`, `/api/health`, `/health`, `/docs`, `/redoc`, `/openapi.json`, `/static/seasonality/*` 以外を安易に追加していないこと。
  - NG例: 検証用途で `/api/dev/*` を passthrough にする。

- [ ] router require_role と middleware の二重チェックを撤去していない
  - 確認内容: 特に master 限定 CRUD は二重防御を維持していること。
  - NG例: 片方で守れているからと router 側制約を削除する。

## 9. 401 / 403 確認チェック

- [ ] token 無しは 401 になっている
  - 確認内容: 未認証アクセスが role 不足扱いになっていないこと。
  - NG例: 未ログインで 403 を返す。

- [ ] token 不正 / 期限切れ / revoke は 401 になっている
  - 確認内容: 認証失敗系を明確に 401 へ寄せていること。
  - NG例: revoke 済み token に 403 を返す。

- [ ] 認証済みだが role 不足は 403 になっている
  - 確認内容: 認証成功後の権限不足を 403 で返していること。
  - NG例: `general` が `master` API にアクセスして 401 を返す。

- [ ] visibility 違反は 403 になっている
  - 確認内容: 「誰か分かるが見せられない」ケースを 403 にしていること。
  - NG例: special 項目に general が来た時に 404 や 401 を返す。

- [ ] inactive ユーザーの扱いが 403 のままである
  - 確認内容: 認証済みだが使用不可、という整理を崩していないこと。
  - NG例: inactive を 401 に寄せる。

- [ ] frontend 側エラー処理が 401 / 403 の意味差を潰していない
  - 確認内容: 401 と 403 を同一文言・同一遷移で雑に扱っていないこと。
  - NG例: 403 でも必ずログアウトさせる。

## 10. 要仕様確認として止めるべきケース

- [ ] `/api/scheduler/status` の権限を変更したい
  - 確認内容: 現在は member-only 扱いのため、master 限定化や special 化は仕様確認が先。
  - NG例: 影響確認なしで master 限定へ変更する。

- [ ] 新しい未認証公開パスを追加したい
  - 確認内容: `public` とは別概念なので、必ず仕様確認を先に行う。
  - NG例: 「public 相当だから」で未ログイン公開にする。

- [ ] `role` を追加・統合・再命名したい
  - 確認内容: 現行 3 ロール前提を崩すため別フェーズで合意が必要。
  - NG例: 実装の都合で `special_admin` を増やす。

- [ ] `visibility` 段階を増やしたい
  - 確認内容: frontend / backend / menu / path 解決に波及するため別フェーズ扱いにする。
  - NG例: 一部機能だけ `internal` visibility を追加する。

- [ ] `countryData.tsx` の大規模構造変更をしたい
  - 確認内容: 本テーマの最小差分方針から外れるため別タスク化する。
  - NG例: 権限制御ついでにデータ構造全体を作り替える。

- [ ] frontend 主体の権限制御へ寄せたい
  - 確認内容: backend 強制を主とする固定前提に反するため着手前に再合意が必要。
  - NG例: API 側チェックを減らして UI 側だけで分岐する。

- [ ] 認証方式や revoke 方式を変更したい
  - 確認内容: JWT / Cookie / revoke 3 経路の前提を壊すため別フェーズで扱う。
  - NG例: 依存関係整理の一環として revoke チェックを 1 箇所へ集約して他を消す。

- [ ] BrowserRunner 残り 2 サービス移行を同時に進めたい
  - 確認内容: 現時点では将来対応事項であり、本チェックリスト適用範囲を超える。
  - NG例: visibility 修正と同時に runner 移行まで混ぜて進める。
