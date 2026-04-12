export type LegalBlock =
  | { type: 'paragraph'; content: string[] }
  | { type: 'list'; content: string[] };

export type LegalSection = {
  title: string;
  blocks: LegalBlock[];
};

type LegalDocumentCopy = {
  noticeTitle: string;
  noticeBody: string;
  officialSummary: string;
  officialToggleLabel: string;
  sections: LegalSection[];
};

type SupportedLegalLanguage =
  | 'ja'
  | 'en'
  | 'zh-CN'
  | 'zh-TW'
  | 'ko'
  | 'vi'
  | 'id'
  | 'pt-BR'
  | 'ne';

type LegalCopy = {
  privacy: LegalDocumentCopy;
  terms: LegalDocumentCopy;
};

const PRIVACY_JP: LegalSection[] = [
  {
    title: '第1条（個人情報の定義）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          '本プライバシーポリシーにおいて「個人情報」とは、メールアドレスその他の記述により特定の個人を識別できる情報を指します。',
          '契約書全文は分析処理のみに使用され、分析完了後にサーバーから即時削除されるため、個人情報として保存されることはありません。',
        ],
      },
    ],
  },
  {
    title: '第2条（収集する情報）',
    blocks: [
      {
        type: 'paragraph',
        content: ['当サービスが収集する情報は以下に限定されます。'],
      },
      {
        type: 'list',
        content: [
          'メールアドレス — レポートリンクの送信にのみ使用',
          '選択された表示言語 — ブラウザの localStorage に保存（サーバー送信なし）',
          '注文情報 — 決済処理に必要な最小限の情報（金額、ステータス）',
        ],
      },
    ],
  },
  {
    title: '第3条（契約書テキストの取扱い）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'アップロードされた契約書全文は、AI分析処理の実行にのみ使用されます。',
          '分析完了後、契約書全文はサーバーから即時に削除され、データベースにも保存されません。',
          'ただし、分析結果と対応する条項原文の抜粋は、72時間の有効期限付きレポート内に限って保存され、期限後に自動削除されます。',
        ],
      },
    ],
  },
  {
    title: '第4条（第三者提供）',
    blocks: [
      {
        type: 'paragraph',
        content: ['当サービスは、以下の場合を除き、収集した個人情報を第三者に提供いたしません。'],
      },
      {
        type: 'list',
        content: [
          'KOMOJU株式会社 — 決済処理のため',
          'Resend, Inc. — レポートリンクのメール送信のため',
          'OpenAI, Inc. — 契約書全文のAI分析処理のため（全文は分析完了後に削除されます）',
        ],
      },
    ],
  },
  {
    title: '第5条（Cookie等の利用）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          '当サービスは、言語設定の保持にブラウザの localStorage を使用します。',
          'トラッキング目的のCookieは原則使用しませんが、サービス改善のため匿名の利用統計を収集する場合があります。',
        ],
      },
    ],
  },
  {
    title: '第6条（セキュリティ）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          '当サービスは、SSL/TLS暗号化通信を使用し、お客様の情報を保護します。',
          'ただし、インターネット上のデータ送信について、完全なセキュリティを保証するものではありません。',
        ],
      },
    ],
  },
  {
    title: '第7条（お問い合わせ）',
    blocks: [
      {
        type: 'paragraph',
        content: ['プライバシーに関するお問い合わせは、サービス運営者までメールにてご連絡ください。'],
      },
    ],
  },
];

const TERMS_JP: LegalSection[] = [
  {
    title: '第1条（サービスの内容）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'ContractGuard（以下「本サービス」）は、AI技術を活用した契約書リスク分析サービスです。',
          'ユーザーがアップロードした日本語の契約書テキストに対し、条項ごとのリスク評価と改善提案を提供します。',
        ],
      },
    ],
  },
  {
    title: '第2条（法律相談ではないことの明示）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          '本サービスは弁護士法第72条に定める法律事務を行うものではありません。',
          '本サービスが提供する分析結果は、あくまでAIによる参考情報であり、法的助言ではありません。',
          '具体的な法的判断や契約の締結に関する決定は、必ず弁護士等の専門家にご相談ください。',
        ],
      },
    ],
  },
  {
    title: '第3条（料金と支払い）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          '本サービスは都度払い方式（Pay-per-use）を採用しています。',
          '料金は契約書の長さおよび処理コストに基づいて算出されます。',
          '決済はKOMOJU株式会社の決済サービスを通じて行われます。',
        ],
      },
    ],
  },
  {
    title: '第4条（返金ポリシー）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'AI分析の処理が開始された後の返金には応じかねます。',
          '決済完了前にサービスの利用をキャンセルされた場合、課金は発生しません。',
          'システム障害等により分析が正常に完了しなかった場合は、個別にご対応いたします。',
        ],
      },
    ],
  },
  {
    title: '第5条（レポートの有効期限）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          '分析レポートは生成から72時間後に自動的に削除されます。',
          'レポートリンクはメールで送信されますが、72時間経過後はアクセスできなくなります。',
          '保存が必要な場合は、有効期限内にお客様ご自身でダウンロードまたは保存をお願いいたします。',
        ],
      },
    ],
  },
  {
    title: '第6条（免責事項）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          '本サービスは、AI分析結果の正確性、完全性、有用性について、いかなる保証も行いません。',
          '本サービスの利用により生じた損害について、当サービス運営者は法令上許容される範囲で責任を負いません。',
          '重要な判断は必ず専門家にご確認ください。',
        ],
      },
    ],
  },
  {
    title: '第7条（プライバシー）',
    blocks: [
      {
        type: 'paragraph',
        content: [
          '個人情報の取扱いについては、別途定めるプライバシーポリシーに従います。',
          'アップロードされた契約書テキストは分析完了後に即時削除され、当サービスのサーバーに保存されることはありません。',
        ],
      },
    ],
  },
  {
    title: '第8条（利用規約の変更）',
    blocks: [
      {
        type: 'paragraph',
        content: ['当サービスは、必要に応じて本利用規約を変更することがあります。変更後の利用規約は、本ページに掲載した時点で効力を生じます。'],
      },
    ],
  },
  {
    title: '第9条（準拠法・管轄）',
    blocks: [
      {
        type: 'paragraph',
        content: ['本利用規約は日本法に準拠し、解釈されるものとします。本サービスに関する紛争については、東京地方裁判所を第一審の専属的合意管轄裁判所とします。'],
      },
    ],
  },
];

const PRIVACY_EN: LegalSection[] = [
  {
    title: '1. What We Treat as Personal Information',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'In this policy, personal information means data that can identify a specific person, such as an email address or other identifying details.',
          'Full contract text is used only for analysis and is deleted from our server immediately after analysis finishes.',
        ],
      },
    ],
  },
  {
    title: '2. Information We Collect',
    blocks: [
      { type: 'paragraph', content: ['We limit collection to the minimum information needed to operate the service.'] },
      {
        type: 'list',
        content: [
          'Email address, used only to send your report link.',
          'Selected display language, stored in your browser localStorage and not sent to the server for account profiling.',
          'Order and payment status information required to complete checkout and deliver your report.',
        ],
      },
    ],
  },
  {
    title: '3. How Contract Text Is Handled',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'Uploaded contract text is processed only to run OCR, structure the contract, analyze risk, and generate the report you requested.',
          'After analysis finishes, the full contract text is removed from active storage and is not retained in the database.',
          'Short clause excerpts tied to findings may remain inside the 72-hour report so you can review the context of each finding before the report expires.',
        ],
      },
    ],
  },
  {
    title: '4. Third-Party Processors',
    blocks: [
      { type: 'paragraph', content: ['We do not sell personal information. We share limited data only with service providers needed to operate the product.'] },
      {
        type: 'list',
        content: [
          'KOMOJU for payment processing.',
          'Resend for sending the report email.',
          'OpenAI for OCR, translation, and contract analysis. Contract text is sent only for processing and is not kept as a permanent report copy by us.',
        ],
      },
    ],
  },
  {
    title: '5. Cookies and Similar Technologies',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'We primarily use browser localStorage to remember your language preference.',
          'We do not rely on tracking cookies for ad targeting. We may collect limited anonymous product analytics to improve reliability and usability.',
        ],
      },
    ],
  },
  {
    title: '6. Security',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'We use encrypted connections and standard infrastructure protections to reduce unauthorized access risk.',
          'No internet service can guarantee absolute security, so please avoid uploading information you are not comfortable transmitting online.',
        ],
      },
    ],
  },
  {
    title: '7. Contact',
    blocks: [{ type: 'paragraph', content: ['For privacy-related questions, please contact the operator by email using the contact method shown on this site.'] }],
  },
];

