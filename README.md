# 传神妙笔

面向专业写作的独立产品。第一阶段先完成一条可核验的最小链路：

`上传材料 → 解析 → Evidence 切片 → 查看每一步提示词与输出`

后续在此基础上接入 Entity / Claim / Fact / Relation、指标公式、DeepSeek Harness Agent 和 Plate 编辑器。

## 产品边界

- 妙笔独立运行，不依赖“传神智库”API。
- 复用 Semantica 的文本归一化与切片能力，不复制其算法。
- 可以连接现有中间件，但使用独立数据库和命名空间。
- 当前页面只展示真实执行结果；尚未运行的步骤明确显示“尚未运行”。

## 本地启动

```bash
cp .env.example .env
docker compose up --build
```

访问：<http://localhost:8101/>

API 健康检查：<http://localhost:8100/health>

## 开发

```bash
python -m venv .venv
.venv/bin/pip install --no-deps \
  "git+https://github.com/semantica-agi/semantica.git@cce5ea177cbac29a526effa546219c48f8ec36f4"
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn apps.api.main:app --reload --port 8100

cd apps/web
npm install
npm run dev
```

这里对 Semantica 使用锁定提交并按适配器所需模块轻量安装，避免把其完整实验与模型依赖带进妙笔 API 镜像。妙笔只调用公开的归一化、切片接口；如后续启用更多 Semantica 能力，将按对应能力补齐并验证依赖。

## 固定上游版本

- Semantica: `cce5ea177cbac29a526effa546219c48f8ec36f4`
- DeepSeek Harness: `cd5ef8148158c3a752a658978873241fdf8e2bbc`
- Plate: `8f65d77f8b4709833436e63661e4d061f709258f`

详见 [架构边界](docs/ARCHITECTURE.md) 和 [代码复用审计](docs/REUSE_AUDIT.md)。
