# V2

V2 是一个独立重写的经营系统，不直接复制旧系统的模块、页面或数据表。

当前阶段：主数据核心第一版，已经可以本地启动和测试；尚未接入生产数据库，也不替换本地 8000 服务。

## 不可违反的数据规则

1. 客户、供应商、公司和其他往来主体使用同一套规范主体主档；角色可以并存，但不能按业务模块复制主档。
2. 一个真实公司只能有一个规范身份；同一主体同时是客户和供应商时，只增加角色，不新建第二条主体记录。
3. 产品使用唯一规范产品主档；采购、销售、库存、财务和生产只能引用同一个 `product_id`。
4. 外部平台的编号、名称和原始报文是来源证据或外部映射，不是第二套业务主档。
5. 原始导入记录必须保留且不可覆盖；规范主档的变更必须可追溯。
6. 仅凭名称相似不能自动合并主体或产品；无法确认时进入待审核状态。

## 建设原则

- 先定义领域契约，再写数据库和 API。
- 先做可测试的主数据核心，再逐步接入采购、销售、库存和财务。
- V2 与旧系统并行验证，数据迁移可回滚，旧系统不作为 V2 的运行依赖。
- 每个阶段都要有真实可运行结果、测试和数据一致性检查。

具体规则见 [`docs/DOMAIN_DATA_CONTRACT.md`](docs/DOMAIN_DATA_CONTRACT.md)，阶段计划见 [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)。

## 本地运行

在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

当前可用接口：

- `GET /healthz`：服务和数据模型健康检查。
- `POST /api/v1/parties/resolve`：将客户、供应商、公司等主体解析到同一个规范主体主档。
- `POST /api/v1/products/resolve`：将外部产品来源解析到唯一规范产品主档。
- `POST /api/v1/source-records/{source_record_id}/resolve`：人工确认待审核来源记录的规范归属。

## 当前边界

- 本地默认使用 SQLite；正式环境接入前还需要建立迁移、权限、审计和备份流程。
- 外部平台连接器、采购/销售/库存业务模块尚未接入。
- 解析无法确认时只产生待审核来源记录，不会按名称自动创建第二个主体或产品。
- 本轮没有修改旧系统，也没有占用或替换 8000 端口。
