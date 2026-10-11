# Chinese interface strings: list for review

Generated from `frontend/src/lib/i18n.tsx` on 2026-10-11. There are 88 strings.
- All are machine-assisted drafts.
- None has been checked by a fluent reader of Simplified Chinese yet.
- Tick a row once it is correct, or write the correction beside it.

## What the Chinese mode covers today (measured)

The 中文 setting translates navigation, page titles, section tabs and some descriptions. Most content is still English:
- table labels;
- rule explanations;
- the assistant's replies;
- every sentence the backend writes.

We switched the app to 中文 on a local copy of the demo company and counted visible text:

| Screen | Chinese characters | English words |
|---|---|---|
| Today | 67 | 189 |
| Cash forecast | 112 | 337 |
| Financial analysis | 81 | 276 |
| Financing & Passport | 107 | 878 |
| Review inbox | 141 | 87 |
| Ask DuitDuit | 83 | 129 |

**Recommendation:** do not show the 中文 switch in the video. A half-translated screen reads as unfinished.
- Carry Chinese through the reviewed subtitles (`docs/submission/subtitles-zh-draft.md`) instead.
- Translating the backend's sentences and the remaining screen text is post-competition work.

## Strings

| Key | English | 中文 | OK |
|---|---|---|---|
| `nav.home` | Today | 今日 | ☐ |
| `nav.group.workforce` | AI workforce | AI 团队 | ☐ |
| `nav.group.cash` | Cash & financing | 现金与融资 | ☐ |
| `nav.group.company` | Company | 公司 | ☐ |
| `nav.group.money` | Money | 资金 | ☐ |
| `nav.group.work` | Work | 工作 | ☐ |
| `nav.cashFinance` | Cash & finance | 现金与财务 | ☐ |
| `nav.trustAudit` | Trust & audit | 信任与审计 | ☐ |
| `tabs.section.inbox` | Review inbox sections | 审核收件箱分区 | ☐ |
| `tabs.section.money` | Cash and finance sections | 现金与财务分区 | ☐ |
| `tabs.section.trust` | Trust and audit sections | 信任与审计分区 | ☐ |
| `tabs.agentProposals` | Agent proposals | 智能体提案 | ☐ |
| `tabs.recommendations` | Recommendations & outreach | 建议与外联 | ☐ |
| `tabs.forecast` | Cash forecast | 现金预测 | ☐ |
| `tabs.analysis` | Financial analysis | 财务分析 | ☐ |
| `tabs.intelligence` | Receivables & intelligence | 应收与财务情报 | ☐ |
| `tabs.posture` | Security posture | 安全态势 | ☐ |
| `tabs.audit` | Audit & access | 审计与权限 | ☐ |
| `nav.inbox` | Review inbox | 审核收件箱 | ☐ |
| `nav.positions` | Positions | 岗位 | ☐ |
| `nav.autonomy` | Agents & autonomy | 智能体与自主权 | ☐ |
| `nav.cashflow` | Cash flow | 现金流 | ☐ |
| `nav.financing` | Financing & Passport | 融资与护照 | ☐ |
| `nav.company` | Company settings | 公司设置 | ☐ |
| `company.desc` | Shape DuitDuit to your company: profile, positions, approval limits, alerts, templates and imports, within safety floors nobody can switch off. | 按贵公司需要配置 DuitDuit：公司资料、岗位、审批额度、预警、模板与导入，并受不可关闭的安全底线保护。 | ☐ |
| `nav.team` | Team | 团队 | ☐ |
| `nav.trust` | Trust center | 信任中心 | ☐ |
| `inbox.eyebrow` | AI workforce | AI 团队 | ☐ |
| `inbox.title` | Review inbox | 审核收件箱 | ☐ |
| `inbox.desc` | Everything the agents prepared for the positions you hold. Nothing is sent or paid until a person approves. | 智能体为您所负责岗位准备的全部事项。在有人批准之前，不会发送或支付任何内容。 | ☐ |
| `inbox.all` | All mine | 全部 | ☐ |
| `inbox.canApprove` | You can approve | 您可批准 | ☐ |
| `inbox.waitingOwner` | Waiting for owner | 等待负责人 | ☐ |
| `inbox.readOnly` | View only | 仅查看 | ☐ |
| `inbox.approve` | Approve | 批准 | ☐ |
| `inbox.approveMaker` | Approve as maker | 作为经办人批准 | ☐ |
| `inbox.approveChecker` | Approve as checker | 作为复核人批准 | ☐ |
| `inbox.reject` | Reject | 拒绝 | ☐ |
| `inbox.edit` | Edit draft | 编辑草稿 | ☐ |
| `inbox.saveEdit` | Save and approve | 保存并批准 | ☐ |
| `inbox.cancel` | Cancel | 取消 | ☐ |
| `inbox.noEditL3` | Editing is off for money movement, so both approvers sign the same content. | 资金类事项不可编辑，确保两位审批人签署的是同一内容。 | ☐ |
| `inbox.empty` | Nothing waiting for you | 暂无待办事项 | ☐ |
| `inbox.emptyDesc` | When an agent prepares work for one of your positions, it appears here. | 当智能体为您的岗位准备好工作时，会显示在这里。 | ☐ |
| `inbox.select` | Choose an item to review it. | 请选择一项进行审核。 | ☐ |
| `inbox.compliance` | Compliance sees every item across all positions, read-only, and decides only its own access reviews. | 合规岗可查看所有岗位的全部事项（只读），只对自己的权限审查作出决定。 | ☐ |
| `inbox.evidence` | Evidence | 依据 | ☐ |
| `inbox.draft` | Draft | 草稿 | ☐ |
| `inbox.stub` | Demo data: decisions are shown but not saved yet. | 演示数据：决定会显示，但尚未保存。 | ☐ |
| `cash.desc` | A 90-day forecast built from every position's signals, with the best–worst range and your minimum balance. | 根据各岗位信号生成的 90 天现金流预测，含最好与最差区间及您的最低余额。 | ☐ |
| `cash.stub` | Demo data: a synthetic trading company, not your books. | 演示数据：虚构的贸易公司，并非您的账目。 | ☐ |
| `fin.desc` | Financing that fits the gap, each match explained rule by rule, and a verifiable Passport you can share with a lender or auditor. | 匹配资金缺口的融资方案，逐条说明匹配规则，并提供可验证的融资护照，可分享给贷款方或审计师。 | ☐ |
| `pos.desc` | One workspace per job: what its agents found, what it adds to the cash forecast, and what is waiting for review. | 每个岗位一个工作台：智能体的发现、对现金流预测的影响，以及待审核事项。 | ☐ |
| `auto.desc` | Every agent, how much it may do on its own, and the switch that stops them all. | 所有智能体、各自可自主执行的范围，以及一键停止全部智能体的开关。 | ☐ |
| `team.desc` | Who has access, which positions they cover, and whether their sign-in is protected. | 谁拥有访问权限、负责哪些岗位，以及其登录是否受到保护。 | ☐ |
| `trust.desc` | Your security posture and every attack the agent guardrails stopped. | 您的安全态势，以及智能体防护拦截的每一次攻击。 | ☐ |
| `home.title` | Briefing | 简报 | ☐ |
| `home.desc` | Everything across your workspace, at a glance. Each card reflects live data — nothing shown here is invented. | 工作区的所有情况，一目了然。每张卡片都反映实时数据——这里显示的内容绝无捏造。 | ☐ |
| `home.greeting.morning` | Good morning | 早上好 | ☐ |
| `home.greeting.afternoon` | Good afternoon | 下午好 | ☐ |
| `home.greeting.evening` | Good evening | 晚上好 | ☐ |
| `nav.aiAgents` | Ask DuitDuit | 询问 DuitDuit | ☐ |
| `nav.customers` | Customers | 客户 | ☐ |
| `nav.einvoicing` | e-Invoicing | 电子发票 | ☐ |
| `nav.financeDashboard` | Financial Intelligence | 财务情报 | ☐ |
| `nav.audit` | Audit & Access | 审计与权限 | ☐ |
| `nav.approvals` | Workflows | 工作流程 | ☐ |
| `nav.settings` | My preferences | 个人偏好 | ☐ |
| `nav.logout` | Log out | 退出登录 | ☐ |
| `settings.title` | My preferences | 个人偏好 | ☐ |
| `settings.desc` | Your personal preferences for this workspace — stored on this device. | 此工作区的个人偏好设置——保存在本设备上。 | ☐ |
| `einvoice.title` | e-Invoicing | 电子发票 | ☐ |
| `einvoice.desc` | Receipts and invoices mapped to MyInvois and checked for missing fields before submission, with personal data masked. | 收据与发票对接 MyInvois，提交前检查缺失字段，个人数据已遮蔽。 | ☐ |
| `einvoice.filterAll` | All invoices | 全部发票 | ☐ |
| `einvoice.filterMine` | My submissions | 我的提交 | ☐ |
| `finance.title` | Cash & finance | 现金与财务 | ☐ |
| `finance.desc` | Company earnings, at a glance — last 12 months. | 公司业绩概览——近 12 个月。 | ☐ |
| `export.csv` | Export as CSV | 导出为 CSV | ☐ |
| `audit.title` | Trust & audit | 信任与审计 | ☐ |
| `audit.desc` | Every access and action, tamper-evident and traceable. | 每一次访问与操作，均可追溯且防篡改。 | ☐ |
| `approvals.title` | Review inbox | 审核收件箱 | ☐ |
| `approvals.desc` | Everything an AI agent has prepared on your behalf — nothing is submitted, sent, or adopted until you act here. | 所有由 AI 代理代您准备的事项——在您在此处操作之前，绝不会提交、发送或采用。 | ☐ |
| `agents.title` | Ask DuitDuit | 询问 DuitDuit | ☐ |
| `agents.desc` | Evidence-backed answers across protected company records, with permission-aware actions. | 跨受保护企业记录的循证答案，并提供权限感知操作。 | ☐ |
| `agents.viewingAs` | Viewing as | 查看身份： | ☐ |
| `nav.ingestion` | Data sources | 数据来源 | ☐ |
| `ingestion.title` | Data sources | 数据来源 | ☐ |
| `ingestion.desc` | Messages forwarded from Telegram or email are captured here automatically — personal details are masked before any AI model ever sees them. | 从 Telegram 或电子邮件转发的消息会在此自动捕获——个人信息会在任何 AI 模型读取之前先被遮蔽。 | ☐ |