const TERMS_EN: LegalSection[] = [
  {
    title: '1. Service Overview',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'ContractGuard is an AI-powered contract risk review service.',
          'When you upload a Japanese contract, the service returns clause-by-clause risk observations and plain-language suggestions in your selected language.',
        ],
      },
    ],
  },
  {
    title: '2. Not Legal Advice',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'ContractGuard is not a law firm and does not provide legal representation or attorney-client services.',
          'All outputs are reference information generated by software. If you need a legal opinion or a binding judgment, you must consult a qualified lawyer or other professional.',
        ],
      },
    ],
  },
  {
    title: '3. Pricing and Payment',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'The service is sold on a pay-per-use basis.',
          'Pricing depends on the contract length and processing cost. Payments are handled through KOMOJU and the payment methods shown at checkout.',
        ],
      },
    ],
  },
  {
    title: '4. Refund Policy',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'Once analysis processing has started, refunds are generally not available because the digital service has already begun.',
          'If payment has not been completed, no charge is collected. If a serious system issue prevents delivery, we will review the case individually.',
        ],
      },
    ],
  },
  {
    title: '5. Report Availability',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'Generated reports are available for 72 hours and are then removed automatically.',
          'If you need to keep the result longer, download the PDF or save the report before the expiry window ends.',
        ],
      },
    ],
  },
  {
    title: '6. Disclaimer',
    blocks: [
      {
        type: 'paragraph',
        content: [
          'We do not guarantee that the analysis will be complete, error-free, or suitable for every situation.',
          'To the maximum extent permitted by law, the operator is not responsible for losses caused by reliance on the report without professional review.',
        ],
      },
    ],
  },
  {
    title: '7. Privacy',
    blocks: [{ type: 'paragraph', content: ['Personal information is handled according to the separate Privacy Policy. Full contract text is removed after analysis completes.'] }],
  },
  {
    title: '8. Changes to These Terms',
    blocks: [{ type: 'paragraph', content: ['We may revise these Terms when necessary. Updated Terms take effect when posted on this page.'] }],
  },
  {
    title: '9. Governing Law and Jurisdiction',
    blocks: [{ type: 'paragraph', content: ['These Terms are governed by Japanese law. The Tokyo District Court has exclusive jurisdiction as the court of first instance for disputes related to this service.'] }],
  },
];

const PRIVACY_ZH_CN: LegalSection[] = [
  {
    title: '1. 个人信息的定义',
    blocks: [{ type: 'paragraph', content: ['本政策中的“个人信息”是指可识别特定个人的信息，例如电子邮箱地址等。', '合同全文仅用于分析处理，分析完成后会立即从服务器删除，不会作为长期资料保存。'] }],
  },
  {
    title: '2. 我们收集的信息',
    blocks: [
      { type: 'paragraph', content: ['我们只收集提供本服务所必需的最少信息。'] },
      { type: 'list', content: ['电子邮箱地址：仅用于发送报告链接。', '所选界面语言：保存在浏览器 localStorage 中，不作为用户画像数据发送。', '订单与支付状态：仅用于完成结算和交付报告。'] },
    ],
  },
  {
    title: '3. 合同文本的处理方式',
    blocks: [{ type: 'paragraph', content: ['上传的合同文本仅用于 OCR、结构解析、风险分析和报告生成。', '分析完成后，合同全文会从活动存储中删除，不会作为完整原文保存在数据库中。', '为便于你在 72 小时有效期内复核各项风险，报告中可能暂时保留与结论对应的条款摘录。'] }],
  },
  {
    title: '4. 向第三方的提供',
    blocks: [
      { type: 'paragraph', content: ['我们不会出售个人信息。只有在提供服务所必需的范围内，才会向下列处理方提供有限数据。'] },
      { type: 'list', content: ['KOMOJU：用于支付处理。', 'Resend：用于发送报告邮件。', 'OpenAI：用于 OCR、翻译和合同分析。合同文本仅用于处理。'] },
    ],
  },
  {
    title: '5. Cookie 与类似技术',
    blocks: [{ type: 'paragraph', content: ['我们主要使用浏览器 localStorage 保存语言偏好。', '我们原则上不使用广告跟踪 Cookie，但可能会收集有限的匿名使用统计，以改进服务稳定性和体验。'] }],
  },
  {
    title: '6. 安全措施',
    blocks: [{ type: 'paragraph', content: ['我们使用加密通信和标准基础设施安全措施来降低未经授权访问的风险。', '但任何互联网服务都无法保证绝对安全，请谨慎上传你不愿在线传输的信息。'] }],
  },
  {
    title: '7. 联系我们',
    blocks: [{ type: 'paragraph', content: ['如对隐私事项有疑问，请通过本站所示联系方式以邮件联系运营方。'] }],
  },
];

const TERMS_ZH_CN: LegalSection[] = [
  {
    title: '1. 服务内容',
    blocks: [{ type: 'paragraph', content: ['ContractGuard 是一项基于 AI 的合同风险分析服务。', '当你上传日文合同后，系统会按条款返回风险提示和通俗建议，并以你选择的语言呈现结果。'] }],
  },
  {
    title: '2. 非法律意见',
    blocks: [{ type: 'paragraph', content: ['本服务不是律师事务，也不提供法律代理或律师意见。', '所有输出均属于软件生成的参考信息。如需法律判断或正式法律意见，请咨询合格律师或其他专业人士。'] }],
  },
  {
    title: '3. 价格与支付',
    blocks: [{ type: 'paragraph', content: ['本服务按次收费。', '价格会根据合同长度与处理成本计算，支付由 KOMOJU 及结算页面显示的支付方式完成。'] }],
  },
  {
    title: '4. 退款政策',
    blocks: [{ type: 'paragraph', content: ['一旦分析流程已经开始，原则上不接受退款，因为数字服务已经开始履行。', '若尚未完成支付则不会扣款；若因重大系统故障导致无法交付，我们会个别核实处理。'] }],
  },
  {
    title: '5. 报告有效期',
    blocks: [{ type: 'paragraph', content: ['生成后的报告仅保留 72 小时，之后会自动删除。', '如需长期保存，请在有效期内下载 PDF 或自行保存。'] }],
  },
  {
    title: '6. 免责声明',
    blocks: [{ type: 'paragraph', content: ['我们不保证分析结果在任何情况下都完整、无误或适用于你的具体场景。', '在法律允许的范围内，因未经专业人士复核而直接依赖本报告所产生的损失，由用户自行承担。'] }],
  },
  {
    title: '7. 隐私',
    blocks: [{ type: 'paragraph', content: ['个人信息处理适用本网站另行公布的隐私政策。合同全文会在分析完成后删除。'] }],
  },
  {
    title: '8. 规则变更',
    blocks: [{ type: 'paragraph', content: ['我们可能根据需要修改本条款，更新后的条款自发布在本页面时生效。'] }],
  },
  {
    title: '9. 准据法与管辖',
    blocks: [{ type: 'paragraph', content: ['本条款适用日本法。与本服务相关的争议由东京地方法院作为第一审专属管辖法院。'] }],
  },
];

