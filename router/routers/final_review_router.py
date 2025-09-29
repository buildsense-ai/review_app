#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档优化服务路由器
基于final_review_agent_app的FastAPI路由器实现
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 添加final_review_agent_app到Python路径
final_review_path = Path(__file__).parent.parent.parent / "final_review_agent_app"
sys.path.insert(0, str(final_review_path))

try:
    from models import (
        DocumentOptimizeRequest, TaskResponse, TaskStatusResponse, 
        TaskResultResponse, HealthResponse, ErrorResponse, TaskStatus
    )
    from task_manager import task_manager
except ImportError as e:
    logging.error(f"无法导入final_review_agent_app模块: {e}")
    # 定义基础模型作为后备
    class TaskStatus:
        PENDING = "pending"
        PROCESSING = "processing" 
        COMPLETED = "completed"
        FAILED = "failed"
    
    class DocumentOptimizeRequest(BaseModel):
        content: str = Field(..., description="Markdown文档内容")
        filename: str = Field(None, description="文件名（可选）")
        options: Dict[str, Any] = Field(default_factory=dict, description="优化选项")
    
    class TaskResponse(BaseModel):
        task_id: str
        status: str
        message: str
        created_at: datetime
    
    class TaskStatusResponse(BaseModel):
        task_id: str
        status: str
        progress: float = None
        message: str
        created_at: datetime
        started_at: datetime = None
        completed_at: datetime = None
        error_message: str = None
    
    class TaskResultResponse(BaseModel):
        task_id: str
        status: str
        result: Dict[str, Any] = None
        error_message: str = None
        created_at: datetime
        completed_at: datetime = None
    
    class HealthResponse(BaseModel):
        status: str
        timestamp: datetime
        version: str
        api_available: bool
    
    task_manager = None

# 创建路由器
router = APIRouter(prefix="", tags=["文档优化"])

logger = logging.getLogger(__name__)

# @router.get("/test")
# async def test_route():
#     """测试路由是否工作"""
#     return {"message": "文档优化服务路由工作正常!"}

# @router.get("/", summary="服务信息")
# async def service_info():
#     """获取文档优化服务信息"""
#     return {
#         "service": "文档优化服务",
#         "description": "基于AI的智能文档质量分析和优化服务",
#         "version": "1.0.0",
#         "endpoints": {
#             "optimize": "/optimize",
#             "optimize_sync": "/optimize/sync", 
#             "task_status": "/tasks/{task_id}/status",
#             "task_result": "/tasks/{task_id}/result",
#             "task_list": "/tasks",
#             "health": "/health"
#         }
#     }

@router.get("/health", response_model=HealthResponse, summary="健康检查")
async def health_check():
    """文档优化服务健康检查"""
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

@router.post("/optimize", response_model=TaskResponse, summary="提交文档优化任务")
async def optimize_document(request: DocumentOptimizeRequest, background_tasks: BackgroundTasks):
    """
    提交文档优化任务
    
    - **content**: Markdown文档内容（必需）
    - **filename**: 文件名（可选）
    - **options**: 优化选项（可选）
    
    返回任务ID，可用于查询任务状态和结果
    """
    if not task_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务管理器未初始化"
        )
    
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

@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse, summary="查询任务状态")
async def get_task_status(task_id: str):
    """
    查询任务状态
    
    - **task_id**: 任务ID
    
    返回任务的详细状态信息，包括进度、消息等
    """
    if not task_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务管理器未初始化"
        )
    
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

@router.get("/tasks/{task_id}/result", response_model=TaskResultResponse, summary="获取任务结果")
async def get_task_result(task_id: str):
    """
    获取任务结果
    
    - **task_id**: 任务ID
    
    返回完整的优化结果，包括原始内容、优化后内容、分析摘要等
    """
    if not task_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务管理器未初始化"
        )
    
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

@router.delete("/tasks/{task_id}", summary="删除任务")
async def delete_task(task_id: str):
    """
    删除任务
    
    - **task_id**: 任务ID
    
    删除任务及其所有相关数据
    """
    if not task_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务管理器未初始化"
        )
    
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

@router.get("/tasks", summary="列出所有任务")
async def list_tasks():
    """
    列出所有任务
    
    返回系统中所有任务的基本信息
    """
    if not task_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务管理器未初始化"
        )
    
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

@router.get("/tasks/{task_id}/unified-sections", summary="获取统一章节结果")
async def get_unified_sections(task_id: str):
    """
    获取任务的统一章节结果（unified_sections格式）
    
    - **task_id**: 任务ID
    
    返回处理后的章节结果，格式为嵌套的章节结构
    """
    if not task_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务管理器未初始化"
        )
    
    try:
        task_info = task_manager.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"任务不存在: {task_id}"
            )
        
        if task_info.status != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="任务尚未完成"
            )
        
        # 从结果中获取unified_sections文件路径并读取内容
        result = task_info.result
        if result and "unified_sections_file" in result:
            unified_sections_file = result["unified_sections_file"]
            
            try:
                import json
                with open(unified_sections_file, 'r', encoding='utf-8') as f:
                    unified_sections_data = json.load(f)
                return unified_sections_data
            except FileNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="unified_sections文件不存在"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"读取文件失败: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到unified_sections文件"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取统一章节结果失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统一章节结果失败: {str(e)}"
        )

@router.post("/tasks/cleanup", summary="清理过期任务")
async def cleanup_tasks(max_age_hours: int = 24):
    """
    清理过期任务
    
    - **max_age_hours**: 最大保留时间（小时），默认24小时
    
    清理超过指定时间的已完成任务
    """
    if not task_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务管理器未初始化"
        )
    
    try:
        task_manager.cleanup_completed_tasks(max_age_hours)
        
        return {"message": f"已清理超过 {max_age_hours} 小时的过期任务"}
        
    except Exception as e:
        logger.error(f"❌ 清理任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理任务失败: {str(e)}"
        )

@router.post("/optimize/sync", summary="同步文档优化")
async def optimize_document_sync(request: DocumentOptimizeRequest):
    """
    同步文档优化
    
    直接返回优化结果，适用于小文档的快速处理
    注意：大文档建议使用异步接口 /optimize
    """
    if not task_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务管理器未初始化"
        )
    
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
