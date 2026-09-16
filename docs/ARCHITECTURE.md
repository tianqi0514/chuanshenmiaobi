# 架构边界

## 独立运行

传神妙笔拥有自己的 API、前端、数据库 Schema、对象存储前缀、搜索索引和运行记录。它不调用智库 API 才能完成核心流程。

## 代码级复用

- Semantica：文本归一化、切片、实体关系抽取、Provenance、规则推演。
- DeepSeek Harness：多步骤 Agent、工具调用、事件流、取消和恢复。
- Plate：正式写作编辑器、Slash Command、评论、建议和协同。

复用方式是固定上游版本并通过适配层调用，不复制或修改上游核心算法。

## 中间件复用

开发期允许共用已部署的 PostgreSQL、Redis、RabbitMQ、MinIO、OpenSearch、Qdrant 和 FalkorDB 服务实例，但必须隔离：

- PostgreSQL 使用独立数据库 `chuanshenmiaobi`。
- Redis 使用独立 DB 或 Key Prefix。
- RabbitMQ 使用独立 Virtual Host。
- MinIO 使用独立 Bucket 或 Object Prefix。
- OpenSearch 使用 `chuanshenmiaobi-*` 索引前缀。
- Qdrant 使用 `chuanshenmiaobi-*` Collection 前缀。
- FalkorDB 使用 `chuanshenmiaobi-*` Graph 前缀。

生产部署可以将相同配置切换到独立中间件，不改变应用代码。

## 分阶段实现

1. 真实解析与 Evidence。
2. Entity / Claim / Fact / Relation 分层抽取和确认。
3. 指标公式与依赖图。
4. DeepSeek Harness 写作 Agent。
5. Plate 正文、绑定和联动更新。
6. 版本、导出和生产验证。

