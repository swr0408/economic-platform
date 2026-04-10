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

function TermsPage() {
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
          利用規約
        </Title>
        <Text style={{ color: colors.textSecondary, display: 'block', textAlign: 'center', marginBottom: 32 }}>
          最終更新日：2026年4月10日
        </Text>

        <div style={{ color: colors.textPrimary, lineHeight: 1.8, fontSize: 14 }}>
          <Paragraph style={{ color: colors.textSecondary, marginBottom: 24 }}>
            本利用規約（以下「本規約」）は、EconAlpha（以下「当サービス」）の利用条件を定めるものです。
            ユーザーの皆様には、本規約に同意いただいた上で当サービスをご利用いただきます。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第1条（適用）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            1. 本規約は、ユーザーと当サービス運営者との間の当サービスの利用に関わる一切の関係に適用されます。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            2. 当サービスの利用をもって、ユーザーは本規約に同意したものとみなします。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第2条（免責事項・投資に関する注意事項）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            1. 当サービスで提供する情報（経済指標データ、チャート、マーケットデータ等）は、情報提供を目的としたものであり、
            特定の金融商品の売買や投資の推奨・勧誘を目的としたものではありません。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            2. 当サービスの情報に基づいて行われた投資判断やその他の行動によって生じた損害について、
            当サービス運営者は一切の責任を負いません。投資に関する最終決定は、ユーザーご自身の判断と責任において行ってください。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            3. 当サービスで提供するデータおよび情報の正確性、完全性、最新性について、当サービス運営者は保証するものではありません。
            データの遅延、誤り、欠落等が生じる場合があります。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            4. 金融商品の取引にはリスクが伴います。為替取引（FX）、株式、先物、オプション等の金融商品は、
            元本を超える損失が発生する可能性があります。お取引に際しては、契約締結前交付書面等をよくお読みいただき、
            リスクを十分にご理解の上、ご自身の判断と責任においてお取引ください。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第3条（データの出典と知的財産権）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            1. 当サービスで表示されるデータは、各国の政府機関、中央銀行、統計局、民間データプロバイダー等の公開情報に基づいています。
            各データの著作権および知的財産権は、それぞれの提供元に帰属します。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            2. 当サービスが独自に作成したチャート、分析、コンテンツの著作権は当サービス運営者に帰属します。
            無断での複製、転載、再配布、商用利用は禁止します。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            3. 個人のブログ、SNS等で当サービスのチャートを引用する場合は、出典として「EconAlpha」を明記してください。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第4条（禁止事項）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            ユーザーは、当サービスの利用にあたり、以下の行為を行ってはなりません。
          </Paragraph>
          <ul style={{ color: colors.textPrimary, paddingLeft: 24 }}>
            <li>法令または公序良俗に違反する行為</li>
            <li>犯罪行為に関連する行為</li>
            <li>当サービスのサーバーまたはネットワークに過度な負荷をかける行為</li>
            <li>当サービスのデータを自動的に大量取得（スクレイピング）する行為</li>
            <li>当サービスのデータを無断で再配布、販売する行為</li>
            <li>当サービスの運営を妨害する行為</li>
            <li>他のユーザーのアカウントを不正に使用する行為</li>
            <li>不正アクセス、リバースエンジニアリング等の行為</li>
            <li>当サービスの信用を毀損する行為</li>
            <li>その他、当サービス運営者が不適切と判断する行為</li>
          </ul>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第5条（アカウント管理）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            1. ユーザーは、自己の責任においてアカウント情報（ユーザー名およびパスワード）を管理するものとします。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            2. アカウント情報の管理不十分、第三者による不正使用等によって生じた損害について、
            当サービス運営者は一切の責任を負いません。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            3. アカウントの第三者への譲渡、貸与は禁止します。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第6条（サービスの変更・停止・終了）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            1. 当サービス運営者は、ユーザーへの事前通知なく、当サービスの内容を変更、追加、または削除することができます。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            2. 以下の事由がある場合、当サービスの全部または一部の提供を停止することがあります。
          </Paragraph>
          <ul style={{ color: colors.textPrimary, paddingLeft: 24 }}>
            <li>システムの保守・点検を行う場合</li>
            <li>地震、落雷、火災、停電等の不可抗力により提供が困難な場合</li>
            <li>データ提供元のAPI停止等、外部要因による場合</li>
            <li>その他、当サービス運営者が停止が必要と判断した場合</li>
          </ul>
          <Paragraph style={{ color: colors.textPrimary }}>
            3. サービスの変更・停止・終了によりユーザーに生じた損害について、当サービス運営者は一切の責任を負いません。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第7条（第三者サービス）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            1. 当サービスには、TradingView、Investing.com 等の第三者が提供するウィジェットやリンクが含まれる場合があります。
            これらの第三者サービスの利用については、各サービスの利用規約が適用されます。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            2. 第三者サービスの内容、正確性、利用可能性について、当サービス運営者は一切の責任を負いません。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第8条（広告）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            当サービスには、当サービス運営者または第三者の広告が表示される場合があります。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第9条（規約の変更）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            1. 当サービス運営者は、必要と判断した場合、ユーザーへの個別の通知なく本規約を変更することができます。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            2. 変更後の規約は、当サービス上に掲載した時点から効力を生じるものとします。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            3. 規約変更後に当サービスを利用した場合、ユーザーは変更後の規約に同意したものとみなします。
          </Paragraph>

          <Title level={4} style={{ color: colors.accent, marginTop: 32 }}>
            第10条（準拠法・裁判管轄）
          </Title>
          <Paragraph style={{ color: colors.textPrimary }}>
            1. 本規約の解釈は日本法に準拠します。
          </Paragraph>
          <Paragraph style={{ color: colors.textPrimary }}>
            2. 当サービスに関する紛争については、東京地方裁判所を第一審の専属的合意管轄裁判所とします。
          </Paragraph>

          <div style={{ marginTop: 40, paddingTop: 24, borderTop: `1px solid ${colors.border}`, textAlign: 'center' }}>
            <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
              <Link to="/privacy" style={{ color: colors.accent }}>プライバシーポリシー</Link>
              {' '}|{' '}
              <Link to="/" style={{ color: colors.accent }}>ホームに戻る</Link>
            </Text>
          </div>
        </div>
      </div>
    </div>
  )
}

export default TermsPage