const PRIVACY_ZH_TW: LegalSection[] = [
  {
    title: '1. 個人資訊的定義',
    blocks: [{ type: 'paragraph', content: ['本政策中的「個人資訊」是指可識別特定個人的資訊，例如電子郵件地址等。', '合約全文僅用於分析處理，分析完成後會立即從伺服器刪除，不會作為長期資料保存。'] }],
  },
  {
    title: '2. 我們收集的資訊',
    blocks: [
      { type: 'paragraph', content: ['我們僅收集提供服務所需的最少資訊。'] },
      { type: 'list', content: ['電子郵件地址：僅用於寄送報告連結。', '所選語言：保存在瀏覽器 localStorage 中，不用於使用者畫像。', '訂單與付款狀態：僅用於完成結帳與交付報告。'] },
    ],
  },
  {
    title: '3. 合約文字的處理方式',
    blocks: [{ type: 'paragraph', content: ['上傳的合約文字僅用於 OCR、結構解析、風險分析與報告生成。', '分析完成後，合約全文會自活動儲存刪除，不會以完整原文形式保存在資料庫中。', '為了讓你在 72 小時有效期內重新查看風險內容，報告中可能暫時保留與結論對應的條款摘錄。'] }],
  },
  {
    title: '4. 提供給第三方',
    blocks: [
      { type: 'paragraph', content: ['我們不販售個人資訊。僅在提供服務所必要的範圍內，向下列處理方提供有限資料。'] },
      { type: 'list', content: ['KOMOJU：付款處理。', 'Resend：寄送報告電子郵件。', 'OpenAI：OCR、翻譯與合約分析。合約內容僅用於處理。'] },
    ],
  },
  {
    title: '5. Cookie 與類似技術',
    blocks: [{ type: 'paragraph', content: ['我們主要使用瀏覽器 localStorage 記住語言偏好。', '原則上不使用廣告追蹤 Cookie，但可能蒐集有限的匿名使用統計以改善穩定性與體驗。'] }],
  },
  {
    title: '6. 安全措施',
    blocks: [{ type: 'paragraph', content: ['我們使用加密通訊與標準基礎設施安全措施來降低未授權存取風險。', '但任何網路服務都無法保證絕對安全，請謹慎上傳你不願在線傳輸的資訊。'] }],
  },
  {
    title: '7. 聯絡我們',
    blocks: [{ type: 'paragraph', content: ['若對隱私事項有疑問，請透過網站所示聯絡方式以電子郵件聯絡營運方。'] }],
  },
];

const TERMS_ZH_TW: LegalSection[] = [
  {
    title: '1. 服務內容',
    blocks: [{ type: 'paragraph', content: ['ContractGuard 是一項以 AI 為基礎的合約風險分析服務。', '當你上傳日文合約後，系統會按條款提供風險提示與易懂建議，並以你選擇的語言呈現。'] }],
  },
  {
    title: '2. 非法律意見',
    blocks: [{ type: 'paragraph', content: ['本服務不是律師事務，也不提供法律代理或律師意見。', '所有輸出均屬軟體生成的參考資訊。如需法律判斷或正式意見，請諮詢合格律師或其他專業人士。'] }],
  },
  {
    title: '3. 價格與付款',
    blocks: [{ type: 'paragraph', content: ['本服務採按次收費。', '價格會依合約長度與處理成本計算，付款由 KOMOJU 與結帳頁面顯示的支付方式完成。'] }],
  },
  {
    title: '4. 退款政策',
    blocks: [{ type: 'paragraph', content: ['一旦分析流程開始，原則上不接受退款，因為數位服務已經開始履行。', '若尚未完成付款則不會扣款；若因重大系統故障無法交付，我們會個別確認後處理。'] }],
  },
  {
    title: '5. 報告有效期',
    blocks: [{ type: 'paragraph', content: ['生成後的報告會保留 72 小時，之後自動刪除。', '如需長期保存，請於有效期內下載 PDF 或自行儲存。'] }],
  },
  {
    title: '6. 免責聲明',
    blocks: [{ type: 'paragraph', content: ['我們不保證分析結果在任何情況下都完整、正確或適合你的具體場景。', '在法律允許範圍內，若未經專業人士確認便直接依賴本報告所造成的損失，由使用者自行承擔。'] }],
  },
  {
    title: '7. 隱私',
    blocks: [{ type: 'paragraph', content: ['個人資訊處理適用本站另行公布的隱私政策。合約全文會於分析完成後刪除。'] }],
  },
  {
    title: '8. 條款變更',
    blocks: [{ type: 'paragraph', content: ['我們可能於必要時修改本條款，更新後的條款自發布於本頁時生效。'] }],
  },
  {
    title: '9. 準據法與管轄',
    blocks: [{ type: 'paragraph', content: ['本條款適用日本法。與本服務相關的爭議由東京地方法院作為第一審專屬管轄法院。'] }],
  },
];

const PRIVACY_KO: LegalSection[] = [
  {
    title: '1. 개인정보의 정의',
    blocks: [{ type: 'paragraph', content: ['이 정책에서 개인정보란 이메일 주소 등 특정 개인을 식별할 수 있는 정보를 의미합니다.', '계약서 전문은 분석 처리에만 사용되며 분석이 끝나면 서버에서 즉시 삭제됩니다.'] }],
  },
  {
    title: '2. 수집하는 정보',
    blocks: [
      { type: 'paragraph', content: ['서비스 운영에 필요한 최소한의 정보만 수집합니다.'] },
      { type: 'list', content: ['이메일 주소: 보고서 링크 발송용.', '선택한 표시 언어: 브라우저 localStorage 에 저장되며 프로파일링 용도로 서버에 보내지지 않음.', '주문 및 결제 상태 정보: 결제 완료와 보고서 제공을 위해 필요함.'] },
    ],
  },
  {
    title: '3. 계약서 텍스트 처리',
    blocks: [{ type: 'paragraph', content: ['업로드된 계약서 텍스트는 OCR, 구조화, 위험 분석, 보고서 생성 목적에 한해 처리됩니다.', '분석이 완료되면 계약서 전문은 활성 저장소에서 삭제되며 데이터베이스에 전문 형태로 보존되지 않습니다.', '다만 72시간 동안 각 판단의 근거를 보여주기 위해 관련 조항 일부가 보고서 안에 남을 수 있습니다.'] }],
  },
  {
    title: '4. 제3자 제공',
    blocks: [
      { type: 'paragraph', content: ['개인정보를 판매하지 않으며, 서비스 운영에 필요한 범위에서만 제한적으로 외부 처리자와 공유합니다.'] },
      { type: 'list', content: ['KOMOJU: 결제 처리.', 'Resend: 보고서 이메일 발송.', 'OpenAI: OCR, 번역, 계약 분석 처리. 계약 텍스트는 처리 목적에 한해서만 전송됩니다.'] },
    ],
  },
  {
    title: '5. 쿠키 및 유사 기술',
    blocks: [{ type: 'paragraph', content: ['주로 브라우저 localStorage 를 이용해 언어 설정을 기억합니다.', '광고 추적용 쿠키는 원칙적으로 사용하지 않으며, 안정성과 사용성 개선을 위한 익명 통계만 제한적으로 수집할 수 있습니다.'] }],
  },
  {
    title: '6. 보안',
    blocks: [{ type: 'paragraph', content: ['암호화된 통신과 표준 인프라 보안 조치를 사용합니다.', '다만 어떤 인터넷 서비스도 절대적인 보안을 보장할 수 없으므로 온라인 전송이 불편한 정보는 업로드하지 마십시오.'] }],
  },
  {
    title: '7. 문의',
    blocks: [{ type: 'paragraph', content: ['개인정보 관련 문의는 사이트에 표시된 연락처를 통해 이메일로 연락해 주십시오.'] }],
  },
];

