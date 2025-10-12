#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一路由管理系统 - 主应用程序
整合三个AI服务：文档优化、论点一致性检查、论据支持度评估
"""

import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 导入路由器
from routers.redundancy_agent_router import router as redundancy_agent_router
from routers.table_agent_router import router as table_agent_router
from routers.thesis_agent_router import router as thesis_agent_router  
from routers.web_agent_router import router as web_agent_router

# 应用生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logging.info("🚀 统一AI服务路由系统启动")
    yield
    # 关闭时
    logging.info("🔄 统一AI服务路由系统关闭")

# 创建FastAPI应用
app = FastAPI(
    title="统一AI服务路由系统",
    description="整合文档优化、论点一致性检查、论据支持度评估三个AI服务的统一API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('unified_api.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"❌ 未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "服务器内部错误",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

# 注册路由器
app.include_router(
    redundancy_agent_router,
    prefix="/api/redundancy-agent"
)

app.include_router(
    table_agent_router,
    prefix="/api/table-agent"
)

app.include_router(
    thesis_agent_router,
    prefix="/api/thesis-agent"
)

app.include_router(
    web_agent_router,
    prefix="/api/web-agent"
)

# 根路径和系统信息
@app.get("/", summary="系统信息", description="获取统一AI服务系统信息")
async def root():
    """系统根路径"""
    return {
        "name": "统一AI服务路由系统",
        "version": "1.0.0",
        "description": "整合冗余优化、表格优化、论点一致性检查、论据支持度评估四个AI服务",
        "services": {
            "redundancy_agent": {
                "name": "冗余内容优化服务",
                "prefix": "/api/redundancy-agent",
                "description": "基于AI的文档冗余内容识别和优化服务"
            },
            "table_agent": {
                "name": "表格优化服务",
                "prefix": "/api/table-agent",
                "description": "基于AI的文档表格化内容识别和优化服务"
            },
            "thesis_agent": {
                "name": "论点一致性检查服务", 
                "prefix": "/api/thesis-agent",
                "description": "智能论文论点一致性检查和修正系统"
            },
            "web_agent": {
                "name": "论据支持度评估服务",
                "prefix": "/api/web-agent", 
                "description": "基于AI的智能文档分析系统，用于验证学术文档中论点的事实支撑"
            }
        },
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", summary="健康检查", description="检查所有服务的健康状态")
async def health_check():
    """统一健康检查"""
    try:
        # 检查环境变量和基础配置
        services_status = {
            "redundancy_agent": {
                "status": "healthy" if os.getenv("OPENROUTER_API_KEY") else "degraded",
                "api_available": bool(os.getenv("OPENROUTER_API_KEY"))
            },
            "table_agent": {
                "status": "healthy" if os.getenv("OPENROUTER_API_KEY") else "degraded",
                "api_available": bool(os.getenv("OPENROUTER_API_KEY"))
            },
            "thesis_agent": {
                "status": "healthy" if os.getenv("OPENROUTER_API_KEY") else "degraded", 
                "api_available": bool(os.getenv("OPENROUTER_API_KEY"))
            },
            "web_agent": {
                "status": "healthy" if os.getenv("OPENROUTER_API_KEY") else "degraded",
                "api_available": bool(os.getenv("OPENROUTER_API_KEY"))
            }
        }
        
        # 计算整体状态
        all_healthy = all(service["status"] == "healthy" for service in services_status.values())
        overall_status = "healthy" if all_healthy else "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "services": services_status
        }
        
    except Exception as e:
        logger.error(f"❌ 健康检查失败: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

if __name__ == "__main__":
    import uvicorn
    
    # 启动服务
    import os
    
    # 从环境变量获取配置，适应生产环境
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    print(f"🚀 启动服务器: {host}:{port}")
    print(f"🔄 热重载: {'开启' if reload else '关闭'}")
    print(f"📊 日志级别: {log_level}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level
    )
