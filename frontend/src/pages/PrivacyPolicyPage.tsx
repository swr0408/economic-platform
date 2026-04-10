import { Typography } from 'antd'
import { Link } from 'react-router-dom'

const { Title, Paragraph, Text } = Typography

const colors = {
  bgPrimary: '#0f172a',
  bgSecondary: '#1e293b',
  accent: '#10b981',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
}

function PrivacyPolicyPage() {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: colors.bgPrimary,
        padding: '40px 24px',
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 800,
          background: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: '40px 48px',
        }}
      >
        <Title level={2} style={{ color: colors.textPrimary, textAlign: 'center', marginBottom: 32 }}>
          プライバシーポリシー
        </Title>
        <Text style={{ color: colors.textSecondary, display: 'block', textAlign: 'center', marginBottom: 32 }}>
          最終更新日：2026年4月10日
        </Text>

        <div style={{ color: colors.textPrimary, lineHeight: 1.8, fontSize: 14 }}>
          <Paragraph style={{ color: colors.textSecondary, marginBottom: 24 }}>
            EconAlpha（以下「当サービス」）は、ユーザーの個人情報の保護に努めます。
            本プライバシーポリシー（以下「本ポリシー」）は、当サービスにおける個人情報の取り扱いについて定めるものです。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            1. 基本方針
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            当サービスは、個人情報の重要性を認識し、個人情報に関する法令を遵守するとともに、
            適正な取り扱いと保護に努めます。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            2. 取得する個人情報
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            当サービスでは、以下の個人情報を取得する場合があります。
          </Paragraph>

          <Title level={5} style={{ color: colors.textPrimary, marginTop: 16 }}>
            2-1. アカウント登録時に取得する情報
          </Title>
          <ul style={{ color: colors.textPrimary, paddingLeft: 24 }}>
            <li>ユーザー名</li>
            <li>パスワード（暗号化して保存）</li>
          </ul>

          <Title level={5} style={{ color: colors.textPrimary, marginTop: 16 }}>
            2-2. サービス利用時に自動的に取得する情報
          </Title>
          <ul style={{ color: colors.textPrimary, paddingLeft: 24 }}>
            <li>IPアドレス</li>
            <li>ブラウザの種類・バージョン</li>
            <li>アクセス日時</li>
            <li>閲覧ページ</li>
            <li>リファラー（参照元URL）</li>
          </ul>

          <Title level={5} style={{ color: colors.textPrimary, marginTop: 16 }}>
            2-3. Cookieによる情報取得
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            当サービスでは、ユーザー体験の向上およびサービスの改善を目的として、
            Cookie（クッキー）を使用しています。Cookieとは、ウェブサイトがユーザーのブラウザに送信する小さなテキストファイルで、
            ブラウザ側に保存されます。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            ユーザーはブラウザの設定により、Cookieの受け入れを拒否することができますが、
            その場合、当サービスの一部機能（ログイン状態の維持等）が正常に動作しない場合があります。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            3. 個人情報の利用目的
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            取得した個人情報は、以下の目的で利用します。
          </Paragraph>
          <ul style={{ color: colors.textPrimary, paddingLeft: 24 }}>
            <li>ユーザー認証およびアカウント管理</li>
            <li>当サービスの提供・運営・改善</li>
            <li>不正アクセスの検知・防止</li>
            <li>利用状況の分析（アクセス解析）</li>
            <li>お問い合わせへの対応</li>
          </ul>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            4. 個人情報の第三者提供
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            当サービスは、以下の場合を除き、ユーザーの個人情報を第三者に提供することはありません。
          </Paragraph>
          <ul style={{ color: colors.textPrimary, paddingLeft: 24 }}>
            <li>ユーザーの同意がある場合</li>
            <li>法令に基づく場合</li>
            <li>人の生命、身体または財産の保護のために必要がある場合</li>
          </ul>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            5. 個人情報の管理
          </Title>

          <Title level={5} style={{ color: colors.textPrimary, marginTop: 16 }}>
            5-1. 安全管理措置
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            当サービスは、個人情報の漏洩、滅失、毀損の防止のために、適切な安全管理措置を講じます。
            パスワードは暗号化（ハッシュ化）して保存し、通信はSSL/TLSにより暗号化します。
          </Paragraph>

          <Title level={5} style={{ color: colors.textPrimary, marginTop: 16 }}>
            5-2. 個人情報の開示・訂正・削除
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            ユーザーは、当サービスが保有する自己の個人情報について、開示、訂正、追加、削除、利用停止を請求することができます。
            請求があった場合、本人確認を行った上で速やかに対応いたします。
          </Paragraph>

          <Title level={5} style={{ color: colors.textPrimary, marginTop: 16 }}>
            5-3. 保存期間
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            アカウント情報は、アカウントが有効な期間中保存されます。
            アクセスログ等の自動取得情報は、取得後最大1年間保存した後、削除します。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            6. アクセス解析ツール
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            当サービスでは、サービスの利用状況を把握するためにアクセス解析ツールを使用する場合があります。
            これらのツールはCookieを使用してデータを収集しますが、個人を特定する情報は含まれません。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            7. 第三者サービスの利用
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            当サービスでは、TradingView等の第三者が提供するウィジェットを利用しています。
            これらの第三者サービスが独自にCookieを使用する場合があります。
            第三者サービスにおける個人情報の取り扱いについては、各サービスのプライバシーポリシーをご確認ください。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            8. 未成年の方へ
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            未成年の方が当サービスを利用する場合は、保護者の同意を得た上でご利用ください。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            9. プライバシーポリシーの変更
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            当サービスは、必要に応じて本ポリシーを変更することがあります。
            変更後のポリシーは、当サービス上に掲載した時点から効力を生じるものとします。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            10. お問い合わせ
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            本ポリシーに関するお問い合わせは、当サービスの管理者までご連絡ください。
          </Paragraph>

          <div style={{ marginTop: 40, paddingTop: 24, borderTop: `1px solid ${colors.border}`, textAlign: 'center' }}>
            <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
              <Link to="/terms" style={{ color: colors.accent }}>利用規約</Link>
              {' '}|{' '}
              <Link to="/" style={{ color: colors.accent }}>ホームに戻る</Link>
            </Text>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PrivacyPolicyPage