const TERMS_KO: LegalSection[] = [
  {
    title: '1. 서비스 개요',
    blocks: [{ type: 'paragraph', content: ['ContractGuard 는 AI 기반 계약 위험 분석 서비스입니다.', '일본어 계약서를 업로드하면 조항별 위험 포인트와 쉬운 설명의 제안을 선택한 언어로 제공합니다.'] }],
  },
  {
    title: '2. 법률 자문 아님',
    blocks: [{ type: 'paragraph', content: ['본 서비스는 법률사무를 수행하지 않으며 변호사 자문을 제공하지 않습니다.', '모든 결과는 소프트웨어가 생성한 참고 정보이며, 구체적인 법률 판단이 필요하면 변호사 등 전문가에게 상담해야 합니다.'] }],
  },
  {
    title: '3. 요금과 결제',
    blocks: [{ type: 'paragraph', content: ['본 서비스는 건별 결제 방식입니다.', '요금은 계약서 길이와 처리 비용에 따라 산정되며 결제는 KOMOJU 와 결제 화면에 표시되는 수단을 통해 이뤄집니다.'] }],
  },
  {
    title: '4. 환불 정책',
    blocks: [{ type: 'paragraph', content: ['분석 처리가 시작된 뒤에는 디지털 서비스가 이미 개시되므로 원칙적으로 환불이 불가합니다.', '결제가 완료되기 전에는 청구되지 않으며, 중대한 시스템 장애로 결과 제공이 불가능한 경우에는 개별적으로 검토합니다.'] }],
  },
  {
    title: '5. 보고서 이용 가능 기간',
    blocks: [{ type: 'paragraph', content: ['생성된 보고서는 72시간 동안 제공되며 이후 자동 삭제됩니다.', '장기 보관이 필요하면 만료 전에 PDF 를 다운로드하거나 직접 저장해 두어야 합니다.'] }],
  },
  {
    title: '6. 면책',
    blocks: [{ type: 'paragraph', content: ['분석 결과의 완전성, 정확성, 특정 상황에 대한 적합성을 보장하지 않습니다.', '전문가 검토 없이 보고서에만 의존해 발생한 손해에 대해 법이 허용하는 범위에서 책임을 지지 않습니다.'] }],
  },
  {
    title: '7. 개인정보',
    blocks: [{ type: 'paragraph', content: ['개인정보 처리는 별도의 개인정보처리방침에 따릅니다. 계약서 전문은 분석 완료 후 삭제됩니다.'] }],
  },
  {
    title: '8. 약관 변경',
    blocks: [{ type: 'paragraph', content: ['필요한 경우 약관을 변경할 수 있으며, 변경된 약관은 이 페이지에 게시되는 시점부터 효력이 발생합니다.'] }],
  },
  {
    title: '9. 준거법 및 관할',
    blocks: [{ type: 'paragraph', content: ['이 약관은 일본법을 준거법으로 하며, 본 서비스와 관련된 분쟁은 도쿄지방법원을 제1심 전속 합의관할 법원으로 합니다.'] }],
  },
];

const PRIVACY_VI: LegalSection[] = [
  {
    title: '1. Định nghĩa thông tin cá nhân',
    blocks: [{ type: 'paragraph', content: ['Trong chính sách này, thông tin cá nhân là thông tin có thể xác định một cá nhân cụ thể, chẳng hạn như địa chỉ email.', 'Toàn văn hợp đồng chỉ được dùng để phân tích và sẽ bị xóa khỏi máy chủ ngay sau khi phân tích xong.'] }],
  },
  {
    title: '2. Thông tin chúng tôi thu thập',
    blocks: [
      { type: 'paragraph', content: ['Chúng tôi chỉ thu thập lượng thông tin tối thiểu cần thiết để vận hành dịch vụ.'] },
      { type: 'list', content: ['Địa chỉ email: chỉ để gửi liên kết báo cáo.', 'Ngôn ngữ hiển thị đã chọn: lưu trong localStorage của trình duyệt, không dùng để lập hồ sơ người dùng.', 'Thông tin đơn hàng và trạng thái thanh toán: cần thiết để hoàn tất thanh toán và giao báo cáo.'] },
    ],
  },
  {
    title: '3. Cách xử lý văn bản hợp đồng',
    blocks: [{ type: 'paragraph', content: ['Văn bản hợp đồng tải lên chỉ được dùng cho OCR, phân tích cấu trúc, đánh giá rủi ro và tạo báo cáo.', 'Sau khi phân tích hoàn tất, toàn văn hợp đồng sẽ bị xóa khỏi bộ nhớ hoạt động và không được lưu như bản sao đầy đủ trong cơ sở dữ liệu.', 'Để bạn có thể xem lại bối cảnh của từng kết luận trong vòng 72 giờ, một số trích đoạn điều khoản có thể tạm thời xuất hiện trong báo cáo.'] }],
  },
  {
    title: '4. Chia sẻ với bên thứ ba',
    blocks: [
      { type: 'paragraph', content: ['Chúng tôi không bán thông tin cá nhân. Dữ liệu chỉ được chia sẻ giới hạn với các đơn vị xử lý cần thiết để vận hành dịch vụ.'] },
      { type: 'list', content: ['KOMOJU: xử lý thanh toán.', 'Resend: gửi email báo cáo.', 'OpenAI: OCR, dịch thuật và phân tích hợp đồng. Nội dung hợp đồng chỉ được gửi cho mục đích xử lý.'] },
    ],
  },
  {
    title: '5. Cookie và công nghệ tương tự',
    blocks: [{ type: 'paragraph', content: ['Chúng tôi chủ yếu dùng localStorage của trình duyệt để ghi nhớ ngôn ngữ.', 'Về nguyên tắc chúng tôi không dùng cookie theo dõi quảng cáo, nhưng có thể thu thập thống kê ẩn danh ở mức giới hạn để cải thiện độ ổn định và trải nghiệm.'] }],
  },
  {
    title: '6. Bảo mật',
    blocks: [{ type: 'paragraph', content: ['Chúng tôi dùng kết nối mã hóa và các biện pháp hạ tầng tiêu chuẩn để giảm rủi ro truy cập trái phép.', 'Tuy nhiên, không dịch vụ internet nào có thể bảo đảm an toàn tuyệt đối, vì vậy vui lòng không tải lên thông tin mà bạn không muốn truyền qua mạng.'] }],
  },
  {
    title: '7. Liên hệ',
    blocks: [{ type: 'paragraph', content: ['Nếu có câu hỏi về quyền riêng tư, vui lòng liên hệ với đơn vị vận hành qua email theo thông tin trên trang web.'] }],
  },
];

