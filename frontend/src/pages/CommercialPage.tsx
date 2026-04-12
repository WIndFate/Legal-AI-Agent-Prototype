import { useTranslation } from 'react-i18next';
import styles from '../styles/legal.module.css';

export default function CommercialPage() {
  const { t } = useTranslation();

  return (
    <div className={`page ${styles.legalPage}`}>
      <h2>{t('commercial.page_title')}</h2>

      <div className={styles.summary}>
        <p>{t('commercial.summary')}</p>
      </div>

      <div className={styles.content}>
        <p className={styles.lastUpdated}>{t('commercial.last_updated', { date: '2026-04-12' })}</p>

        <table className={styles.infoTable}>
          <tbody>
            <tr>
              <th>事業者名称</th>
              <td>CodeWave Seki Studio</td>
            </tr>
            <tr>
              <th>代表者</th>
              <td>請求があった場合に遅滞なく開示いたします</td>
            </tr>
            <tr>
              <th>所在地</th>
              <td>請求があった場合に遅滞なく開示いたします</td>
            </tr>
            <tr>
              <th>電話番号</th>
              <td>請求があった場合に遅滞なく開示いたします</td>
            </tr>
            <tr>
              <th>メールアドレス</th>
              <td>[redacted-email]</td>
            </tr>
            <tr>
              <th>販売価格</th>
              <td>契約書の長さに応じた従量課金制（¥75／1,000トークン、最低料金¥200〜）</td>
            </tr>
            <tr>
              <th>追加費用</th>
              <td>なし（表示価格に消費税を含む）</td>
            </tr>
            <tr>
              <th>支払方法</th>
              <td>クレジットカード、WeChat Pay、Alipay（KOMOJU決済）</td>
            </tr>
            <tr>
              <th>支払時期</th>
              <td>サービスご利用前の前払い制</td>
            </tr>
            <tr>
              <th>サービス提供時期</th>
              <td>お支払い確認後、即時にAI分析を開始いたします（通常1〜3分以内にレポート生成）。レポートリンクはご登録のメールアドレスにも送信いたします。</td>
            </tr>
            <tr>
              <th>返品・返金</th>
              <td>デジタルサービスの性質上、AI分析処理が開始された後のキャンセル・返金には応じかねます。決済完了前であればキャンセル可能で、課金は発生しません。システム障害等によりAI分析が正常に完了しなかった場合は、メールにてお問い合わせいただければ個別に対応いたします。</td>
            </tr>
            <tr>
              <th>動作環境</th>
              <td>インターネット接続環境が必要です。推奨ブラウザ：Chrome、Safari、Edge、Firefox（最新版）</td>
            </tr>
            <tr>
              <th>特記事項</th>
              <td>本サービスはAI技術を活用した契約書リスク分析の参考情報を提供するものであり、弁護士法第72条に定める法律相談・法律事務には該当しません。分析結果に基づく法的判断や契約締結の最終決定は、必ず弁護士等の専門家にご相談ください。分析レポートは生成から72時間後に自動削除されます。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
