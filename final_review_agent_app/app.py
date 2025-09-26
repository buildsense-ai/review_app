#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档优化FastAPI应用
提供异步文档优化服务的REST API
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import (
    DocumentOptimizeRequest, TaskResponse, TaskStatusResponse, 
    TaskResultResponse, HealthResponse, ErrorResponse, TaskStatus
)
from task_manager import task_manager


# 应用生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logging.info("🚀 文档优化API服务启动")
    yield
    # 关闭时
    task_manager.shutdown()
    logging.info("🔄 文档优化API服务关闭")


# 创建FastAPI应用
app = FastAPI(
    title="文档优化API",
    description="基于AI的智能文档质量分析和优化服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fastapi_app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# 异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"❌ 未处理的异常: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="InternalServerError",
            message="服务器内部错误",
            detail=str(exc),
            timestamp=datetime.now()
        ).dict()
    )


# API路由
@app.get("/", summary="根路径", description="API服务根路径")
async def root():
    """根路径"""
    return {
        "message": "文档优化API服务",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, summary="健康检查", description="检查API服务健康状态")
async def health_check():
    """健康检查"""
    try:
        # 检查OpenRouter API是否可用
        api_available = bool(os.getenv("OPENROUTER_API_KEY"))
        
        return HealthResponse(
            status="healthy" if api_available else "degraded",
            timestamp=datetime.now(),
            version="1.0.0",
            api_available=api_available
        )
    except Exception as e:
        logger.error(f"❌ 健康检查失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务不可用"
        )


@app.post("/optimize", response_model=TaskResponse, summary="提交文档优化任务", description="提交Markdown文档进行异步优化处理")
async def optimize_document(request: DocumentOptimizeRequest, background_tasks: BackgroundTasks):
    """
    提交文档优化任务
    
    - **content**: Markdown文档内容（必需）
    - **filename**: 文件名（可选）
    - **options**: 优化选项（可选）
    
    返回任务ID，可用于查询任务状态和结果
    """
    try:
        # 验证输入
        if not request.content or not request.content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文档内容不能为空"
            )
        
        if len(request.content) > 1000000:  # 1MB限制
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="文档内容过大，请限制在1MB以内"
            )
        
        # 创建任务
        task_id = task_manager.create_task(
            content=request.content,
            filename=request.filename,
            options=request.options
        )
        
        # 在后台启动任务
        background_tasks.add_task(task_manager.start_task, task_id)
        
        logger.info(f"📝 创建文档优化任务: {task_id}")
        
        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            message="文档优化任务已创建，正在处理中",
            created_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 创建优化任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建任务失败: {str(e)}"
        )


@app.get("/tasks/{task_id}/status", response_model=TaskStatusResponse, summary="查询任务状态", description="根据任务ID查询处理状态和进度")
async def get_task_status(task_id: str):
    """
    查询任务状态
    
    - **task_id**: 任务ID
    
    返回任务的详细状态信息，包括进度、消息等
    """
    try:
        task_info = task_manager.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"任务不存在: {task_id}"
            )
        
        return TaskStatusResponse(
            task_id=task_info.task_id,
            status=task_info.status,
            progress=task_info.progress,
            message=task_info.message,
            created_at=task_info.created_at,
            started_at=task_info.started_at,
            completed_at=task_info.completed_at,
            error_message=task_info.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 查询任务状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询任务状态失败: {str(e)}"
        )


@app.get("/tasks/{task_id}/result", response_model=TaskResultResponse, summary="获取任务结果", description="获取已完成任务的优化结果")
async def get_task_result(task_id: str):
    """
    获取任务结果
    
    - **task_id**: 任务ID
    
    返回完整的优化结果，包括原始内容、优化后内容、分析摘要等
    """
    try:
        task_info = task_manager.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"任务不存在: {task_id}"
            )
        
        return TaskResultResponse(
            task_id=task_info.task_id,
            status=task_info.status,
            result=task_info.result,
            error_message=task_info.error_message,
            created_at=task_info.created_at,
            completed_at=task_info.completed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取任务结果失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务结果失败: {str(e)}"
        )