const TERMS_VI: LegalSection[] = [
  {
    title: '1. Nội dung dịch vụ',
    blocks: [{ type: 'paragraph', content: ['ContractGuard là dịch vụ phân tích rủi ro hợp đồng bằng AI.', 'Khi bạn tải lên hợp đồng tiếng Nhật, hệ thống sẽ trả về cảnh báo rủi ro theo từng điều khoản và gợi ý dễ hiểu bằng ngôn ngữ bạn chọn.'] }],
  },
  {
    title: '2. Không phải tư vấn pháp lý',
    blocks: [{ type: 'paragraph', content: ['Dịch vụ này không phải là hãng luật và không cung cấp đại diện pháp lý hoặc tư vấn luật sư.', 'Mọi kết quả chỉ là thông tin tham khảo do phần mềm tạo ra. Nếu cần đánh giá pháp lý cụ thể, bạn phải tham khảo luật sư hoặc chuyên gia đủ điều kiện.'] }],
  },
  {
    title: '3. Giá và thanh toán',
    blocks: [{ type: 'paragraph', content: ['Dịch vụ được bán theo hình thức trả tiền theo lần sử dụng.', 'Giá được tính dựa trên độ dài hợp đồng và chi phí xử lý; thanh toán được thực hiện qua KOMOJU và các phương thức hiển thị trên màn hình thanh toán.'] }],
  },
  {
    title: '4. Chính sách hoàn tiền',
    blocks: [{ type: 'paragraph', content: ['Sau khi quá trình phân tích đã bắt đầu, về nguyên tắc không thể hoàn tiền vì dịch vụ số đã được thực hiện.', 'Nếu chưa thanh toán xong thì sẽ không bị tính phí; nếu có lỗi hệ thống nghiêm trọng khiến dịch vụ không thể cung cấp, chúng tôi sẽ xem xét từng trường hợp.'] }],
  },
  {
    title: '5. Thời hạn báo cáo',
    blocks: [{ type: 'paragraph', content: ['Báo cáo được tạo sẽ khả dụng trong 72 giờ và sau đó bị xóa tự động.', 'Nếu cần lưu lâu hơn, vui lòng tải PDF hoặc tự lưu trước khi hết hạn.'] }],
  },
  {
    title: '6. Miễn trừ trách nhiệm',
    blocks: [{ type: 'paragraph', content: ['Chúng tôi không bảo đảm kết quả phân tích là đầy đủ, chính xác hoặc phù hợp cho mọi tình huống.', 'Trong phạm vi pháp luật cho phép, chúng tôi không chịu trách nhiệm cho thiệt hại phát sinh do dựa vào báo cáo mà không có sự xem xét của chuyên gia.'] }],
  },
  {
    title: '7. Quyền riêng tư',
    blocks: [{ type: 'paragraph', content: ['Thông tin cá nhân được xử lý theo Chính sách quyền riêng tư riêng. Toàn văn hợp đồng sẽ bị xóa sau khi phân tích hoàn tất.'] }],
  },
  {
    title: '8. Thay đổi điều khoản',
    blocks: [{ type: 'paragraph', content: ['Chúng tôi có thể sửa đổi Điều khoản khi cần thiết. Điều khoản đã cập nhật có hiệu lực khi được đăng trên trang này.'] }],
  },
  {
    title: '9. Luật áp dụng và tòa án',
    blocks: [{ type: 'paragraph', content: ['Điều khoản này được điều chỉnh bởi pháp luật Nhật Bản. Mọi tranh chấp liên quan đến dịch vụ này thuộc thẩm quyền sơ thẩm độc quyền của Tòa án Quận Tokyo.'] }],
  },
];

const PRIVACY_ID: LegalSection[] = [
  {
    title: '1. Definisi informasi pribadi',
    blocks: [{ type: 'paragraph', content: ['Dalam kebijakan ini, informasi pribadi berarti informasi yang dapat mengidentifikasi orang tertentu, seperti alamat email.', 'Teks kontrak lengkap hanya digunakan untuk analisis dan dihapus dari server segera setelah analisis selesai.'] }],
  },
  {
    title: '2. Informasi yang kami kumpulkan',
    blocks: [
      { type: 'paragraph', content: ['Kami hanya mengumpulkan informasi minimum yang diperlukan untuk menjalankan layanan.'] },
      { type: 'list', content: ['Alamat email: hanya untuk mengirim tautan laporan.', 'Bahasa tampilan yang dipilih: disimpan di localStorage browser dan tidak dipakai untuk profiling pengguna.', 'Informasi pesanan dan status pembayaran: diperlukan untuk menyelesaikan checkout dan mengirim laporan.'] },
    ],
  },
  {
    title: '3. Penanganan teks kontrak',
    blocks: [{ type: 'paragraph', content: ['Teks kontrak yang diunggah hanya diproses untuk OCR, pemetaan struktur, analisis risiko, dan pembuatan laporan.', 'Setelah analisis selesai, teks penuh dihapus dari penyimpanan aktif dan tidak disimpan sebagai salinan lengkap di database.', 'Agar Anda dapat meninjau kembali konteks tiap temuan dalam masa berlaku 72 jam, kutipan klausul tertentu dapat tetap muncul sementara di dalam laporan.'] }],
  },
  {
    title: '4. Berbagi dengan pihak ketiga',
    blocks: [
      { type: 'paragraph', content: ['Kami tidak menjual informasi pribadi. Data hanya dibagikan secara terbatas kepada pemroses yang diperlukan untuk menjalankan layanan.'] },
      { type: 'list', content: ['KOMOJU: pemrosesan pembayaran.', 'Resend: pengiriman email laporan.', 'OpenAI: OCR, penerjemahan, dan analisis kontrak. Teks kontrak hanya dikirim untuk tujuan pemrosesan.'] },
    ],
  },
  {
    title: '5. Cookie dan teknologi serupa',
    blocks: [{ type: 'paragraph', content: ['Kami terutama menggunakan localStorage browser untuk mengingat preferensi bahasa.', 'Kami pada prinsipnya tidak menggunakan cookie pelacakan iklan, tetapi dapat mengumpulkan statistik anonim terbatas untuk meningkatkan keandalan dan pengalaman penggunaan.'] }],
  },
  {
    title: '6. Keamanan',
    blocks: [{ type: 'paragraph', content: ['Kami menggunakan koneksi terenkripsi dan langkah keamanan infrastruktur standar untuk mengurangi risiko akses tanpa izin.', 'Namun, tidak ada layanan internet yang dapat menjamin keamanan mutlak, jadi jangan unggah informasi yang tidak nyaman Anda kirimkan secara online.'] }],
  },
  {
    title: '7. Kontak',
    blocks: [{ type: 'paragraph', content: ['Untuk pertanyaan terkait privasi, silakan hubungi operator melalui email menggunakan informasi kontak yang ditampilkan di situs ini.'] }],
  },
];

const TERMS_ID: LegalSection[] = [
  {
    title: '1. Gambaran layanan',
    blocks: [{ type: 'paragraph', content: ['ContractGuard adalah layanan analisis risiko kontrak berbasis AI.', 'Saat Anda mengunggah kontrak berbahasa Jepang, layanan ini mengembalikan penjelasan risiko per klausul dan saran yang mudah dipahami dalam bahasa pilihan Anda.'] }],
  },
  {
    title: '2. Bukan nasihat hukum',
    blocks: [{ type: 'paragraph', content: ['Layanan ini bukan firma hukum dan tidak memberikan representasi hukum atau nasihat pengacara.', 'Semua keluaran adalah informasi referensi yang dihasilkan perangkat lunak. Jika Anda memerlukan penilaian hukum yang spesifik, Anda harus berkonsultasi dengan pengacara atau profesional yang berkualifikasi.'] }],
  },
  {
    title: '3. Harga dan pembayaran',
    blocks: [{ type: 'paragraph', content: ['Layanan ini dijual per penggunaan.', 'Harga dihitung berdasarkan panjang kontrak dan biaya pemrosesan. Pembayaran dilakukan melalui KOMOJU dan metode pembayaran yang ditampilkan saat checkout.'] }],
  },
  {
    title: '4. Kebijakan refund',
    blocks: [{ type: 'paragraph', content: ['Setelah proses analisis dimulai, refund pada prinsipnya tidak tersedia karena layanan digital sudah mulai diberikan.', 'Jika pembayaran belum selesai, Anda tidak akan dikenai biaya. Jika terjadi masalah sistem serius yang mencegah penyampaian hasil, kami akan meninjau kasus tersebut secara individual.'] }],
  },
  {
    title: '5. Masa berlaku laporan',
    blocks: [{ type: 'paragraph', content: ['Laporan yang dihasilkan tersedia selama 72 jam dan kemudian dihapus secara otomatis.', 'Jika Anda perlu menyimpannya lebih lama, unduh PDF atau simpan sendiri sebelum masa berlaku berakhir.'] }],
  },
  {
    title: '6. Penafian',
    blocks: [{ type: 'paragraph', content: ['Kami tidak menjamin bahwa hasil analisis akan lengkap, bebas kesalahan, atau cocok untuk setiap situasi.', 'Sejauh diizinkan oleh hukum, operator tidak bertanggung jawab atas kerugian yang timbul karena mengandalkan laporan tanpa peninjauan profesional.'] }],
  },
  {
    title: '7. Privasi',
    blocks: [{ type: 'paragraph', content: ['Informasi pribadi ditangani sesuai Kebijakan Privasi yang terpisah. Teks kontrak lengkap dihapus setelah analisis selesai.'] }],
  },
  {
    title: '8. Perubahan ketentuan',
    blocks: [{ type: 'paragraph', content: ['Kami dapat mengubah Ketentuan ini bila diperlukan. Ketentuan yang diperbarui berlaku saat dipublikasikan di halaman ini.'] }],
  },
  {
    title: '9. Hukum yang berlaku dan yurisdiksi',
    blocks: [{ type: 'paragraph', content: ['Ketentuan ini diatur oleh hukum Jepang. Sengketa terkait layanan ini tunduk pada yurisdiksi eksklusif Pengadilan Distrik Tokyo sebagai pengadilan tingkat pertama.'] }],
  },
];

