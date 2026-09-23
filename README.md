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
V2_DATABASE_URL=sqlite:///./data/v2.db .venv/bin/alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests
export V2_API_KEY='请在本地环境保存随机长密钥'
export V2_API_ACTOR_ID=local-admin
export V2_API_ROLE=admin
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

服务启动不会自动建表；首次启动必须先执行 Alembic 迁移。以上迁移命令针对空库或全新检出目录；如果本地库是早期 `create_all` 自动创建的旧开发库，不要直接执行 `upgrade head`，应先做结构和数据核对。本项目尚未对任何生产库执行迁移。

当前可用接口：

- `GET /healthz`：服务和数据模型健康检查。
- `GET /api/v1/parties/{party_id}`：读取统一主体主档及角色、强标识。
- `GET /api/v1/products/{product_id}`：读取统一产品主档及强标识。
- `GET /api/v1/source-records/review`：读取待人工确认的来源记录。
- `GET /api/v1/audit-events`：按规范实体或来源记录读取处理审计事件。
- `POST /api/v1/parties/resolve`：将客户、供应商、公司等主体解析到同一个规范主体主档。
- `POST /api/v1/products/resolve`：将外部产品来源解析到唯一规范产品主档。
- `POST /api/v1/source-records/{source_record_id}/resolve`：人工确认待审核来源记录的规范归属。

除 `/healthz` 外，接口需要 `Authorization: Bearer $V2_API_KEY`。默认 `admin` 和 `operator` 可以写入，`viewer` 只能读取；可通过 `V2_API_READ_ROLES` 和 `V2_API_WRITE_ROLES` 调整角色集合。

## 当前边界

- 本地默认使用 SQLite；第一版 Alembic 迁移已加入，正式环境接入前还需要完善用户中心、细粒度权限和备份流程。
- 主数据审计事件已加入；直接服务层调用记为 `actor_type=system`，通过 API 的调用会记录 `actor_type=api` 及操作者 ID。
- 单条主数据解析会在来源记录中保存完整解析请求字段和额外原始 `payload`，文件导入仍需另外保存原文件和原始行。
- 当前认证是单个环境 API Key + 角色配置，尚未实现用户表、密钥轮换、登录会话和细粒度权限。
- 外部平台付费连接器暂不接入；规划采用人工下载/导出后导入。当前文件上传/批量导入工作流和采购/销售/库存模块尚未实现，现有解析接口只接收单条 JSON。
- 解析无法确认时只产生待审核来源记录，不会按名称自动创建第二个主体或产品。
- 本轮没有修改旧系统，也没有占用或替换 8000 端口。
