// Mock example report data for the homepage showcase section.
// Translatable fields (risk_reason, suggestion) are in i18n locale files
// under keys like examples.rental_c1_reason / examples.rental_c1_suggestion.
// original_text, referenced_law, and clause_number stay in Japanese.

export interface ExampleClause {
  clause_number: string;
  original_text: string;
  risk_level: string;
  referenced_law: string;
}

export interface ExampleReport {
  id: string;
  overall_risk: string;
  clauses: ExampleClause[];
}

export const exampleReports: Record<string, ExampleReport> = {
  rental: {
    id: 'rental',
    overall_risk: '中',
    clauses: [
      {
        clause_number: '第5条（原状回復）',
        original_text:
          '乙は、本物件を明け渡す際、自然損耗及び経年変化を含む全ての損耗について原状回復を行い、その費用を負担するものとする。',
        risk_level: '高',
        referenced_law: '民法第621条、国土交通省「原状回復をめぐるトラブルとガイドライン」',
      },
      {
        clause_number: '第8条（中途解約）',
        original_text:
          '乙は、契約期間中に本契約を解約する場合、6ヶ月前までに甲に書面で通知し、違約金として賃料3ヶ月分を支払うものとする。',
        risk_level: '中',
        referenced_law: '借地借家法第27条、第28条',
      },
      {
        clause_number: '第12条（更新料）',
        original_text:
          '本契約の更新に際し、乙は更新料として賃料1ヶ月分を甲に支払うものとする。',
        risk_level: '低',
        referenced_law: '最高裁判所平成23年7月15日判決',
      },
    ],
  },

  employment: {
    id: 'employment',
    overall_risk: '中',
    clauses: [
      {
        clause_number: '第9条（競業避止）',
        original_text:
          '従業員は、退職後2年間、日本国内において同業他社への就職及び競合事業の開始を行ってはならない。違反した場合、退職金の全額返還及び損害賠償を求めることができる。',
        risk_level: '高',
        referenced_law: '労働契約法第16条、東京地裁判例（競業避止の合理性判断基準）',
      },
      {
        clause_number: '第6条（試用期間）',
        original_text:
          '試用期間は入社日から6ヶ月間とし、会社が適格性を欠くと判断した場合、試用期間中又は期間満了時に本採用を拒否することができる。',
        risk_level: '中',
        referenced_law: '労働基準法第20条、第21条',
      },
    ],
  },

  parttime: {
    id: 'parttime',
    overall_risk: '中',
    clauses: [
      {
        clause_number: '第4条（勤務時間）',
        original_text:
          '勤務時間はシフトにより決定し、業務の都合により所定労働時間を超えて勤務を命じることがある。時間外勤務に対する割増賃金は、月40時間を超えた部分についてのみ支払うものとする。',
        risk_level: '高',
        referenced_law: '労働基準法第32条、第37条',
      },
      {
        clause_number: '第10条（損害賠償）',
        original_text:
          '従業員の故意又は過失により会社に損害を与えた場合、その全額を賠償するものとする。また、制服・備品の紛失については、実費相当額を給与から控除することができる。',
        risk_level: '中',
        referenced_law: '労働基準法第24条（賃金全額払いの原則）、民法第715条',
      },
    ],
  },
};
