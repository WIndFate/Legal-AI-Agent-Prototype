// Mock example report data for the homepage showcase section.
// Content is in Chinese (primary target users) with Japanese original clause text.

export interface ExampleClause {
  clause_number: string;
  original_text: string;
  risk_level: string;
  risk_reason: string;
  suggestion: string;
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
        risk_reason:
          '该条款要求租户承担包括自然损耗在内的所有修复费用。根据日本民法和国土交通省指南，自然损耗和正常老化应由房东负担，此条款可能对租户不公平。',
        suggestion:
          '建议修改为"乙は、故意又は過失により生じた損耗について原状回復を行う"，明确排除自然损耗的修复义务。',
        referenced_law: '民法第621条、国土交通省「原状回復をめぐるトラブルとガイドライン」',
      },
      {
        clause_number: '第8条（中途解約）',
        original_text:
          '乙は、契約期間中に本契約を解約する場合、6ヶ月前までに甲に書面で通知し、違約金として賃料3ヶ月分を支払うものとする。',
        risk_level: '中',
        risk_reason:
          '6个月的提前通知期和3个月的违约金虽然在日本租赁市场存在，但通常标准为1-2个月。此条件较为严格，建议确认是否有协商空间。',
        suggestion:
          '建议协商将提前通知期缩短为2个月、违约金降低为1个月租金，这更符合市场惯例。',
        referenced_law: '借地借家法第27条、第28条',
      },
      {
        clause_number: '第12条（更新料）',
        original_text:
          '本契約の更新に際し、乙は更新料として賃料1ヶ月分を甲に支払うものとする。',
        risk_level: '低',
        risk_reason:
          '1个月租金的更新费在东京地区较为常见，最高裁判所也确认了合理范围内的更新费条款有效。此条款在合理范围内。',
        suggestion: '此条款属于常见做法，但签约前可确认是否每次更新都需支付。',
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
        risk_reason:
          '竞业限制期间2年较长，且范围覆盖全日本同业，限制过于宽泛。日本判例通常认为超过1年的竞业限制、无补偿金的竞业条款容易被认定无效。',
        suggestion:
          '建议协商缩短为6个月至1年，限定地域和业务范围，并要求企业支付竞业限制补偿金。',
        referenced_law: '劳动契约法第16条、東京地裁判例（竞业限制合理性判断基准）',
      },
      {
        clause_number: '第6条（試用期間）',
        original_text:
          '試用期間は入社日から6ヶ月間とし、会社が適格性を欠くと判断した場合、試用期間中又は期間満了時に本採用を拒否することができる。',
        risk_level: '中',
        risk_reason:
          '6个月试用期在日本法律允许范围内（通常3-6个月），但"适格性不足"的判断标准较为模糊，企业有较大裁量权。',
        suggestion:
          '建议要求明确"适格性不足"的具体判断标准，并确认试用期间的解雇是否需要提前30天通知。',
        referenced_law: '劳动基准法第20条、第21条',
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
        risk_reason:
          '加班费仅在月超40小时后才支付，这违反了劳动基准法。法律规定超过法定工时（每天8小时/每周40小时）的部分必须支付25%以上的加班费，没有40小时免费加班的例外。',
        suggestion:
          '此条款违法。应要求修改为"法定労働時間を超えた全ての時間外勤務に対し、25%以上の割増賃金を支払う"。',
        referenced_law: '劳动基准法第32条、第37条',
      },
      {
        clause_number: '第10条（損害賠償）',
        original_text:
          '従業員の故意又は過失により会社に損害を与えた場合、その全額を賠償するものとする。また、制服・備品の紛失については、実費相当額を給与から控除することができる。',
        risk_level: '中',
        risk_reason:
          '要求员工赔偿全部损失在判例中通常被限缩，法院一般只认可损失的一部分。另外，从工资中直接扣除需要劳动者书面同意，否则违反工资全额支付原则。',
        suggestion:
          '建议确认公司是否加入了业务损害保险，并要求明确"工资扣除需经本人书面同意"。',
        referenced_law: '劳动基准法第24条（工资全额支付原则）、民法第715条',
      },
    ],
  },
};