const PRIVACY_PT_BR: LegalSection[] = [
  {
    title: '1. Definição de informações pessoais',
    blocks: [{ type: 'paragraph', content: ['Nesta política, informações pessoais significam dados que podem identificar uma pessoa específica, como endereço de email.', 'O texto integral do contrato é usado apenas para análise e é removido do servidor imediatamente após a conclusão do processamento.'] }],
  },
  {
    title: '2. Informações que coletamos',
    blocks: [
      { type: 'paragraph', content: ['Coletamos apenas o mínimo necessário para operar o serviço.'] },
      { type: 'list', content: ['Endereço de email: apenas para enviar o link do relatório.', 'Idioma selecionado: armazenado no localStorage do navegador e não usado para perfilização.', 'Informações de pedido e status de pagamento: necessárias para concluir a cobrança e entregar o relatório.'] },
    ],
  },
  {
    title: '3. Como tratamos o texto do contrato',
    blocks: [{ type: 'paragraph', content: ['O texto do contrato enviado é processado apenas para OCR, estruturação, análise de risco e geração do relatório.', 'Depois que a análise termina, o texto integral é removido do armazenamento ativo e não permanece como cópia completa no banco de dados.', 'Para permitir a revisão do contexto de cada conclusão dentro da validade de 72 horas, alguns trechos de cláusulas podem permanecer temporariamente no relatório.'] }],
  },
  {
    title: '4. Compartilhamento com terceiros',
    blocks: [
      { type: 'paragraph', content: ['Não vendemos informações pessoais. Compartilhamos dados limitados apenas com processadores necessários para operar o serviço.'] },
      { type: 'list', content: ['KOMOJU: processamento de pagamento.', 'Resend: envio do email do relatório.', 'OpenAI: OCR, tradução e análise do contrato. O texto do contrato é enviado apenas para processamento.'] },
    ],
  },
  {
    title: '5. Cookies e tecnologias semelhantes',
    blocks: [{ type: 'paragraph', content: ['Usamos principalmente o localStorage do navegador para lembrar a preferência de idioma.', 'Em princípio, não usamos cookies de rastreamento publicitário, mas podemos coletar estatísticas anônimas limitadas para melhorar a estabilidade e a experiência do produto.'] }],
  },
  {
    title: '6. Segurança',
    blocks: [{ type: 'paragraph', content: ['Usamos conexões criptografadas e medidas padrão de segurança de infraestrutura para reduzir o risco de acesso não autorizado.', 'Ainda assim, nenhum serviço na internet pode garantir segurança absoluta; evite enviar informações que você não se sinta confortável em transmitir online.'] }],
  },
  {
    title: '7. Contato',
    blocks: [{ type: 'paragraph', content: ['Se tiver dúvidas sobre privacidade, entre em contato com a operadora por email usando o meio indicado neste site.'] }],
  },
];

const TERMS_PT_BR: LegalSection[] = [
  {
    title: '1. Visão geral do serviço',
    blocks: [{ type: 'paragraph', content: ['ContractGuard é um serviço de análise de risco contratual com IA.', 'Ao enviar um contrato em japonês, o serviço devolve observações de risco por cláusula e sugestões em linguagem simples no idioma selecionado.'] }],
  },
  {
    title: '2. Não é aconselhamento jurídico',
    blocks: [{ type: 'paragraph', content: ['Este serviço não é um escritório de advocacia e não fornece representação legal nem aconselhamento de advogado.', 'Todos os resultados são informações de referência geradas por software. Se você precisar de avaliação jurídica específica, deve consultar um advogado ou outro profissional qualificado.'] }],
  },
  {
    title: '3. Preço e pagamento',
    blocks: [{ type: 'paragraph', content: ['O serviço é vendido por uso.', 'O preço depende do tamanho do contrato e do custo de processamento. O pagamento é realizado via KOMOJU e pelos métodos exibidos no checkout.'] }],
  },
  {
    title: '4. Política de reembolso',
    blocks: [{ type: 'paragraph', content: ['Depois que a análise começa, o reembolso geralmente não é possível porque o serviço digital já foi iniciado.', 'Se o pagamento ainda não foi concluído, nenhuma cobrança é feita. Se uma falha grave do sistema impedir a entrega, analisaremos o caso individualmente.'] }],
  },
  {
    title: '5. Disponibilidade do relatório',
    blocks: [{ type: 'paragraph', content: ['Os relatórios gerados ficam disponíveis por 72 horas e depois são removidos automaticamente.', 'Se precisar mantê-los por mais tempo, baixe o PDF ou salve o conteúdo antes do vencimento.'] }],
  },
  {
    title: '6. Isenção de responsabilidade',
    blocks: [{ type: 'paragraph', content: ['Não garantimos que a análise seja completa, isenta de erros ou adequada para toda situação.', 'Na máxima extensão permitida por lei, a operadora não se responsabiliza por perdas decorrentes do uso do relatório sem revisão profissional.'] }],
  },
  {
    title: '7. Privacidade',
    blocks: [{ type: 'paragraph', content: ['As informações pessoais são tratadas de acordo com a Política de Privacidade separada. O texto integral do contrato é removido após a análise.'] }],
  },
  {
    title: '8. Alterações destes termos',
    blocks: [{ type: 'paragraph', content: ['Podemos revisar estes Termos quando necessário. Os Termos atualizados entram em vigor quando publicados nesta página.'] }],
  },
  {
    title: '9. Lei aplicável e foro',
    blocks: [{ type: 'paragraph', content: ['Estes Termos são regidos pela lei japonesa. O Tribunal Distrital de Tóquio tem jurisdição exclusiva como tribunal de primeira instância para disputas relacionadas a este serviço.'] }],
  },
];

