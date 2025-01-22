# Cursor Account API 本地开发指南

## 环境要求
- Python 3.8+
- PostgreSQL 12+
- pip (Python包管理器)

## 本地开发设置步骤

1. 安装 PostgreSQL
```bash
# Windows 用户
# 从 https://www.postgresql.org/download/windows/ 下载并安装

# Mac 用户
brew install postgresql

# Linux (Ubuntu) 用户
sudo apt-get install postgresql
```

2. 创建数据库
```sql
CREATE DATABASE cursor_db;
```

3. 安装 Python 依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
- 复制 `.env.example` 到 `.env`
- 修改 `.env` 文件中的数据库连接信息：
```
POSTGRES_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/cursor_db
```
注意：将 `your_password` 替换为你的实际 PostgreSQL 密码

5. 运行开发服务器
```bash
uvicorn api:app --reload
```

## API 端点

- `GET /` - API 信息
- `GET /accounts` - 获取所有账号
- `GET /account/random` - 随机获取一个账号
- `POST /account` - 创建新账号

## API 文档
运行服务器后，访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发工具建议
- VS Code 或 PyCharm
- PostgreSQL 管理工具：pgAdmin 或 DBeaver

## 调试提示
1. 查看日志
```bash
tail -f logs/api.log
```

2. 数据库迁移（如果需要）
```bash
# 待添加
```

3. 测试数据导入
```bash
# 从 cursor_accounts.txt 导入数据
# API 启动时会自动执行
``` 