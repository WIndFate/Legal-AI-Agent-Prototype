import { useTranslation } from 'react-i18next';
import styles from '../styles/legal.module.css';

export default function PrivacyPage() {
  const { t } = useTranslation();

  return (
    <div className={`page ${styles.legalPage}`}>
      <h2>{t('privacy.page_title')}</h2>

      <div className={styles.summary}>
        <p>{t('privacy.summary')}</p>
      </div>

      <div className={styles.content}>
        <p className={styles.lastUpdated}>{t('privacy.last_updated', { date: '2026-03-25' })}</p>

        <h3>第1条（個人情報の定義）</h3>
        <p>
          本プライバシーポリシーにおいて「個人情報」とは、メールアドレスその他の記述により特定の個人を識別できる情報を指します。
          契約書全文は分析処理のみに使用され、分析完了後にサーバーから即時削除されるため、個人情報として保存されることはありません。
        </p>

        <h3>第2条（収集する情報）</h3>
        <p>当サービスが収集する情報は以下に限定されます：</p>
        <ul>
          <li>メールアドレス — レポートリンクの送信にのみ使用</li>
          <li>選択された表示言語 — ブラウザの localStorage に保存（サーバー送信なし）</li>
          <li>注文情報 — 決済処理に必要な最小限の情報（金額、ステータス）</li>
        </ul>

        <h3>第3条（契約書テキストの取扱い）</h3>
        <p>
          アップロードされた契約書全文は、AI分析処理の実行にのみ使用されます。
          分析完了後、契約書全文はサーバーから即時に削除され、データベースにも保存されません。
          ただし、分析結果と対応する条項原文の抜粋は、72時間の有効期限付きレポート内に限って保存され、期限後に自動削除されます。
        </p>

        <h3>第4条（第三者提供）</h3>
        <p>当サービスは、以下の場合を除き、収集した個人情報を第三者に提供いたしません：</p>
        <ul>
          <li>KOMOJU株式会社 — 決済処理のため</li>
          <li>Resend, Inc. — レポートリンクのメール送信のため</li>
          <li>OpenAI, Inc. — 契約書全文のAI分析処理のため（全文は分析完了後に削除されます）</li>
        </ul>

        <h3>第5条（Cookieの使用）</h3>
        <p>
          当サービスは、言語設定の保持にブラウザの localStorage を使用します。
          トラッキング目的のCookieは使用しません。
          サービス改善のため、匿名の利用統計を収集する場合があります（PostHog）。
        </p>

        <h3>第6条（セキュリティ）</h3>
        <p>
          当サービスは、SSL/TLS暗号化通信を使用し、お客様の情報を保護します。
          ただし、インターネット上のデータ送信について、完全なセキュリティを保証するものではありません。
        </p>

        <h3>第7条（お問い合わせ）</h3>
        <p>
          プライバシーに関するお問い合わせは、サービス運営者までメールにてご連絡ください。
        </p>
      </div>
    </div>
  );
}
