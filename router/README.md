# 统一AI服务路由系统

整合三个AI服务的统一FastAPI路由管理系统：
- **文档优化服务** (final_review_agent)
- **论点一致性检查服务** (thesis_agent)  
- **论据支持度评估服务** (web_agent)

## 系统架构

```
router/
├── main.py                    # 主应用程序
├── config.py                  # 统一配置管理
├── start_server.py           # 启动脚本
├── requirements.txt          # 依赖包
├── README.md                 # 说明文档
└── routers/                  # 路由器模块
    ├── __init__.py
    ├── final_review_router.py    # 文档优化路由器
    ├── thesis_agent_router.py    # 论点一致性检查路由器
    └── web_agent_router.py       # 论据支持度评估路由器
```

## 服务端点

### 系统信息
- `GET /` - 系统根路径和服务信息
- `GET /health` - 统一健康检查
- `GET /docs` - API文档 (Swagger UI)
- `GET /redoc` - API文档 (ReDoc)

### 文档优化服务 (`/api/final-review`)
- `GET /api/final-review/test` - 测试路由
- `GET /api/final-review/health` - 健康检查
- `POST /api/final-review/optimize` - 提交文档优化任务
- `POST /api/final-review/optimize/sync` - 同步文档优化
- `GET /api/final-review/tasks/{task_id}/status` - 查询任务状态
- `GET /api/final-review/tasks/{task_id}/result` - 获取任务结果
- `GET /api/final-review/tasks` - 列出所有任务
- `DELETE /api/final-review/tasks/{task_id}` - 删除任务
- `POST /api/final-review/tasks/cleanup` - 清理过期任务

### 论点一致性检查服务 (`/api/thesis-agent`)
- `GET /api/thesis-agent/test` - 测试路由
- `GET /api/thesis-agent/health` - 健康检查
- `POST /api/thesis-agent/v1/extract-thesis` - 提取核心论点
- `POST /api/thesis-agent/v1/check-consistency` - 检查论点一致性
- `POST /api/thesis-agent/v1/correct-document` - 修正文档
- `POST /api/thesis-agent/v1/pipeline` - 完整流水线处理
- `POST /api/thesis-agent/v1/upload` - 文件上传处理
- `POST /api/thesis-agent/v1/pipeline-async` - 异步流水线处理
- `GET /api/thesis-agent/v1/task/{task_id}` - 查询任务状态
- `GET /api/thesis-agent/v1/download/{task_id}` - 下载处理结果

### 论据支持度评估服务 (`/api/web-agent`)
- `GET /api/web-agent/test` - 测试路由
- `GET /api/web-agent/health` - 健康检查
- `POST /api/web-agent/v1/extract-claims` - 提取论断
- `POST /api/web-agent/v1/search-evidence` - 搜索证据
- `POST /api/web-agent/v1/analyze-evidence` - 分析证据
- `POST /api/web-agent/v1/websearch` - 网络搜索
- `POST /api/web-agent/v1/pipeline` - 完整流水线处理
- `POST /api/web-agent/v1/upload` - 文件上传处理
- `POST /api/web-agent/v1/pipeline-async` - 异步流水线处理
- `GET /api/web-agent/v1/task/{task_id}` - 查询任务状态
- `GET /api/web-agent/v1/download/{task_id}` - 下载处理结果

## 安装和运行

### 1. 安装依赖
```bash
cd router
pip install -r requirements.txt
```

### 2. 配置环境变量
创建 `.env` 文件或设置环境变量：
```bash
# OpenRouter API配置
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# 搜索API配置
CUSTOM_SEARCH_API_URL=http://43.139.19.144:8005/search

# 系统配置
MAX_WORKERS=5
TEMPERATURE=0.3
LOG_LEVEL=INFO
```

### 3. 启动服务
```bash
# 使用启动脚本
python start_server.py

# 或直接使用uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问服务
- API文档: http://localhost:8000/docs
- 系统信息: http://localhost:8000/
- 健康检查: http://localhost:8000/health

## 使用示例

### 文档优化
```python
import requests

# 提交优化任务
response = requests.post("http://localhost:8000/api/final-review/optimize", json={
    "content": "# 示例文档\n\n这是一个需要优化的文档...",
    "filename": "example.md"
})
task_id = response.json()["task_id"]

# 查询任务状态
status = requests.get(f"http://localhost:8000/api/final-review/tasks/{task_id}/status")
print(status.json())
```

### 论点一致性检查
```python
# 完整流水线处理
response = requests.post("http://localhost:8000/api/thesis-agent/v1/pipeline", json={
    "document_content": "# 论文标题\n\n## 引言\n这是一篇关于...",
    "document_title": "示例论文",
    "auto_correct": True
})
print(response.json())
```

### 论据支持度评估
```python
# 完整流水线处理
response = requests.post("http://localhost:8000/api/web-agent/v1/pipeline", json={
    "content": "# 研究报告\n\n人工智能将改变世界...",
    "max_claims": 10,
    "use_section_based_processing": True
})
print(response.json())
```

## 配置说明

系统支持通过环境变量进行配置，主要配置项包括：

### API配置
- `OPENROUTER_API_KEY`: OpenRouter API密钥
- `OPENROUTER_MODEL`: 使用的AI模型
- `CUSTOM_SEARCH_API_URL`: 搜索API地址

### 性能配置
- `MAX_WORKERS`: 最大工作线程数
- `TEMPERATURE`: 模型温度参数
- `MAX_TOKENS`: 最大token数

### 功能配置
- `ENABLE_PARALLEL_PROCESSING`: 是否启用并行处理
- `DEFAULT_AUTO_CORRECT`: 是否默认自动修正
- `SAVE_INTERMEDIATE_RESULTS`: 是否保存中间结果

## 注意事项

1. **依赖关系**: 系统依赖原有的三个服务模块，需要确保相关Python包可以正确导入
2. **API密钥**: 需要配置有效的OpenRouter API密钥才能正常工作
3. **搜索服务**: 论据支持度评估服务需要外部搜索API支持
4. **资源使用**: 并行处理会占用更多系统资源，根据服务器配置调整`MAX_WORKERS`
5. **日志文件**: 系统会生成日志文件，注意磁盘空间使用

## 故障排除

### 常见问题
1. **模块导入失败**: 检查Python路径和依赖包安装
2. **API调用失败**: 检查API密钥和网络连接
3. **任务处理超时**: 调整超时配置或检查系统资源
4. **文件权限错误**: 确保输出目录有写入权限

### 日志查看
```bash
# 查看应用日志
tail -f unified_api.log

# 查看特定服务日志
tail -f final_review_agent_app/fastapi_app.log
tail -f thesis_agent_app/thesis_api.log
```
