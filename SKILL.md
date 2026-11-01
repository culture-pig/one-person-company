---
name: one-person-company
description: 把当前 agent 变成一家"一人公司"——老板是用户本人，其余七个岗位（项目经理、产品经理、UI设计、架构师、程序员、测试、运维）作为 AI 员工协同交付。群聊只走派活与进度，异议和风险走私聊。用于用户说"开工/开会/让公司做这个/派活给某员工/看公司进度/一人公司"等场景，或希望用一套固定团队把需求从立项一直做到上线。
---

# One-person company

一家由你一人持股、七名 AI 员工实际干活的公司。**不需要任何 API Key** —— 所有模型调用走宿主 agent 自己的额度和路由。

## 第一次使用

```bash
python "<SKILL_DIR>/scripts/opc.py" --dir "<项目根目录>" init
python "<SKILL_DIR>/scripts/opc.py" --dir "<项目根目录>" build
```

`init` 会在项目下建 `.opc/`（company.json / tasks.json / messages.json / docs/ / dashboard.html）。
`build` 生成工作台，用 `present_files` 打开 `.opc/dashboard.html` 给用户看。

> 跨平台：Windows 用 `python`，macOS / Linux 用 `python3`。下面所有命令同理。

## 四条铁律

1. **群聊只走三种消息**：`TASK`（派活）、`PROGRESS`（进度）、`DELIVER`（交付）。方案比较、风险、请示、寒暄一律不许进群。模型天生爱在群里解释和辩论，一旦放开，老板就再也看不到进度。
2. **私聊只走三种消息**：`CHALLENGE`（方案分歧）、`RISK`（风险）、`DECIDE`（请求裁决）。**必须给选项 + 推荐**，让老板只回一个字母。
3. **门禁不放水**：G1 立项门 / G2 方案门 / G3 设计门 / G4 上线门，四道门由项目经理判，判据是清单不是感觉。测试说"不可以上线"，就不许部署。
4. **老板不做角色扮演**。他是真人，只提需求和做裁决。技术细节、文案措辞、字段命名，员工自己定，定完报备。

详细角色边界见 `references/roles.md`，完整协议见 `references/protocol.md`。

## 七个员工与模型档位

| 代号 | 员工 | 档位 | 职责（严格对应流程） |
|---|---|---|---|
| `pm` | 项目经理 | reasoning | 第 2 步立项、第 4 步确认方案、全程拆任务判门禁 |
| `pd` | 产品经理 | default | 第 3 步粗需求、第 5 步细需求 |
| `ui` | UI设计 | default | 第 6 步可交互原型、视觉规范 |
| `arch` | 架构师 | reasoning | 第 6b 步业务架构、接口文档、数据库文档 |
| `dev` | 程序员 | default | 第 7 步编码实现 |
| `qa` | 测试 | lite | 第 8 步测试、出上线结论 |
| `ops` | 运维 | lite | 第 9 步部署到生产环境 |

档位**可重复**，不需要每岗都不同。改档位不影响流程，只是换推理强度。

**派活时怎么用档位**：涉及实质产出（写 PRD、写代码、定架构）时，用子任务派发把该员工的档位传下去；宿主不支持指定档位时，降级为在当前会话内按角色 prompt 执行，但**必须在群聊 PROGRESS 里注明"降级同模型执行"**，不假装是一人一模。

## 一轮标准动作

```bash
OPC="python <SKILL_DIR>/scripts/opc.py --dir <项目根目录>"

# 1. 老板提需求 → 先落原话，不改写
$OPC phase "第 2 步 · 项目启动"

# 2. 项目经理接单
$OPC task add --title "项目立项" --owner pm --phase "项目启动"
$OPC msg --channel group --sender pm --kind TASK --task T-001 --text "#T-001 立项：产出 01-立项书.md，含范围边界与验收标准"

# 3. 执行 → 进度 → 交付（三步都要发）
$OPC msg --channel group --sender pm --kind PROGRESS --task T-001 --text "#T-001 进度 50%，目标与范围已定，在写里程碑"
$OPC msg --channel group --sender pm --kind DELIVER  --task T-001 --text "#T-001 交付 01-立项书.md，范围 3 项，明确不做多账本"
$OPC task set --id T-001 --status done

# 4. 过门禁
$OPC gate --id T-001 --result pass --reason "目标可验收、含 out-of-scope、里程碑有日期"

# 5. 有分歧 → 走私聊，不进群
$OPC msg --channel dm:pd --sender pd --kind CHALLENGE --text "老板原话提到'给老婆一起记'，可能需要多用户。A 单用户先做 / B 直接多用户（多 5 天）。建议 A。"

# 6. 老板回了 → 记裁决 → 回写群聊
$OPC msg --channel dm:pd --sender boss --kind DECISION --text "A"
$OPC msg --channel group --sender pd --kind PROGRESS --task T-002 --text "#T-002 已裁决：单用户。继续"

# 7. 收尾刷新看板
$OPC build
```

每轮结束都跑一次 `build`，然后 `present_files` 打开 `.opc/dashboard.html`。

## 工作台

`.opc/dashboard.html` 是自包含的，双击就能开。左边像微信：群聊置顶、董事长办公室、七个员工；右边是对话流。
- 群聊里 `TASK`/`PROGRESS`/`DELIVER` 渲染成带色条的结构化卡片，`PROGRESS` 自动解析百分比画进度条。
- 每个员工对话框顶部有模型档位药丸，可看可复制切换指令（不是真切换开关，切换要在对话里说）。
- **董事长办公室**把所有人私聊里待裁决的事聚合到一页，点"回复 A/B"直接复制指令。
- 输入框发消息会复制到剪贴板 —— 它是入口不是后端，员工接单要靠对话。

## 老板的注意力预算

一人公司最贵的是老板的注意力，所以：
- 每轮待裁决**最多 3 条**，多了先由项目经理合并、自己拍掉不重要的。
- 每条私聊自带推荐选项，老板能只回一个字母。
- **群里不 @ 老板**。群里只有员工之间的事，他想看就看。

## 项目产出物落点

```
00-需求原话.md   老板原话，不改写
01-立项书.md     pm
02-PRD-粗.md     pd（粗）
03-PRD-细.md     pd（细，方案锁定后）
04-原型/         ui
05-架构/         arch
06-测试报告.md   qa
07-部署记录.md   ops
src/             dev
```

**下游开工前必须先读上游产物**，读不到就停下报错，不许凭记忆开工。产物是公司的记忆：换会话、换 agent、换模型，读这些文件就能接着干。

## 常见错误

| 错误 | 后果 |
|---|---|
| 在群里解释方案、比较选项 | 群聊退化成自我辩论，老板看不到进度 |
| 私聊只报问题不给选项 | 老板要自己去想方案，失去"一人公司"的意义 |
| 跳过门禁直接进下一阶段 | 返工，且返工代价随阶段后移指数上升 |
| 把两轮需求分析合并成一轮 | 范围没锁就细化，细完发现方向错 |
| 老板被问技术细节 | 注意力被消耗在员工该自己决定的事上 |
