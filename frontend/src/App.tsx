import { useState } from "react";

interface ClauseAnalysis {
  clause_number: string;
  risk_level: string;
  risk_reason: string;
  suggestion: string;
  referenced_law: string;
}

interface ReviewReport {
  overall_risk_level: string;
  summary: string;
  clause_analyses: ClauseAnalysis[];
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  total_clauses: number;
}

interface StreamEvent {
  type: "node_start" | "token" | "tool_call" | "complete" | "error";
  node?: string;
  label?: string;
  text?: string;
  tool?: string;
  clause?: string;
  report?: ReviewReport;
  message?: string;
}

const SAMPLE_CONTRACT = `業務委託契約書

委託者 株式会社テック・ソリューションズ（以下「甲」という）と受託者 山田太郎（以下「乙」という）は、以下のとおり業務委託契約（以下「本契約」という）を締結する。

第1条（委託内容）
甲は乙に対し、ソフトウェア開発に関する業務（以下「本業務」という）を委託し、乙はこれを受託する。業務の具体的な内容は、甲乙協議の上、別途定めるものとする。

第2条（契約期間）
本契約の期間は、2024年4月1日から2025年3月31日までとする。ただし、期間満了の1ヶ月前までに甲乙いずれからも書面による解約の申し出がない場合は、同条件で1年間自動更新されるものとし、以後も同様とする。

第3条（報酬）
甲は乙に対し、本業務の報酬として月額50万円（税別）を支払うものとする。支払いは、毎月末日締め、翌月末日払いとする。

第4条（秘密保持）
乙は、本業務に関連して知り得た甲の業務上の秘密情報を、本契約期間中はもちろん、本契約終了後も無期限に第三者に開示・漏洩してはならない。

第5条（損害賠償）
乙は、本業務の遂行に関して甲に損害を与えた場合、その損害の全額を賠償するものとする。なお、甲の乙に対する損害賠償額には上限を設けないものとする。

第6条（競業避止）
乙は、本契約期間中および本契約終了後5年間、甲の事前の書面による承諾なく、日本国内において甲と競合する事業を直接的または間接的に行ってはならない。なお、本条に違反した場合、乙は甲に対し違約金として金1000万円を支払うものとする。

第7条（契約解除）
甲は、理由の如何を問わず、いつでも本契約を即時に解除することができる。この場合、甲は乙に対して何らの補償も行わない。乙は、甲の書面による承諾がある場合に限り、3ヶ月前の予告をもって本契約を解除することができる。

第8条（知的財産権）
本業務により生じた一切の成果物に関する知的財産権（著作権法第27条及び第28条に規定する権利を含む）は、その発生と同時に甲に帰属するものとする。

第9条（準拠法・管轄）
本契約は日本法に準拠し、本契約に関する一切の紛争については、東京地方裁判所を第一審の専属的合意管轄裁判所とする。`;

function riskColor(level: string): string {
  switch (level) {
    case "高":
      return "#dc2626";
    case "中":
      return "#f59e0b";
    case "低":
      return "#16a34a";
    default:
      return "#6b7280";
  }
}

function riskBg(level: string): string {
  switch (level) {
    case "高":
      return "#fef2f2";
    case "中":
      return "#fffbeb";
    case "低":
      return "#f0fdf4";
    default:
      return "#f9fafb";
  }
}

export default function App() {
  const [contractText, setContractText] = useState(SAMPLE_CONTRACT);
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentLines, setRecentLines] = useState<string[]>([]);

  const pushLine = (line: string) =>
    setRecentLines((prev) => [...prev, line].slice(-3));

  const handleReview = async () => {
    if (!contractText.trim()) return;
    setLoading(true);
    setError(null);
    setReport(null);
    setRecentLines([]);

    try {
      const res = await fetch("/api/review/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contract_text: contractText }),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const evt: StreamEvent = JSON.parse(line.slice(6));
          if (evt.type === "node_start") {
            pushLine(evt.label!);
          } else if (evt.type === "tool_call") {
            const icon = evt.tool === "analyze_clause_risk" ? "🔍" : "💡";
            pushLine(`${icon} ${evt.clause}`);
          } else if (evt.type === "complete") {
            setReport(evt.report!);
            setLoading(false);
          } else if (evt.type === "error") {
            setError(evt.message!);
            setLoading(false);
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <header>
        <h1>法律契約審査 AI Agent</h1>
        <p className="subtitle">
          LangGraph + RAG + MCP による日本語契約書リスク分析
        </p>
      </header>

      <div className="main-grid">
        <section className="input-section">
          <h2>契約書テキスト</h2>
          <textarea
            value={contractText}
            onChange={(e) => setContractText(e.target.value)}
            placeholder="契約書のテキストをここに貼り付けてください..."
            rows={20}
          />
          <button onClick={handleReview} disabled={loading || !contractText.trim()}>
            {loading ? "審査中..." : "契約書を審査する"}
          </button>
        </section>

        <section className="report-section">
          <h2>審査レポート</h2>
          {loading && (
            <div className="loading">
              <div className="spinner" />
              <div className="recent-log">
                {recentLines.map((line, i) => (
                  <p key={i} className="recent-log-line">{line}</p>
                ))}
              </div>
            </div>
          )}
          {error && <div className="error">エラー: {error}</div>}
          {report && (
            <div className="report">
              <div
                className="overall-risk"
                style={{
                  borderColor: riskColor(report.overall_risk_level),
                  background: riskBg(report.overall_risk_level),
                }}
              >
                <span className="risk-badge" style={{ background: riskColor(report.overall_risk_level) }}>
                  総合リスク: {report.overall_risk_level}
                </span>
                <p>{report.summary}</p>
                <div className="risk-stats">
                  <span className="stat high">高リスク: {report.high_risk_count}</span>
                  <span className="stat medium">中リスク: {report.medium_risk_count}</span>
                  <span className="stat low">低リスク: {report.low_risk_count}</span>
                </div>
              </div>

              <div className="clauses">
                {report.clause_analyses.map((clause, idx) => (
                  <div
                    key={idx}
                    className="clause-card"
                    style={{
                      borderLeftColor: riskColor(clause.risk_level),
                      background: riskBg(clause.risk_level),
                    }}
                  >
                    <div className="clause-header">
                      <strong>{clause.clause_number}</strong>
                      <span
                        className="risk-tag"
                        style={{ background: riskColor(clause.risk_level) }}
                      >
                        {clause.risk_level}
                      </span>
                    </div>
                    <p className="risk-reason">{clause.risk_reason}</p>
                    {clause.suggestion && (
                      <div className="suggestion">
                        <strong>修正提案:</strong>
                        <p>{clause.suggestion}</p>
                      </div>
                    )}
                    {clause.referenced_law && (
                      <div className="reference">
                        <strong>参照法律:</strong>
                        <p>{clause.referenced_law}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {!loading && !error && !report && (
            <p className="placeholder">左側に契約書を入力して「審査する」をクリックしてください。</p>
          )}
        </section>
      </div>
    </div>
  );
}