const PRIVACY_NE: LegalSection[] = [
  {
    title: '१. व्यक्तिगत जानकारीको परिभाषा',
    blocks: [{ type: 'paragraph', content: ['यस नीतिमा व्यक्तिगत जानकारी भन्नाले इमेल ठेगाना जस्ता कुनै व्यक्तिलाई पहिचान गर्न सकिने जानकारी बुझिन्छ।', 'सम्झौता पत्रको पूर्ण पाठ केवल विश्लेषणका लागि प्रयोग गरिन्छ र विश्लेषण सकिएपछि सर्भरबाट तुरुन्त मेटाइन्छ।'] }],
  },
  {
    title: '२. हामीले सङ्कलन गर्ने जानकारी',
    blocks: [
      { type: 'paragraph', content: ['सेवा सञ्चालनका लागि आवश्यक न्यूनतम जानकारी मात्र सङ्कलन गरिन्छ।'] },
      { type: 'list', content: ['इमेल ठेगाना: रिपोर्ट लिंक पठाउन मात्र।', 'छानिएको भाषा: ब्राउजरको localStorage मा सुरक्षित हुन्छ, प्रयोगकर्ता प्रोफाइल बनाउन प्रयोग हुँदैन।', 'अर्डर र भुक्तानी स्थिति: चेकआउट पूरा गर्न र रिपोर्ट उपलब्ध गराउन आवश्यक।'] },
    ],
  },
  {
    title: '३. सम्झौता पाठको प्रयोग',
    blocks: [{ type: 'paragraph', content: ['अपलोड गरिएको सम्झौता पाठ OCR, संरचना पहिचान, जोखिम विश्लेषण र रिपोर्ट तयार गर्न मात्र प्रयोग हुन्छ।', 'विश्लेषण सकिएपछि पूर्ण पाठ सक्रिय भण्डारणबाट हटाइन्छ र डेटाबेसमा पूर्ण प्रतिलिपिका रूपमा राखिँदैन।', '७२ घण्टे वैधता अवधिमा प्रत्येक निष्कर्षको सन्दर्भ देखाउन केही सानातिना धारा अंश रिपोर्टमा अस्थायी रूपमा रहन सक्छन्।'] }],
  },
  {
    title: '४. तेस्रो पक्षसँग साझेदारी',
    blocks: [
      { type: 'paragraph', content: ['हामी व्यक्तिगत जानकारी बेच्दैनौं। सेवा सञ्चालनका लागि आवश्यक सीमित प्रोसेसरसँग मात्र जानकारी साझा गरिन्छ।'] },
      { type: 'list', content: ['KOMOJU: भुक्तानी प्रक्रिया।', 'Resend: रिपोर्ट इमेल पठाउन।', 'OpenAI: OCR, अनुवाद र सम्झौता विश्लेषण। सम्झौता पाठ केवल प्रक्रिया उद्देश्यका लागि पठाइन्छ।'] },
    ],
  },
  {
    title: '५. कुकी र समान प्रविधि',
    blocks: [{ type: 'paragraph', content: ['हामी मुख्य रूपमा भाषा प्राथमिकता सम्झन ब्राउजर localStorage प्रयोग गर्छौं।', 'विज्ञापन ट्र्याकिङ कुकी सिद्धान्ततः प्रयोग गर्दैनौं, तर सेवा सुधारका लागि सीमित गुमनाम तथ्याङ्क सङ्कलन हुन सक्छ।'] }],
  },
  {
    title: '६. सुरक्षा',
    blocks: [{ type: 'paragraph', content: ['हामी इन्क्रिप्टेड कनेक्सन र मानक पूर्वाधार सुरक्षा उपाय प्रयोग गर्छौं।', 'तर कुनै पनि इन्टरनेट सेवाले पूर्ण सुरक्षा ग्यारेन्टी गर्न सक्दैन, त्यसैले अनलाइन पठाउन असहज हुने जानकारी अपलोड नगर्नुहोस्।'] }],
  },
  {
    title: '७. सम्पर्क',
    blocks: [{ type: 'paragraph', content: ['गोपनीयता सम्बन्धी प्रश्न भए साइटमा देखाइएको सम्पर्क माध्यमबाट इमेल गर्नुहोस्।'] }],
  },
];

const TERMS_NE: LegalSection[] = [
  {
    title: '१. सेवाको सार',
    blocks: [{ type: 'paragraph', content: ['ContractGuard AI आधारित सम्झौता जोखिम विश्लेषण सेवा हो।', 'तपाईंले जापानी सम्झौता अपलोड गरेपछि, सेवाले धारा-धारा जोखिम बिन्दु र सजिलो सुझाव तपाईंले छानेको भाषामा देखाउँछ।'] }],
  },
  {
    title: '२. यो कानुनी सल्लाह होइन',
    blocks: [{ type: 'paragraph', content: ['यो सेवा कानुनी फर्म होइन र कानुनी प्रतिनिधित्व वा वकिलीय सल्लाह प्रदान गर्दैन।', 'सबै नतिजा सफ्टवेयरले बनाएको सन्दर्भ सामग्री मात्र हुन्। विशेष कानुनी निर्णय आवश्यक परे योग्य वकिल वा विशेषज्ञसँग परामर्श गर्नुहोस्।'] }],
  },
  {
    title: '३. शुल्क र भुक्तानी',
    blocks: [{ type: 'paragraph', content: ['यो सेवा प्रत्येक प्रयोग अनुसार शुल्क लाग्ने मोडेलमा उपलब्ध छ।', 'शुल्क सम्झौताको लम्बाइ र प्रशोधन लागतका आधारमा निर्धारण हुन्छ, र भुक्तानी KOMOJU तथा चेकआउटमा देखाइएका भुक्तानी साधनमार्फत हुन्छ।'] }],
  },
  {
    title: '४. फिर्ता नीति',
    blocks: [{ type: 'paragraph', content: ['विश्लेषण प्रक्रिया सुरु भएपछि, डिजिटल सेवा सुरु भइसकेकाले सामान्यतया रकम फिर्ता हुँदैन।', 'भुक्तानी पूरा नभएसम्म शुल्क लाग्दैन। यदि गम्भीर प्रणाली समस्या कारण सेवा दिन सकिएन भने, हामी केस अनुसार जाँच गर्छौं।'] }],
  },
  {
    title: '५. रिपोर्ट उपलब्ध अवधि',
    blocks: [{ type: 'paragraph', content: ['बनाइएको रिपोर्ट ७२ घण्टा उपलब्ध रहन्छ र त्यसपछि स्वतः मेटाइन्छ।', 'लामो समय राख्न आवश्यक भए समयसीमा सकिनुअघि PDF डाउनलोड वा स्वयं सुरक्षित गर्नुहोस्।'] }],
  },
  {
    title: '६. दायित्व अस्वीकरण',
    blocks: [{ type: 'paragraph', content: ['हामी विश्लेषण सबै अवस्थामा पूर्ण, त्रुटिरहित वा उपयुक्त हुनेछ भन्ने ग्यारेन्टी गर्दैनौं।', 'पेशेवर समीक्षा बिना रिपोर्टमा निर्भर भई भएको क्षतिका लागि कानुनले अनुमति दिएको हदसम्म हामी जिम्मेवार हुँदैनौं।'] }],
  },
  {
    title: '७. गोपनीयता',
    blocks: [{ type: 'paragraph', content: ['व्यक्तिगत जानकारी छुट्टै गोपनीयता नीतिअनुसार सञ्चालन हुन्छ। सम्झौताको पूर्ण पाठ विश्लेषणपछि मेटाइन्छ।'] }],
  },
  {
    title: '८. नियम परिवर्तन',
    blocks: [{ type: 'paragraph', content: ['आवश्यक परे यी नियम परिवर्तन गर्न सकिन्छ। अद्यावधिक नियम यस पृष्ठमा प्रकाशित भएपछि लागू हुन्छन्।'] }],
  },
  {
    title: '९. लागू हुने कानुन र क्षेत्राधिकार',
    blocks: [{ type: 'paragraph', content: ['यी नियम जापानी कानुनअन्तर्गत व्याख्या गरिन्छन्। यस सेवासँग सम्बन्धित विवादका लागि टोक्यो जिल्ला अदालत पहिलो श्रेणीको विशेष सहमति अदालत हुनेछ।'] }],
  },
];

