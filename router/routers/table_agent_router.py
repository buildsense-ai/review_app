#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Table Agent 路由器
处理文档表格优化的API端点
"""

import os
import sys
import json
import uuid
import logging
import tempfile
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 添加 table_agent_app 到Python路径
table_agent_path = Path(__file__).parent.parent.parent / "table_agent_app"
sys.path.insert(0, str(table_agent_path))

# 添加shared到Python路径
shared_path = Path(__file__).parent.parent.parent / "shared"
sys.path.insert(0, str(shared_path))

try:
    from run_table_agent import TableAgent
except ImportError as e:
    logging.error(f"无法导入table_agent_app模块: {e}")
    TableAgent = None

# 导入统一的任务管理器
from shared import TaskManager, TaskStatus

# 使用统一的任务管理器
task_manager = TaskManager()

# 请求和响应模型
class DocumentOptimizeRequest(BaseModel):
    document_content: str = Field(..., description="文档内容")
    document_title: str = Field(default="文档", description="文档标题")
    filename: str = Field(default="document.md", description="文件名")

# 任务状态响应模型从shared导入
TaskStatusResponse = TaskStatus

# 辅助函数
def create_task_id() -> str:
    """生成唯一任务ID"""
    return str(uuid.uuid4())

def update_task_status(task_id: str, status: str, progress: float, message: str, result: Any = None, error: str = None):
    """更新任务状态（使用统一的TaskManager）"""
    task_manager.update_task(task_id, status=status, progress=progress, message=message, result=result, error=error)

# 创建路由器
router = APIRouter(prefix="", tags=["表格优化"])

logger = logging.getLogger(__name__)

# 异步处理函数
async def process_table_async(task_id: str, request: DocumentOptimizeRequest):
    """异步处理表格优化任务"""
    try:
        update_task_status(task_id, "running", 10.0, "开始表格优化分析")
        
        if not TableAgent:
            raise Exception("TableAgent未正确导入")
        
        # 创建agent实例
        agent = TableAgent()
        
        update_task_status(task_id, "running", 30.0, "执行表格优化分析")
        
        # 处理文档
        unified_sections = agent.process(request.document_content, request.document_title)
        
        update_task_status(task_id, "running", 90.0, "生成输出文件")
        
        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        # 使用统一的输出目录
        results_dir = Path(__file__).parent.parent / "outputs" / "table_agent"
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        unified_sections_file = results_dir / f"table_unified_{task_id}_{timestamp}.json"
        
        # 保存unified_sections JSON文件
        with open(unified_sections_file, 'w', encoding='utf-8') as f:
            json.dump(unified_sections, f, ensure_ascii=False, indent=2)
        
        # 构建结果
        sections_count = sum(len(sections) for sections in unified_sections.values())
        result = {
            "unified_sections_file": str(unified_sections_file),
            "sections_count": sections_count,
            "service_type": "table_agent",
            "message": f"已生成文件: {unified_sections_file.name}",
            "timestamp": timestamp
        }
        
        update_task_status(task_id, "completed", 100.0, "表格优化完成", result=result)
        
    except Exception as e:
        logger.error(f"表格优化任务失败: {e}")
        import traceback
        traceback.print_exc()
        update_task_status(task_id, "failed", 0.0, "处理失败", error=str(e))

@router.get("/test", summary="Test Route")
async def test_route():
    return {"message": "Table Agent 运行正常", "timestamp": datetime.now().isoformat()}

@router.post("/v1/pipeline-async", summary="异步表格优化处理")
async def async_pipeline(request: DocumentOptimizeRequest, background_tasks: BackgroundTasks):
    """
    异步执行表格优化流水线
    
    返回任务ID，可通过 /v1/task/{task_id} 查询进度
    """
    task_id = create_task_id()
    
    # 初始化任务状态
    task_manager.create_task(task_id)
    update_task_status(task_id, "pending", 0.0, "任务已创建，等待处理")
    
    # 添加后台任务
    background_tasks.add_task(process_table_async, task_id, request)
    
    return {"task_id": task_id, "status": "pending", "message": "任务已提交，请使用task_id查询进度"}

@router.get("/v1/task/{task_id}", response_model=TaskStatusResponse, summary="查询任务状态")
async def get_task_status(task_id: str):
    """
    查询异步任务的处理状态和结果
    
    - **task_id**: 任务ID
    """
    if not task_manager.task_exists(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task_manager.get_task_status(task_id)

@router.get("/v1/result/{task_id}", summary="获取表格优化结果")
async def get_unified_sections(task_id: str):
    """
    获取表格优化结果（unified_sections格式）
    
    - **task_id**: 任务ID
    
    返回处理后的章节结果
    """
    if not task_manager.task_exists(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = task_manager.get_task(task_id)
    
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    # 从结果中获取unified_sections文件路径并读取内容
    result = task_info.get("result", {})
    if isinstance(result, dict) and "unified_sections_file" in result:
        unified_sections_file = result["unified_sections_file"]
        
        try:
            with open(unified_sections_file, 'r', encoding='utf-8') as f:
                unified_sections_data = json.load(f)
            return unified_sections_data
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="unified_sections文件不存在")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="未找到unified_sections文件")

