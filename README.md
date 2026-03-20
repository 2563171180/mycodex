# mycodex

沭阳县金鑫冷链冰棒管理系统，一个基于 Python 标准库 + SQLite + 原生 HTML/CSS/JS 的前后端示例项目。

## 功能特性

- 冰棒库存的新增、编辑、删除
- 低库存和 30 天内临期预警
- 按名称 / 口味 / 供应商 / 库区筛选
- 冷库分区统计、库存总量和库存货值看板
- SQLite 本地持久化，启动后自动建表

## 项目结构

```text
.
├── app.py              # 后端服务与 API
├── data/               # SQLite 数据目录
├── static/
│   ├── index.html      # 前端页面
│   ├── styles.css      # 页面样式
│   └── app.js          # 前端交互逻辑
└── requirements.txt    # 依赖说明
```

## 启动方式

```bash
python3 app.py
```

启动后访问：<http://127.0.0.1:8000>

## API 概览

- `GET /api/popsicles`：获取冰棒列表，可带 `keyword` 和 `zone` 查询参数
- `POST /api/popsicles`：新增冰棒记录
- `PUT /api/popsicles/{id}`：更新冰棒记录
- `DELETE /api/popsicles/{id}`：删除冰棒记录
- `GET /api/summary`：获取看板统计数据
- `GET /health`：健康检查

## 示例数据

首次启动后可直接通过页面录入冰棒信息，例如：

- 名称：牛奶雪糕
- 口味：草莓
- 冷库分区：A-01
- 当前库存：1200
- 单价：3.50
- 最低库存预警值：300
- 供应商：宿迁冷饮厂
- 生产日期：2026-03-01
- 到期日期：2026-08-01

## 技术说明

- 后端：`http.server` + `sqlite3`
- 前端：原生 HTML / CSS / JavaScript
- 数据库：SQLite

如果您后续希望扩展为扫码出入库、员工权限、财务报表或微信端填报，我也可以继续帮您升级这一套系统。