const LEGAL_COPY: Record<SupportedLegalLanguage, LegalCopy> = {
  ja: {
    privacy: {
      noticeTitle: 'この日本語本文が正式版です。',
      noticeBody: '法的な解釈が必要な場合は、この日本語版を基準としてご確認ください。',
      officialSummary: '以下は正式な日本語本文です。',
      officialToggleLabel: '日本語版（正式版）を表示',
      sections: PRIVACY_JP,
    },
    terms: {
      noticeTitle: 'この日本語本文が正式版です。',
      noticeBody: '翻訳版との間に差異が生じる場合は、この日本語版が優先します。',
      officialSummary: '以下は正式な日本語本文です。',
      officialToggleLabel: '日本語版（正式版）を表示',
      sections: TERMS_JP,
    },
  },
  en: {
    privacy: {
      noticeTitle: 'This translation is provided for reference.',
      noticeBody: 'The official controlling version is the Japanese text shown below. If there is any inconsistency, the Japanese version prevails.',
      officialSummary: 'Official Japanese version',
      officialToggleLabel: 'Show official Japanese text',
      sections: PRIVACY_EN,
    },
    terms: {
      noticeTitle: 'This translation is provided for reference.',
      noticeBody: 'The official controlling version is the Japanese text shown below. If there is any inconsistency, the Japanese version prevails.',
      officialSummary: 'Official Japanese version',
      officialToggleLabel: 'Show official Japanese text',
      sections: TERMS_EN,
    },
  },
  'zh-CN': {
    privacy: {
      noticeTitle: '当前翻译版仅供参考。',
      noticeBody: '下方日文版为正式有效版本。如翻译内容与日文版存在差异，以日文版为准。',
      officialSummary: '日文正式版',
      officialToggleLabel: '查看日文正式版',
      sections: PRIVACY_ZH_CN,
    },
    terms: {
      noticeTitle: '当前翻译版仅供参考。',
      noticeBody: '下方日文版为正式有效版本。如翻译内容与日文版存在差异，以日文版为准。',
      officialSummary: '日文正式版',
      officialToggleLabel: '查看日文正式版',
      sections: TERMS_ZH_CN,
    },
  },
  'zh-TW': {
    privacy: {
      noticeTitle: '目前翻譯版僅供參考。',
      noticeBody: '下方日文版為正式有效版本；若翻譯內容與日文版不一致，以日文版為準。',
      officialSummary: '日文正式版',
      officialToggleLabel: '查看日文正式版',
      sections: PRIVACY_ZH_TW,
    },
    terms: {
      noticeTitle: '目前翻譯版僅供參考。',
      noticeBody: '下方日文版為正式有效版本；若翻譯內容與日文版不一致，以日文版為準。',
      officialSummary: '日文正式版',
      officialToggleLabel: '查看日文正式版',
      sections: TERMS_ZH_TW,
    },
  },
  ko: {
    privacy: {
      noticeTitle: '현재 번역본은 참고용입니다.',
      noticeBody: '아래의 일본어 본문이 공식 기준 버전이며, 내용 차이가 있을 경우 일본어 버전이 우선합니다.',
      officialSummary: '공식 일본어 버전',
      officialToggleLabel: '일본어 공식 본문 보기',
      sections: PRIVACY_KO,
    },
    terms: {
      noticeTitle: '현재 번역본은 참고용입니다.',
      noticeBody: '아래의 일본어 본문이 공식 기준 버전이며, 내용 차이가 있을 경우 일본어 버전이 우선합니다.',
      officialSummary: '공식 일본어 버전',
      officialToggleLabel: '일본어 공식 본문 보기',
      sections: TERMS_KO,
    },
  },
  vi: {
    privacy: {
      noticeTitle: 'Bản dịch này chỉ để tham khảo.',
      noticeBody: 'Bản tiếng Nhật bên dưới là bản chính thức có giá trị ưu tiên. Nếu có khác biệt, bản tiếng Nhật sẽ được áp dụng.',
      officialSummary: 'Bản tiếng Nhật chính thức',
      officialToggleLabel: 'Xem bản tiếng Nhật chính thức',
      sections: PRIVACY_VI,
    },
    terms: {
      noticeTitle: 'Bản dịch này chỉ để tham khảo.',
      noticeBody: 'Bản tiếng Nhật bên dưới là bản chính thức có giá trị ưu tiên. Nếu có khác biệt, bản tiếng Nhật sẽ được áp dụng.',
      officialSummary: 'Bản tiếng Nhật chính thức',
      officialToggleLabel: 'Xem bản tiếng Nhật chính thức',
      sections: TERMS_VI,
    },
  },
  id: {
    privacy: {
      noticeTitle: 'Versi terjemahan ini hanya untuk referensi.',
      noticeBody: 'Versi resmi yang mengikat adalah teks bahasa Jepang di bawah. Jika ada perbedaan, versi Jepang yang berlaku.',
      officialSummary: 'Versi resmi bahasa Jepang',
      officialToggleLabel: 'Lihat teks resmi bahasa Jepang',
      sections: PRIVACY_ID,
    },
    terms: {
      noticeTitle: 'Versi terjemahan ini hanya untuk referensi.',
      noticeBody: 'Versi resmi yang mengikat adalah teks bahasa Jepang di bawah. Jika ada perbedaan, versi Jepang yang berlaku.',
      officialSummary: 'Versi resmi bahasa Jepang',
      officialToggleLabel: 'Lihat teks resmi bahasa Jepang',
      sections: TERMS_ID,
    },
  },
  'pt-BR': {
    privacy: {
      noticeTitle: 'Esta tradução é apenas para referência.',
      noticeBody: 'A versão oficial aplicável é o texto em japonês exibido abaixo. Em caso de divergência, prevalece a versão em japonês.',
      officialSummary: 'Versão oficial em japonês',
      officialToggleLabel: 'Ver texto oficial em japonês',
      sections: PRIVACY_PT_BR,
    },
    terms: {
      noticeTitle: 'Esta tradução é apenas para referência.',
      noticeBody: 'A versão oficial aplicável é o texto em japonês exibido abaixo. Em caso de divergência, prevalece a versão em japonês.',
      officialSummary: 'Versão oficial em japonês',
      officialToggleLabel: 'Ver texto oficial em japonês',
      sections: TERMS_PT_BR,
    },
  },
  ne: {
    privacy: {
      noticeTitle: 'यो अनुवाद केवल सन्दर्भका लागि हो।',
      noticeBody: 'तलको जापानी पाठ नै औपचारिक मान्य संस्करण हो। फरक देखिएमा जापानी संस्करण लागू हुन्छ।',
      officialSummary: 'आधिकारिक जापानी संस्करण',
      officialToggleLabel: 'आधिकारिक जापानी पाठ हेर्नुहोस्',
      sections: PRIVACY_NE,
    },
    terms: {
      noticeTitle: 'यो अनुवाद केवल सन्दर्भका लागि हो।',
      noticeBody: 'तलको जापानी पाठ नै औपचारिक मान्य संस्करण हो। फरक देखिएमा जापानी संस्करण लागू हुन्छ।',
      officialSummary: 'आधिकारिक जापानी संस्करण',
      officialToggleLabel: 'आधिकारिक जापानी पाठ हेर्नुहोस्',
      sections: TERMS_NE,
    },
  },
};

export function resolveLegalLanguage(language: string): SupportedLegalLanguage {
  if (language.startsWith('ja')) return 'ja';
  if (language.startsWith('en')) return 'en';
  if (language.startsWith('zh-CN')) return 'zh-CN';
  if (language.startsWith('zh-TW')) return 'zh-TW';
  if (language.startsWith('ko')) return 'ko';
  if (language.startsWith('vi')) return 'vi';
  if (language.startsWith('id')) return 'id';
  if (language.startsWith('pt-BR') || language.startsWith('pt')) return 'pt-BR';
  if (language.startsWith('ne')) return 'ne';
  return 'en';
}

export function getPrivacyCopy(language: string): LegalDocumentCopy {
  return LEGAL_COPY[resolveLegalLanguage(language)].privacy;
}

export function getTermsCopy(language: string): LegalDocumentCopy {
  return LEGAL_COPY[resolveLegalLanguage(language)].terms;
}

export const OFFICIAL_PRIVACY_SECTIONS = PRIVACY_JP;
export const OFFICIAL_TERMS_SECTIONS = TERMS_JP;
