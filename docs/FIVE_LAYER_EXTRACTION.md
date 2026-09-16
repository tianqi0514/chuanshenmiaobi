# 五层抽取设计

## 五层关系

```text
原始文件
  → Evidence：可定位、不可伪造的原文证据
  → Entity：原文涉及的稳定业务对象
  → Claim：来源明确表达了什么
  → Fact：经过来源、时间、范围与冲突检查的事实候选
  → Relation：由 Fact 支撑的对象直接关系
```

这些对象不是五份互不相关的模型摘要。它们通过稳定 ID 形成可追踪链：

- Entity 必须引用 Evidence。
- Claim 必须引用 Evidence。
- Fact 必须引用 Claim 与 Evidence。
- Relation 必须引用 Entity、Fact 与 Evidence。
- 指标和公式依赖 Fact 与 Evidence，后续再绑定正文 Chunk。

## 哪些步骤使用模型

| 步骤 | 执行方式 | 模型边界 |
|---|---|---|
| 材料归类 | 用户确认 | 模型最多推荐，不能覆盖用户选择 |
| 样稿结构 | 大模型 | 只学习结构、章节职责和文风 |
| Evidence | 确定性 | 解析器和 Semantica Normalize/Split |
| Entity | 大模型 + 引用校验 | 只生成候选，必须引用 Evidence |
| Claim | 大模型 + 引用校验 | 区分陈述、要求、预测、建议和观点 |
| Fact | 混合校验 | 模型输出固定为 candidate，不能自证为已核验 |
| Relation | 混合校验 | 必须引用真实 Entity、Fact 和 Evidence |
| 指标公式 | 混合校验 | 模型只提出候选，正式数值由确定性引擎计算 |

## 对写作的直接用途

- Evidence 支撑正文引用和原文定位。
- Entity 保证跨章节名称一致。
- Claim 防止把建议或观点写成事实。
- Fact 为正式段落提供可确认的事实输入。
- Relation 支撑影响路径、关联检索和 Semantica 推演。
- 指标依赖为后续“修改输入—查看影响—选择应用”提供依赖图。

模型提示词、输入与输出都在页面逐步展示；程序不会展示模型私有思维过程。
