# 统一AI服务路由系统

一个基于FastAPI的统一AI服务路由系统，整合了三个核心AI服务：

- 🔧 **Final Review Agent**: 文档优化服务
- 📝 **Thesis Agent**: 论点一致性检查服务  
- 🔍 **Web Agent**: 论据支持度评估服务

## 🚀 快速部署

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd revise_tool_app
```

### 2. 自动部署

```bash
./deploy.sh
```

### 3. 配置环境变量

```bash
cd router
cp .env.example .env
# 编辑 .env 文件，填入你的API密钥
nano .env
```

### 4. 启动服务

#### 开发模式
```bash
cd router
python3 main.py
```

#### 生产模式 (推荐)
```bash
cd router
nohup python3 main.py > ../logs/app.log 2>&1 &
```

#### 使用uvicorn
```bash
cd router
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ../logs/app.log 2>&1 &
```

## 📋 环境要求

- Python 3.8+
- 所需依赖见 `router/requirements.txt`

## 🔧 配置说明

主要配置项（在 `.env` 文件中）：

```env
# 必需配置
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=qwen/qwen-2.5-32b-instruct

# 可选配置
LOG_LEVEL=INFO
MAX_WORKERS=5
DEFAULT_OUTPUT_DIR=./test_results
```

## 🌐 API端点

服务启动后，访问以下端点：

- **健康检查**: `GET /health`
- **API文档**: `GET /docs`
- **文档优化**: `POST /api/final-review/optimize`
- **论点检查**: `POST /api/thesis-agent/v1/pipeline-async`
- **论据评估**: `POST /api/web-agent/v1/pipeline-async`

## 🧪 测试

```bash
cd router
python3 test_router.py
```

## 📊 监控

### 检查服务状态
```bash
curl http://localhost:8000/health
```

### 查看日志
```bash
tail -f logs/app.log
```

### 检查进程
```bash
ps aux | grep python
```

### 停止服务
```bash
# 查找进程ID
ps aux | grep "main.py"
# 停止进程
kill <PID>
```

## 🔍 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   lsof -i :8000
   kill -9 <PID>
   ```

2. **API密钥错误**
   - 检查 `.env` 文件中的 `OPENROUTER_API_KEY`
   - 确保密钥有效且有足够余额

3. **依赖安装失败**
   ```bash
   pip install --upgrade pip
   pip install -r router/requirements.txt
   ```

4. **权限问题**
   ```bash
   chmod +x deploy.sh
   ```

## 📁 项目结构

```
revise_tool_app/
├── router/                 # 主要路由系统
│   ├── main.py            # 主应用入口
│   ├── routers/           # 各服务路由
│   ├── config.py          # 配置管理
│   └── requirements.txt   # 依赖列表
├── final_review_agent_app/ # 文档优化服务
├── thesis_agent_app/      # 论点检查服务
├── web_agent_app/         # 论据评估服务
├── deploy.sh              # 部署脚本
└── README.md              # 本文件
```

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

[MIT License](LICENSE)
# review_app
