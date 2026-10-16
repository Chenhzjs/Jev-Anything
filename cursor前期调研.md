# Jev Anything 前期调研与项目构想

> 文档用途：为后续切换到 Codex 后继续开发保留完整上下文。
>
> 调研时间：2026-10-04（前期调研）
> 整理时间：2026-10-11
> 当前项目目录：`<repository-root>`
>
> 相关项目：
>
> - [GUI2TUI](https://github.com/Chenhzjs/GUI2TUI)
> - [CLI-Anything](https://github.com/HKUDS/CLI-Anything)
>
---

## 1. 一句话结论

这个想法值得做，而且具有较强的传播潜力。

最有价值的产品定义不是“把 GUI 全部自动转换为 CLI”，而是：

> **把 GUI 暴露出来的可验证语义状态，投影成 Agent 可消费的候选动作和上下文，再由 Jev 做低延迟结构化决策，最后由确定性执行器完成安全校验、执行和权威回读。**

推荐的项目方向是：

> **Jev Anything：让原本只能通过 GUI 操作的软件，变成 Agent 可以发现、理解、决策、调用并验证的软件接口。**

---

## 2. 调研范围和已核实事实

### 2.1 GUI2TUI

GUI2TUI 当前已经不是简单的“截图转终端”项目，而是一个基于 Linux AT-SPI Accessibility 语义的 Rust 系统。

其核心链路是：

```text
GUI application
      ↓
public AT-SPI Accessibility semantics
      ↓
GUI2TUI semantic runtime
      ↓
terminal-native views and operations
      ↓
authoritative GUI state/readback
```

已核实的主要特点：

- 使用公开 Accessibility 语义，而不是截图、OCR 或像素坐标。
- 原始 GUI 仍然是权威状态源，TUI 是语义投影。
- 支持应用发现、场景导航、按钮、开关、值、单选、表格行、标签页、菜单、模态对话框、文件选择等语义。
- 操作之后要求通过权威 readback 验证结果。
- 会拒绝 stale target、失效应用、无效 scope 和不完整语义。
- 不把成功调用 backend 方法本身当作操作成功证明。
- 对密码字段、外部文本和敏感内容有边界控制。
- 支持 Headless-first 运行路径，包括 Managed Xvfb、容器、SSH 和部分 Wayland/XWayland 场景。
- 技术栈是 Rust 2024、Rust 1.88+、AT-SPI、Tokio、Ratatui、Crossterm、Serde、Clap 等。

GUI2TUI 的边界也非常明确：

- 不是远程桌面。
- 不是 framebuffer 转 ASCII。
- 不是 OCR 系统。
- 不是坐标点击工具。
- 不是键盘鼠标注入层。
- 不是应用专用脚本框架。
- 不制造应用没有公开暴露的能力。

这一点非常重要，因为它为 Jev 集成提供了一个可信的语义和执行底座。

### 2.2 CLI-Anything

CLI-Anything 的成功点不只是“给软件加一个 CLI”，而是一套完整的 Agent-native 生态方法：

- 统一命令结构。
- 结构化 JSON 输出。
- 同时保留人类可读输出。
- 真实软件作为后端，不用玩具替代品伪造能力。
- 统一的 Harness 生成和文档规范。
- `SKILL.md` 作为 Agent 可发现入口。
- CLI-Hub 作为发现、安装、升级和卸载平台。
- 真实应用 E2E 测试。
- 单元测试、命令行子进程测试和端到端验证。
- 支持 Cursor、Claude Code、Codex、OpenClaw、Pi、OpenCode 等多个 Agent 平台。
- 通过社区贡献和注册表形成生态网络效应。

CLI-Anything 的公开仓库在 2026-10-04 调研时约有 5 万级 Star，说明“让软件变成 Agent 可用工具”的叙事已经有强烈市场关注度。

CLI-Anything 更偏向：

```text
软件源码 / 后端能力
      ↓
Agent-native CLI harness
      ↓
JSON / Skill / Hub / Agent
```

Jev Anything 可以形成不同但互补的方向：

```text
公开 GUI 语义
      ↓
SemanticSnapshot / ActionCandidates
      ↓
Jev 决策
      ↓
安全执行 / 权威回读
```

### 2.3 Jev 生态

当前公开生态普遍把 Jev 视为适合以下任务的结构化决策模型：

- Choice：在有限候选中选择。
- Score：对候选或状态评分。
- Noul：进行布尔判断。
- 意图分类。
- 路由。
- 置信度门控。
- 工具选择。
- 上下文压缩。
- Agent fast-path。
- 低延迟安全判断。

适合 Jev 的任务特点：

- 候选集合有限。
- 输出空间可以严格约束。
- 结果需要直接被代码消费。
- 不需要长篇文本生成。
- 需要频繁、便宜、低延迟地做微决策。

不应该让 Jev 单独承担的职责：

- 最终授权。
- 新参数生成。
- 新坐标生成。
- 新命令生成。
- 高副作用动作的最终批准。
- 密码、密钥和敏感字段处理。
- 对未观测状态进行猜测。

Jev 的具体 API、模型版本、字段名、延迟和价格仍然必须以 TypeSafe 当前官方文档和实际账号接口为最终准入依据，不应只依据社区项目或搜索摘要实现。

### 2.4 当前工作区

前期调研时 `<repository-root>` 为空目录，没有现有实现和 git 历史，适合从协议、核心运行时和第一个 Tracer Bullet 直接起步。

---

## 3. 产品价值评估

### 3.1 价值来源

#### 把 GUI 状态变成可压缩状态

Agent 不需要接收截图、整棵 Accessibility 树或无关窗口，只需要接收完成当前判断所需的最小语义证据：

- 当前场景。
- 可见且可用的控件。
- 控件的能力。
- 控件之间的关系。
- 当前值的安全摘要。
- 可执行动作。
- 预期结果。
- 当前 generation 和 freshness 信息。

这能够降低：

- context 长度。
- 网络成本。
- 推理延迟。
- 敏感信息泄漏面。
- 模型解析复杂度。

#### 让 Jev 只负责“选”

Jev 最适合在封闭候选集合中做选择，而不是从自然语言中创造完整执行计划。

例如，GUI2TUI 可以先生成：

```text
candidate_1: 点击“下一页”
candidate_2: 打开“设置”
candidate_3: 关闭当前窗口
candidate_4: abstain
```

Jev 只能返回：

```text
candidate_1
```

或者：

```text
abstain
```

Jev 不得返回：

- 坐标。
- 任意快捷键。
- 新路径。
- 新文本输入。
- 新工具名。
- 不在候选集合中的目标。

#### 复用 GUI2TUI 已有的安全正确性

GUI2TUI 已经拥有：

- 语义目标身份。
- stale target 检查。
- action dispatch。
- focus 和 source 检查。
- authoritative readback。
- unsupported refusal。
- 运行时恢复。
- headless 环境支持。

Jev Anything 不应重新实现这些能力，而应作为上层决策适配器使用它们。

#### 形成清晰的传播故事

项目可以用一句容易理解的表达传播：

> **任何公开暴露 Accessibility 语义的 GUI，都可以变成 Agent 可发现、可决策、可验证的工具。**

这同时连接了三个热门方向：

- GUI Agent。
- Agent-native software。
- Jev 结构化决策。

### 3.2 定性评分

| 维度 | 评分 | 判断 |
|---|---:|---|
| 需求真实度 | 5/5 | Agent 需要更便宜、更可靠、更结构化的软件接口 |
| 技术互补性 | 5/5 | GUI2TUI 与 Jev 的职责天然互补 |
| 首个 Demo 可行性 | 4/5 | 单个 GTK fixture 可以较快闭环 |
| 生态传播性 | 5/5 | GUI、CLI、MCP、Skill、Jev 的组合易于展示 |
| 短期商业化 | 2/5 | 需要先验证真实需求和稳定覆盖范围 |
| 长期平台价值 | 4/5 | 有机会成为 GUI 语义到 Agent 接口的协议层 |

综合机会分：25/30。

这个分数代表项目机会判断，不是用户量、收入或成功概率预测。

---

## 4. 推荐的产品定位

### 4.1 不要定位成

- 万能 GUI 自动化。
- 任何 GUI 都能无条件控制。
- 用 Jev 代替所有 LLM。
- 用 TUI 替代真实 GUI。
- 用模型自由生成控制指令。
- 只做一个 Jev API wrapper。

### 4.2 推荐定位

> Jev Anything 是一个面向 Agent 的 GUI 语义桥接层：它从 GUI2TUI 获取可验证的语义状态和候选动作，用 Jev 做低延迟结构化决策，再调用已有执行器完成受约束操作和权威回读。

### 4.3 推荐的三层产品形态

#### 第一层：核心协议与运行时

建议项目名或内部模块名：

```text
jev-anything-core
```

负责：

- Snapshot。
- Candidate。
- Decision。
- Outcome。
- Provider abstraction。
- 候选 membership 校验。
- freshness 校验。
- 风险门控。
- fallback。
- trace 和 replay。

#### 第二层：CLI 和 MCP

CLI 负责调试、shell 编排、脚本集成和人类检查。

MCP 负责接入 Cursor、Codex、Claude Code、OpenClaw 和其他 Agent。

建议命令形态：

```bash
jev-anything observe
jev-anything candidates
jev-anything decide
jev-anything act --candidate candidate_12
jev-anything run --goal "打开设置并切换深色模式"
```

建议所有命令支持：

```bash
--json
--dry-run
--trace-id
--timeout
--no-network
```

#### 第三层：Skill 和插件生态

建议结构：

```text
skills/
  gui2tui/
  jev-fast-path/
  libreoffice/
  mousepad/
  qt-designer/
  browser/
```

每个应用或任务 Skill 应包含：

- 能力说明。
- 前置环境。
- 支持的语义范围。
- 不支持的操作。
- 风险等级。
- 命令示例。
- JSON 输出示例。
- E2E fixture。
- readback 说明。

后续再考虑 registry、Hub 和社区贡献体系。

---

## 5. 推荐总体架构

```text
GUI / Application
    ↓
GUI2TUI / AT-SPI semantic runtime
    ↓
SemanticSnapshot
    ↓
Local policy filters
    ↓
Bounded ActionCandidates
    ↓
Jev Choice / Score / Noul
    ↓
Candidate membership + freshness + risk validation
    ↓
Deterministic dispatcher
    ↓
Authoritative GUI readback
    ↓
Outcome / handback / trace
```

### 5.1 SemanticSnapshot

描述当前 GUI 的最小可用语义状态。

建议字段：

```json
{
  "source_id": "app-window-01",
  "generation": 42,
  "scene_id": "settings.general",
  "observed_at": "2026-10-11T15:00:00Z",
  "controls": [],
  "relations": [],
  "capabilities": [],
  "redactions": []
}
```

关键原则：

- 绑定 source identity。
- 绑定 generation。
- 保留 freshness。
- 默认最小化。
- 默认脱敏。
- 不把完整文档、密码、剪贴板和无关窗口发送出去。

### 5.2 ActionCandidate

描述已经经过本地语义和策略过滤的候选动作。

建议字段：

```json
{
  "candidate_id": "candidate_12",
  "kind": "invoke_button",
  "target_ref": "control.settings.apply",
  "args_schema": {},
  "risk_level": "low",
  "preconditions": ["target_visible", "target_enabled"],
  "expected_observation": "settings.applied"
}
```

候选动作由 GUI2TUI 和本地 policy 生成，Jev 不参与创造候选。

### 5.3 Decision

描述 Jev 的选择结果。

建议字段：

```json
{
  "selected_candidate_id": "candidate_12",
  "abstain": false,
  "probabilities": {
    "candidate_12": 0.91,
    "candidate_13": 0.06,
    "abstain": 0.03
  },
  "confidence": 0.91,
  "model": "jev",
  "latency_ms": 143,
  "trace_id": "trace-001"
}
```

必须验证：

- 返回值是否属于原始候选集合。
- 是否存在重复或未知 ID。
- 概率是否有限且在合法范围。
- 是否满足最低置信度。
- 是否对应当前 snapshot generation。
- 是否触发风险策略。

### 5.4 Outcome

描述执行、回读和 handback 结果。

建议字段：

```json
{
  "delivery_state": "delivered",
  "effect": "settings.applied",
  "authoritative_readback": {},
  "evidence": [],
  "next_observation": {},
  "handback_reason": null
}
```

不能把“backend 方法返回成功”直接当作最终成功。必须尽可能通过 GUI 当前公开语义进行 readback。

---

## 6. 安全和数据边界

### 6.1 默认不发送给 Jev 的内容

- 截图。
- 密码字段。
- API Key、Token、Cookie、私钥。
- 剪贴板。
- 无关窗口。
- 未经任务需要的现有编辑内容。
- 完整文档正文。
- 与当前候选判断无关的环境变量。
- 未授权的应用内部数据。

### 6.2 Jev 不应控制的能力

- 删除文件。
- 发送消息。
- 支付。
- 上传文件。
- 提交表单到外部系统。
- 修改账号和安全设置。
- 执行任意命令。
- 输入密码或秘密。
- 自动确认无法估计后果的操作。

### 6.3 最小权限原则

建议每个候选动作都带有：

- `risk_level`。
- `preconditions`。
- `expected_observation`。
- 是否需要人工确认。
- 是否允许 fast-path。
- 是否允许离线 fallback。

Jev 的高置信度不能绕过本地授权策略。

---

## 7. 与 GUI2TUI 作者的合作边界

### 7.1 GUI2TUI 作者负责

- AT-SPI 连接和应用发现。
- 语义树和场景建模。
- TUI 展示和人工交互。
- 目标身份和 freshness。
- action dispatch。
- 输入串行化和取消。
- authoritative readback。
- runtime recovery。
- Headless、容器和 SSH 支持。
- 语义兼容矩阵。

### 7.2 你负责

- Jev Adapter。
- Snapshot 到 bounded decision payload 的投影。
- Choice / Score / Noul 的问题设计。
- 候选筛选和置信度门控策略。
- CLI JSON 接口。
- MCP 接入。
- `SKILL.md` 和 Agent 使用说明。
- fallback 和 provider abstraction。
- trace、replay 和评测。
- registry、Hub 和后续生态分发。
- Jev 与规则、LLM、人工确认之间的路由。

### 7.3 共同维护的接口

双方应尽早冻结：

```text
SemanticSnapshot
ActionCandidate
Decision
Outcome
```

推荐合作方式：

- GUI2TUI 保持自己的内部架构和发布节奏。
- Jev Anything 作为独立仓库或独立上层模块开发。
- 通过稳定 JSON Schema 和版本号集成。
- 不直接依赖对方私有内部模块。
- 使用 mock transport、fixture 和 replay 做并行开发。
- 先完成一个最小端到端闭环，再扩大支持范围。

---

## 8. 首个 Demo 设计

不要一开始选择复杂浏览器、Office 或设计软件。

推荐选择一个公开、无敏感数据、状态变化清晰且容易 readback 的 GTK fixture。

最小闭环：

```text
读取当前 GUI 状态
    ↓
生成 3 个候选动作
    ↓
Jev 选择其中一个或 abstain
    ↓
校验 candidate membership、generation 和风险
    ↓
调用 GUI2TUI 执行器
    ↓
重新读取 GUI 状态
    ↓
返回结构化 Outcome
```

Demo 必须同时展示成功和拒绝：

1. Jev 选择有效候选，操作成功并被 readback 证明。
2. UI 在决策后发生变化，旧候选被拒绝。
3. Jev 置信度不足，返回 `abstain`。
4. 语义不完整，返回 unsupported。
5. Jev 超时或缺少 API Key，走 fallback。
6. 高风险动作不会因为 Jev 置信度高而自动执行。

比单纯展示“Jev 点击了一个按钮”更重要的是展示完整的可信闭环。

---

## 9. 90 天开发路线

### P0：协议先行

目标：先让双方可以独立开发。

任务：

- 定义四个 JSON Schema。
- 定义版本号和兼容策略。
- 做本地 mock Jev provider。
- 做 Snapshot 和 Outcome replay。
- 定义字段脱敏策略。
- 定义候选动作风险等级。
- 定义 trace 格式。
- 建立基本 CI。

验收：

- mock transport 可以完成完整协议调用。
- 未知 candidate ID 会被拒绝。
- stale generation 会被拒绝。
- 所有输入和输出都可以 replay。

### P1：Tracer Bullet

目标：单个 GTK 应用完成真实闭环。

任务：

- observe。
- candidate generation。
- Jev decide。
- local validate。
- action dispatch。
- authoritative readback。
- outcome 返回。

验收：

- 成功场景一条。
- stale 场景一条。
- abstain 场景一条。
- unsupported 场景一条。
- timeout/fallback 场景一条。

### P2：CLI 与 MCP

目标：让同一套核心能力被人类和 Agent 使用。

任务：

- CLI 命令。
- `--json`。
- `--dry-run`。
- `--trace-id`。
- `--timeout`。
- `--no-network`。
- MCP Server。
- Skill 文档。
- 错误和 handback 规范。

验收：

- CLI 与 MCP 使用同一核心协议。
- 人类可以直接检查 JSON。
- Agent 可以发现和调用工具。
- 无网络时有明确 fallback。

### P3：可复用插件

目标：从单个 Demo 变成生态入口。

任务：

- 增加 3 个真实应用。
- 为每个应用建立 Skill。
- 为每个应用建立 fixture。
- 建立支持/限制矩阵。
- 增加长链路 benchmark。
- 设计 registry metadata。
- 评估是否接入 CLI-Hub 风格分发。

验收：

- 3 个应用有真实 E2E 证据。
- 每个应用都能明确说明支持和不支持的语义。
- 每个应用都能输出结构化 trace。

---

## 10. 评测指标

第一版不要只测“Jev 选对没有”。

建议记录：

```text
decision_latency_ms
payload_bytes
payload_tokens
candidate_count
valid_selection_rate
abstain_rate
stale_candidate_block_rate
unsafe_action_block_rate
readback_success_rate
fallback_rate
```

重点关注：

- 快路径决策耗时是否低于 300ms。
- 非法候选执行率是否为 0。
- 具有权威证据的完成率是否高于 95%。
- context 或 payload 是否缩减 70% 以上。
- stale target 是否始终被拒绝。
- fallback 是否可用。
- Jev 置信度和真实成功率是否有校准关系。
- 高风险动作是否始终经过本地策略和人工确认。

建议做以下对照实验：

1. 整棵 UI 语义树 vs 最小候选上下文。
2. Jev fast-path vs 普通 LLM 规划。
3. Jev 决策 vs 纯规则。
4. 有 readback vs 无 readback。
5. 自动操作 vs dry-run。
6. 有网络 vs 无网络 fallback。

---

## 11. 关键风险和应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 把 GUI2TUI 误解成万能 GUI 自动化 | 范围失控、Demo 失真 | 把 AT-SPI 暴露语义作为正式前提，unsupported 必须可见 |
| 把整棵 UI 树发送给 Jev | 延迟、成本、隐私增加 | Candidate-first projection，按任务生成最小证据 |
| Jev 误选高副作用动作 | 删除、发送、支付等事故 | 本地 policy denylist、风险等级、人工确认 |
| 只做 Jev wrapper，没有生态入口 | 难传播、难复用 | 同时设计 CLI JSON、MCP、Skill 和 registry metadata |
| 缺少独立评测 | 只能讲故事 | 建立 replay fixture、真实应用 E2E 和指标台账 |
| Accessibility 质量差异 | 覆盖范围不稳定 | 建立应用/Toolkit 兼容矩阵和能力等级 |
| Jev API 变化 | 适配层失效 | Provider abstraction、版本锁定、mock contract |
| 依赖网络和 API Key | 离线不可用 | 规则 fallback、人工 TUI、明确标注决策来源 |
| 双方直接共享内部实现 | 开发耦合、冲突频繁 | 通过版本化 JSON 协议和独立仓库协作 |
| 名称或品牌误导 | 社区和法律风险 | 确认 Jev 使用规范，避免暗示官方背书 |

---

## 12. 当前不应做的事情

暂时不要：

- 一开始支持所有 GUI Toolkit。
- 一开始实现复杂多步规划。
- 让 Jev 自由生成命令或坐标。
- 把截图直接发送给 Jev。
- 把整棵语义树无筛选地发送给 Jev。
- 绕过 GUI2TUI 的执行器直接注入键鼠。
- 用模型置信度替代本地授权。
- 只做漂亮 Demo 而没有拒绝路径。
- 在没有真实 readback 的情况下声称任务完成。
- 先构建大规模 Hub，再验证最小闭环。

---

## 13. 建议给 GUI2TUI 作者的合作提案

可以发送以下内容作为初步沟通：

> GUI2TUI 已经解决了 GUI 语义获取、TUI 投影和权威状态回读。我想在上层增加一个独立的 Agent/Decision Adapter：GUI2TUI 负责生成当前语义快照和受约束候选动作，我负责将最小上下文投影给 Jev，由 Jev 只返回候选 ID 或 abstain，随后由 GUI2TUI 原有执行器校验、执行和 readback。
>
> 双方可以先冻结 `SemanticSnapshot`、`ActionCandidate`、`Decision`、`Outcome` 四个 JSON 协议。这样 GUI2TUI 可以继续优化前面的 GUI2TUI 能力，我可以独立优化 Jev 接入、CLI/MCP/Skill、fallback 和评测逻辑，双方不会互相侵入内部实现。
>
> 第一阶段只做一个 GTK fixture 的 Tracer Bullet，并刻意验证成功、stale candidate、低置信度、unsupported 和 timeout/fallback 五条路径。

---

## 14. 后续切换到 Codex 后的第一批任务

建议 Codex 接手后按以下顺序执行：

### 任务 1：初始化项目

- 确认是否使用 Rust、Python、TypeScript 或混合结构。
- 建立 git 仓库。
- 建立 `docs/`、`schemas/`、`src/`、`tests/`、`skills/` 目录。
- 将本文件作为前期设计依据。
- 不要立即复制 GUI2TUI 全部代码。

### 任务 2：定义协议

建议新增：

```text
schemas/semantic-snapshot.schema.json
schemas/action-candidate.schema.json
schemas/decision.schema.json
schemas/outcome.schema.json
```

同时定义：

```text
schemas/versioning.md
schemas/redaction-policy.md
schemas/risk-policy.md
```

### 任务 3：实现 mock core

先不连接真实 GUI 和 Jev：

- 用 fixture 生成 SemanticSnapshot。
- 用规则生成 ActionCandidate。
- 用 mock provider 生成 Decision。
- 用 validator 检查 Decision。
- 用 fake dispatcher 生成 Outcome。
- 完成 replay。

### 任务 4：做协议测试

至少覆盖：

- 合法 candidate。
- 未知 candidate。
- stale generation。
- 空候选集合。
- abstain。
- 低置信度。
- 越界概率。
- malformed response。
- timeout。
- provider error。
- redaction。
- 高风险动作拦截。

### 任务 5：连接 GUI2TUI

先实现只读 observe：

```text
GUI2TUI → SemanticSnapshot
```

再实现候选读取：

```text
GUI2TUI → ActionCandidates
```

最后才实现真实执行：

```text
Decision → validate → GUI2TUI dispatch → readback
```

### 任务 6：连接真实 Jev

- 先保留 mock provider。
- 增加真实 provider adapter。
- API Key 只从环境变量或安全配置读取。
- 记录模型版本和 latency。
- 记录请求 payload 的脱敏摘要，而不是默认记录完整敏感内容。
- 增加超时和 fallback。

### 任务 7：制作第一个可公开 Demo

Demo 必须包括：

- 真实 GUI。
- 真实语义状态。
- 候选动作列表。
- Jev 选择。
- 本地校验。
- 执行。
- authoritative readback。
- JSON Outcome。
- 拒绝路径。
- trace。

---

## 15. 最终判断

建议推进，但采用小步验证和协议优先策略。

最好的第一步不是构建“万能的 Jev GUI Agent”，而是完成：

```text
一个 GUI
+ 一个语义快照
+ 三个候选动作
+ 一次 Jev Choice
+ 一次本地校验
+ 一次真实执行
+ 一次权威 readback
+ 一条失败/拒绝路径
```

如果这个闭环真实跑通，项目就不再只是概念，而会具备明确的产品类别和技术护城河：

```text
可验证 GUI 语义
+ 候选动作约束
+ Jev 低延迟决策
+ 确定性执行
+ authoritative readback
+ CLI / MCP / Skill 分发
+ 可回放评测
```

这条路线与 CLI-Anything 不是竞争关系，而是互补关系：

- CLI-Anything 更偏向从软件源码和后端能力生成 Agent CLI。
- GUI2TUI + Jev Anything 更偏向从公开 GUI 语义生成可验证 Agent 接口。

长期来看，Jev Anything 可以成为 GUI 语义到 Agent 工具之间的桥接层。
