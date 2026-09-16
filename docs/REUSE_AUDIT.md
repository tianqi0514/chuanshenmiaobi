# 代码复用审计

## 直接采用的上游能力

| 来源 | 版本 | 用途 | 当前阶段 |
|---|---|---|---|
| Semantica | `cce5ea177cbac29a526effa546219c48f8ec36f4` | Normalize / Split | 已接入 |
| DeepSeek Harness | `cd5ef8148158c3a752a658978873241fdf8e2bbc` | Agent Loop / Session Event | 预留适配层 |
| Plate | `8f65d77f8b4709833436e63661e4d061f709258f` | 编辑器 | 下一阶段接入 |

## 参考但不直接复制的智库实现

- `packages/semantica_adapter/parse.py`：多格式解析和 Provenance 设计。
- `packages/semantica_adapter/extract.py`：模型结构化抽取和原文锚定。
- `apps/worker/tasks.py`：任务进度、增量复用和发布一致性。
- `packages/platform/writing_sample_profile.py`：样稿不作为事实的安全边界。

## 明确不搬迁

- 智库租户、应用发布和知识产品模型。
- 智库静态前端和旧妙笔工作台。
- 自动把 RelationAssertion 当作权威写作事实的路径。
- 与妙笔写作无关的治理、数据库和运营页面。

