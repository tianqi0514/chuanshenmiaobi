# 真实模型测试

测试模型：`Qwen3.8-27B-FP8`，OpenAI-compatible，关闭 thinking。

## 已验证

- 最小结构化健康请求成功，约 0.65～0.67 秒。
- 真实应急简报完成 Evidence、Entity、Claim、Fact、Relation、指标的顺序调用。
- 完整调用得到 1 个 Evidence、5 个 Entity、6 个 Claim、4 个 Fact 候选。
- 所有 Fact 状态均由服务端固定为 `candidate` 且 `needs_confirmation=true`。
- 服务端验证了 Entity/Claim/Fact/Relation 引用的 ID 均来自真实上游对象。
- 独立指标测试得到 3 个指标，其中 1 个派生指标。
- 独立关系测试得到 1 条有 Fact 和 Evidence 支撑的直接关系。
- 非法 Relation（缺少 Fact ID）首次被严格 Schema 拒绝；随后增加一次严格重试，仍不放宽 Schema。

## 实际发现并修复

1. 模型可能把指标值返回为 JSON number，而不是字符串。Schema 已改为接受数字或文本，公式仍必须是字符串。
2. 模型可能生成缺少 Fact 的 Relation。系统不会接受；提示词要求无支撑时返回空列表，并提供一次严格重试。
3. 连续五层同步抽取总耗时超过两分钟，单层耗时约 1～43 秒。当前 MVP 保留真实耗时，不显示假进度。

## 当前限制

- 当前仍是同步 MVP。进入项目写作阶段前，应改造成可恢复的后台任务和事件流。
- 大文件尚未实现 Evidence 分批、合并和跨批去重。
- Fact 仍是待确认候选，尚未实现人工确认工作台。
- 指标公式尚未进入确定性计算引擎，也尚未绑定 Plate 正文 Chunk。

这些限制不会通过前端文案伪装为已完成能力。