@app.delete("/tasks/{task_id}", summary="删除任务", description="删除指定的任务及其结果")
async def delete_task(task_id: str):
    """
    删除任务
    
    - **task_id**: 任务ID
    
    删除任务及其所有相关数据
    """
    try:
        success = task_manager.delete_task(task_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"任务不存在: {task_id}"
            )
        
        logger.info(f"🗑️ 删除任务: {task_id}")
        
        return {"message": f"任务 {task_id} 已删除"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除任务失败: {str(e)}"
        )


@app.get("/tasks", summary="列出所有任务", description="获取所有任务的列表和状态")
async def list_tasks():
    """
    列出所有任务
    
    返回系统中所有任务的基本信息
    """
    try:
        tasks = task_manager.list_tasks()
        
        task_list = []
        for task_id, task_info in tasks.items():
            task_list.append({
                "task_id": task_info.task_id,
                "status": task_info.status,
                "filename": task_info.filename,
                "created_at": task_info.created_at,
                "progress": task_info.progress,
                "message": task_info.message
            })
        
        return {
            "total": len(task_list),
            "tasks": task_list
        }
        
    except Exception as e:
        logger.error(f"❌ 列出任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出任务失败: {str(e)}"
        )


@app.post("/tasks/cleanup", summary="清理过期任务", description="清理已完成的过期任务")
async def cleanup_tasks(max_age_hours: int = 24):
    """
    清理过期任务
    
    - **max_age_hours**: 最大保留时间（小时），默认24小时
    
    清理超过指定时间的已完成任务
    """
    try:
        task_manager.cleanup_completed_tasks(max_age_hours)
        
        return {"message": f"已清理超过 {max_age_hours} 小时的过期任务"}
        
    except Exception as e:
        logger.error(f"❌ 清理任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理任务失败: {str(e)}"
        )


# 同步优化接口（用于简单场景）
@app.post("/optimize/sync", summary="同步文档优化", description="同步处理文档优化（适用于小文档）")
async def optimize_document_sync(request: DocumentOptimizeRequest):
    """
    同步文档优化
    
    直接返回优化结果，适用于小文档的快速处理
    注意：大文档建议使用异步接口 /optimize
    """
    try:
        # 验证输入
        if not request.content or not request.content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文档内容不能为空"
            )
        
        if len(request.content) > 100000:  # 100KB限制
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="同步处理仅支持100KB以内的文档，大文档请使用异步接口"
            )
        
        # 创建并立即处理任务
        task_id = task_manager.create_task(
            content=request.content,
            filename=request.filename,
            options=request.options
        )
        
        # 同步处理
        await task_manager.start_task(task_id)
        
        # 等待完成（简单轮询）
        import asyncio
        max_wait = 300  # 最大等待5分钟
        wait_time = 0
        
        while wait_time < max_wait:
            task_info = task_manager.get_task_status(task_id)
            if task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                break
            await asyncio.sleep(1)
            wait_time += 1
        
        # 获取结果
        task_info = task_manager.get_task_status(task_id)
        
        if task_info.status == TaskStatus.COMPLETED:
            result = TaskResultResponse(
                task_id=task_info.task_id,
                status=task_info.status,
                result=task_info.result,
                error_message=task_info.error_message,
                created_at=task_info.created_at,
                completed_at=task_info.completed_at
            )
            
            # 清理任务
            task_manager.delete_task(task_id)
            
            return result
        else:
            # 处理失败或超时
            error_msg = task_info.error_message or "处理超时"
            task_manager.delete_task(task_id)
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文档优化失败: {error_msg}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 同步优化失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步优化失败: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    # 确保必要的目录存在
    os.makedirs("./temp_results", exist_ok=True)
    
    # 启动服务
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
