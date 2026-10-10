import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type Lang = "en" | "ms" | "zh";

const FB_I18N: Record<string, Record<Lang, string>> = {
  "nav.home": { en: "Today", ms: "Hari ini", zh: "今日" },
  "nav.group.workforce": { en: "AI workforce", ms: "Tenaga kerja AI", zh: "AI 团队" },
  "nav.group.cash": { en: "Cash & financing", ms: "Tunai & pembiayaan", zh: "现金与融资" },
  "nav.group.company": { en: "Company", ms: "Syarikat", zh: "公司" },
  "nav.group.money": { en: "Money", ms: "Wang", zh: "资金" },
  "nav.group.work": { en: "Work", ms: "Kerja", zh: "工作" },
  "nav.cashFinance": { en: "Cash & finance", ms: "Tunai & kewangan", zh: "现金与财务" },
  "nav.trustAudit": { en: "Trust & audit", ms: "Amanah & audit", zh: "信任与审计" },
  "tabs.section.inbox": { en: "Review inbox sections", ms: "Bahagian peti semakan", zh: "审核收件箱分区" },
  "tabs.section.money": { en: "Cash and finance sections", ms: "Bahagian tunai dan kewangan", zh: "现金与财务分区" },
  "tabs.section.trust": { en: "Trust and audit sections", ms: "Bahagian amanah dan audit", zh: "信任与审计分区" },
  "tabs.agentProposals": { en: "Agent proposals", ms: "Cadangan ejen", zh: "智能体提案" },
  "tabs.recommendations": { en: "Recommendations & outreach", ms: "Cadangan & jangkauan", zh: "建议与外联" },
  "tabs.forecast": { en: "Cash forecast", ms: "Ramalan tunai", zh: "现金预测" },
  "tabs.analysis": { en: "Financial analysis", ms: "Analisis kewangan", zh: "财务分析" },
  "tabs.intelligence": { en: "Receivables & intelligence", ms: "Penghutang & risikan", zh: "应收与财务情报" },
  "tabs.posture": { en: "Security posture", ms: "Postur keselamatan", zh: "安全态势" },
  "tabs.audit": { en: "Audit & access", ms: "Audit & akses", zh: "审计与权限" },
  "nav.inbox": { en: "Review inbox", ms: "Peti semakan", zh: "审核收件箱" },
  "nav.positions": { en: "Positions", ms: "Jawatan", zh: "岗位" },
  "nav.autonomy": { en: "Agents & autonomy", ms: "Ejen & autonomi", zh: "智能体与自主权" },
  "nav.cashflow": { en: "Cash flow", ms: "Aliran tunai", zh: "现金流" },
  "nav.financing": { en: "Financing & Passport", ms: "Pembiayaan & Pasport", zh: "融资与护照" },
  "nav.company": { en: "Company settings", ms: "Tetapan syarikat", zh: "公司设置" },
  "company.desc": {
    en: "Shape DuitDuit to your company: profile, positions, approval limits, alerts, templates and imports, within safety floors nobody can switch off.",
    ms: "Sesuaikan DuitDuit dengan syarikat anda: profil, jawatan, had kelulusan, amaran, templat dan import, dalam had keselamatan yang tidak boleh dimatikan.",
    zh: "按贵公司需要配置 DuitDuit：公司资料、岗位、审批额度、预警、模板与导入，并受不可关闭的安全底线保护。",
  },
  "nav.team": { en: "Team", ms: "Pasukan", zh: "团队" },
  "nav.trust": { en: "Trust center", ms: "Pusat amanah", zh: "信任中心" },
  "inbox.eyebrow": { en: "AI workforce", ms: "Tenaga kerja AI", zh: "AI 团队" },
  "inbox.title": { en: "Review inbox", ms: "Peti semakan", zh: "审核收件箱" },
  "inbox.desc": {
    en: "Everything the agents prepared for the positions you hold. Nothing is sent or paid until a person approves.",
    ms: "Semua yang disediakan oleh ejen untuk jawatan anda. Tiada apa-apa dihantar atau dibayar sehingga seseorang meluluskannya.",
    zh: "智能体为您所负责岗位准备的全部事项。在有人批准之前，不会发送或支付任何内容。",
  },
  "inbox.all": { en: "All mine", ms: "Semua milik saya", zh: "全部" },
  "inbox.canApprove": { en: "You can approve", ms: "Anda boleh lulus", zh: "您可批准" },
  "inbox.waitingOwner": { en: "Waiting for owner", ms: "Menunggu pemilik", zh: "等待负责人" },
  "inbox.readOnly": { en: "View only", ms: "Lihat sahaja", zh: "仅查看" },
  "inbox.approve": { en: "Approve", ms: "Lulus", zh: "批准" },
  "inbox.approveMaker": { en: "Approve as maker", ms: "Lulus sebagai pembuat", zh: "作为经办人批准" },
  "inbox.approveChecker": { en: "Approve as checker", ms: "Lulus sebagai penyemak", zh: "作为复核人批准" },
  "inbox.reject": { en: "Reject", ms: "Tolak", zh: "拒绝" },
  "inbox.edit": { en: "Edit draft", ms: "Sunting draf", zh: "编辑草稿" },
  "inbox.saveEdit": { en: "Save and approve", ms: "Simpan dan lulus", zh: "保存并批准" },
  "inbox.cancel": { en: "Cancel", ms: "Batal", zh: "取消" },
  "inbox.noEditL3": {
    en: "Editing is off for money movement, so both approvers sign the same content.",
    ms: "Suntingan dimatikan untuk pergerakan wang, supaya kedua-dua pelulus menandatangani kandungan yang sama.",
    zh: "资金类事项不可编辑，确保两位审批人签署的是同一内容。",
  },
  "inbox.empty": { en: "Nothing waiting for you", ms: "Tiada apa-apa menunggu anda", zh: "暂无待办事项" },
  "inbox.emptyDesc": {
    en: "When an agent prepares work for one of your positions, it appears here.",
    ms: "Apabila ejen menyediakan kerja untuk jawatan anda, ia akan dipaparkan di sini.",
    zh: "当智能体为您的岗位准备好工作时，会显示在这里。",
  },
  "inbox.select": { en: "Choose an item to review it.", ms: "Pilih item untuk disemak.", zh: "请选择一项进行审核。" },
  "inbox.compliance": {
    en: "Compliance sees every item across all positions, read-only, and decides only its own access reviews.",
    ms: "Pematuhan melihat setiap item merentas semua jawatan (lihat sahaja) dan hanya memutuskan semakan akses sendiri.",
    zh: "合规岗可查看所有岗位的全部事项（只读），只对自己的权限审查作出决定。",
  },
  "inbox.evidence": { en: "Evidence", ms: "Bukti", zh: "依据" },
  "inbox.draft": { en: "Draft", ms: "Draf", zh: "草稿" },
  "inbox.stub": {
    en: "Demo data: decisions are shown but not saved yet.",
    ms: "Data demo: keputusan dipaparkan tetapi belum disimpan.",
    zh: "演示数据：决定会显示，但尚未保存。",
  },
  "cash.desc": {
    en: "A 90-day forecast built from every position's signals, with the best–worst range and your minimum balance.",
    ms: "Ramalan 90 hari daripada isyarat setiap jawatan, dengan julat terbaik–terburuk dan baki minimum anda.",
    zh: "根据各岗位信号生成的 90 天现金流预测，含最好与最差区间及您的最低余额。",
  },
  "cash.stub": {
    en: "Demo data: a synthetic trading company, not your books.",
    ms: "Data demo: syarikat perdagangan sintetik, bukan akaun anda.",
    zh: "演示数据：虚构的贸易公司，并非您的账目。",
  },
  "fin.desc": {
    en: "Financing that fits the gap, each match explained rule by rule, and a verifiable Passport you can share with a lender or auditor.",
    ms: "Pembiayaan yang sesuai dengan jurang, setiap padanan diterangkan mengikut peraturan, dan Pasport boleh disahkan untuk dikongsi dengan pemberi pinjaman atau juruaudit.",
    zh: "匹配资金缺口的融资方案，逐条说明匹配规则，并提供可验证的融资护照，可分享给贷款方或审计师。",
  },
  "pos.desc": {
    en: "One workspace per job: what its agents found, what it adds to the cash forecast, and what is waiting for review.",
    ms: "Satu ruang kerja bagi setiap jawatan: dapatan ejen, sumbangannya kepada ramalan tunai, dan perkara yang menunggu semakan.",
    zh: "每个岗位一个工作台：智能体的发现、对现金流预测的影响，以及待审核事项。",
  },
  "auto.desc": {
    en: "Every agent, how much it may do on its own, and the switch that stops them all.",
    ms: "Setiap ejen, sejauh mana ia boleh bertindak sendiri, dan suis untuk menghentikan semuanya.",
    zh: "所有智能体、各自可自主执行的范围，以及一键停止全部智能体的开关。",
  },
  "team.desc": {
    en: "Who has access, which positions they cover, and whether their sign-in is protected.",
    ms: "Siapa yang mempunyai akses, jawatan yang mereka liputi, dan sama ada log masuk mereka dilindungi.",
    zh: "谁拥有访问权限、负责哪些岗位，以及其登录是否受到保护。",
  },
  "trust.desc": {
    en: "Your security posture and every attack the agent guardrails stopped.",
    ms: "Postur keselamatan anda dan setiap serangan yang dihalang oleh kawalan ejen.",
    zh: "您的安全态势，以及智能体防护拦截的每一次攻击。",
  },
  "home.title": { en: "Briefing", ms: "Taklimat", zh: "简报" },
  "home.desc": {
    en: "Everything across your workspace, at a glance. Each card reflects live data — nothing shown here is invented.",
    ms: "Semua yang berlaku dalam ruang kerja anda, secara ringkas. Setiap kad memaparkan data sebenar — tiada apa-apa di sini direka-reka.",
    zh: "工作区的所有情况，一目了然。每张卡片都反映实时数据——这里显示的内容绝无捏造。",
  },
  "home.greeting.morning": { en: "Good morning", ms: "Selamat pagi", zh: "早上好" },
  "home.greeting.afternoon": { en: "Good afternoon", ms: "Selamat tengah hari", zh: "下午好" },
  "home.greeting.evening": { en: "Good evening", ms: "Selamat petang", zh: "晚上好" },
  "nav.aiAgents": { en: "Ask DuitDuit", ms: "Tanya DuitDuit", zh: "询问 DuitDuit" },
  "nav.customers": { en: "Customers", ms: "Pelanggan", zh: "客户" },
  "nav.einvoicing": { en: "e-Invoicing", ms: "e-Invois", zh: "电子发票" },
  "nav.financeDashboard": { en: "Financial Intelligence", ms: "Risikan Kewangan", zh: "财务情报" },
  "nav.audit": { en: "Audit & Access", ms: "Audit & Akses", zh: "审计与权限" },
  "nav.approvals": { en: "Workflows", ms: "Aliran Kerja", zh: "工作流程" },
  "nav.settings": { en: "My preferences", ms: "Pilihan saya", zh: "个人偏好" },
  "nav.logout": { en: "Log out", ms: "Log keluar", zh: "退出登录" },
  "settings.title": { en: "My preferences", ms: "Pilihan saya", zh: "个人偏好" },
  "settings.desc": {
    en: "Your personal preferences for this workspace — stored on this device.",
    ms: "Keutamaan peribadi anda untuk ruang kerja ini — disimpan pada peranti ini.",
    zh: "此工作区的个人偏好设置——保存在本设备上。",
  },
  "einvoice.title": { en: "e-Invoicing", ms: "e-Invois", zh: "电子发票" },
  "einvoice.desc": {
    en: "Receipts and invoices mapped to MyInvois and checked for missing fields before submission, with personal data masked.",
    ms: "Resit dan invois dipetakan ke MyInvois dan disemak untuk medan yang tiada sebelum dihantar, dengan data peribadi disembunyikan.",
    zh: "收据与发票对接 MyInvois，提交前检查缺失字段，个人数据已遮蔽。",
  },
  "einvoice.filterAll": { en: "All invoices", ms: "Semua invois", zh: "全部发票" },
  "einvoice.filterMine": { en: "My submissions", ms: "Penyerahan saya", zh: "我的提交" },
  "finance.title": { en: "Cash & finance", ms: "Tunai & kewangan", zh: "现金与财务" },
  "finance.desc": {
    en: "Company earnings, at a glance — last 12 months.",
    ms: "Pendapatan syarikat secara ringkas — 12 bulan terakhir.",
    zh: "公司业绩概览——近 12 个月。",
  },
  "export.csv": { en: "Export as CSV", ms: "Eksport sebagai CSV", zh: "导出为 CSV" },
  "audit.title": { en: "Trust & audit", ms: "Amanah & audit", zh: "信任与审计" },
  "audit.desc": {
    en: "Every access and action, tamper-evident and traceable.",
    ms: "Setiap akses dan tindakan, tahan gangguan dan boleh dijejaki.",
    zh: "每一次访问与操作，均可追溯且防篡改。",
  },
  "approvals.title": { en: "Review inbox", ms: "Peti semakan", zh: "审核收件箱" },
  "approvals.desc": {
    en: "Everything an AI agent has prepared on your behalf — nothing is submitted, sent, or adopted until you act here.",
    ms: "Semua yang disediakan oleh ejen AI bagi pihak anda — tidak ada yang dihantar atau digunakan sehingga anda meluluskannya di sini.",
    zh: "所有由 AI 代理代您准备的事项——在您在此处操作之前，绝不会提交、发送或采用。",
  },
  "agents.title": { en: "Ask DuitDuit", ms: "Tanya DuitDuit", zh: "询问 DuitDuit" },
  "agents.desc": {
    en: "Evidence-backed answers across protected company records, with permission-aware actions.",
    ms: "Jawapan berasaskan bukti merentas rekod syarikat terlindung, dengan tindakan mengikut kebenaran.",
    zh: "跨受保护企业记录的循证答案，并提供权限感知操作。",
  },
  "agents.viewingAs": { en: "Viewing as", ms: "Melihat sebagai", zh: "查看身份：" },
  "nav.ingestion": { en: "Data sources", ms: "Sumber data", zh: "数据来源" },
  "ingestion.title": { en: "Data sources", ms: "Sumber data", zh: "数据来源" },
  "ingestion.desc": {
    en: "Messages forwarded from Telegram or email are captured here automatically — personal details are masked before any AI model ever sees them.",
    ms: "Mesej yang dihantar dari Telegram atau e-mel akan diambil di sini secara automatik — butiran peribadi disamarkan sebelum sebarang model AI melihatnya.",
    zh: "从 Telegram 或电子邮件转发的消息会在此自动捕获——个人信息会在任何 AI 模型读取之前先被遮蔽。",
  },
};

export const FB_UI_STRINGS: Record<Lang, { placeholder: string; send: string; switched: string }> = {
  en: { placeholder: "Ask DuitDuit anything, or tell it what to do...", send: "Send", switched: "Switched to English." },
  ms: { placeholder: "Tanya DuitDuit apa-apa, atau beritahu ia apa yang perlu dilakukan...", send: "Hantar", switched: "Ditukar kepada Bahasa Malaysia." },
  zh: { placeholder: "向 DuitDuit 提问，或告诉它该做什么...", send: "发送", switched: "已切换为中文。" },
};

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);
const LANG_STORAGE_KEY = "fb-lang";

function readStoredLang(): Lang {
  try {
    const raw = window.localStorage.getItem(LANG_STORAGE_KEY);
    if (raw === "en" || raw === "ms" || raw === "zh") return raw;
  } catch {
    // Private browsing / storage disabled: fall through to the default.
  }
  return "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => readStoredLang());
  const setLang = (next: Lang) => {
    setLangState(next);
    try {
      window.localStorage.setItem(LANG_STORAGE_KEY, next);
    } catch {
      // Private browsing / storage disabled: choice just won't persist.
    }
  };
  const value = useMemo<I18nContextValue>(
    () => ({
      lang,
      setLang,
      t: (key: string) => FB_I18N[key]?.[lang] ?? FB_I18N[key]?.en ?? key,
    }),
    [lang],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
