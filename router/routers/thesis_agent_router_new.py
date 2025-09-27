"""
论点一致性检查服务路由
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from typing import Optional, Dict, Any
import httpx
import asyncio
import uuid
import time
import logging
from datetime import datetime
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/thesis-agent", tags=["论点一致性检查"])

# 任务存储
task_storage: Dict[str, Dict] = {}

# Pydantic 模型
from pydantic import BaseModel

class PipelineRequest(BaseModel):
    document_content: str
    document_title: Optional[str] = None
    auto_correct: bool = True

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    updated_at: str

def create_task_id() -> str:
    """生成唯一任务ID"""
    return str(uuid.uuid4())

def update_task_status(task_id: str, status: str, progress: float, message: str, 
                      result: Optional[Dict] = None, error: Optional[str] = None):
    """更新任务状态"""
    task_storage[task_id] = {
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "message": message,
        "result": result,
        "error": error,
        "updated_at": datetime.now().isoformat()
    }

@router.get("/test", summary="Test Route")
async def test_route():
    """测试路由连接"""
    return {"message": "论点一致性检查服务运行正常", "timestamp": datetime.now().isoformat()}

@router.post("/v1/pipeline-async", summary="异步流水线处理")
async def async_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """
    异步执行完整的论点一致性检查流水线
    
    返回任务ID，可通过 /v1/task/{task_id} 查询进度
    """
    task_id = create_task_id()
    
    # 初始化任务状态
    update_task_status(task_id, "pending", 0.0, "任务已创建，等待处理")
    
    # 添加后台任务
    background_tasks.add_task(process_pipeline_async, task_id, request)
    
    return {"task_id": task_id, "status": "pending", "message": "任务已提交，请使用task_id查询进度"}

async def process_pipeline_async(task_id: str, request: PipelineRequest):
    """异步处理流水线任务 - 调用主应用API"""
    try:
        update_task_status(task_id, "running", 10.0, "转发请求到主应用")
        
        # 调用主应用的异步API
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                "http://localhost:8001/api/v1/pipeline-async",
                json=request.dict()
            )
            
            if response.status_code != 200:
                raise Exception(f"主应用API调用失败: {response.status_code} - {response.text}")
            
            main_app_result = response.json()
            main_task_id = main_app_result.get("task_id")
            
            if not main_task_id:
                raise Exception("主应用未返回task_id")
            
            update_task_status(task_id, "running", 30.0, "等待主应用处理完成")
            
            # 轮询主应用的任务状态
            max_attempts = 60  # 最多等待5分钟
            attempt = 0
            
            while attempt < max_attempts:
                await asyncio.sleep(5)  # 每5秒检查一次
                attempt += 1
                
                status_response = await client.get(f"http://localhost:8001/api/v1/task/{main_task_id}")
                
                if status_response.status_code != 200:
                    continue
                
                task_info = status_response.json()
                status = task_info.get("status")
                progress = task_info.get("progress", 0)
                message = task_info.get("message", "处理中")
                
                # 更新router的任务状态，进度从30%开始到90%
                router_progress = 30.0 + (progress * 0.6)
                update_task_status(task_id, "running", router_progress, f"主应用: {message}")
                
                if status == "completed":
                    # 主应用处理完成，获取结果
                    result = task_info.get("result", {})
                    
                    update_task_status(task_id, "completed", 100.0, "处理完成", result)
                    return
                    
                elif status == "failed":
                    error_msg = task_info.get("error", "主应用处理失败")
                    raise Exception(f"主应用处理失败: {error_msg}")
            
            # 超时
            raise Exception("主应用处理超时")
        
    except Exception as e:
        logger.error(f"异步任务处理失败: {e}")
        update_task_status(task_id, "failed", 0.0, "处理失败", error=str(e))

@router.get("/v1/task/{task_id}",
         response_model=TaskStatusResponse,
         summary="查询任务状态")
async def get_task_status(task_id: str):
    """
    查询异步任务的处理状态和结果
    
    - **task_id**: 任务ID
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = task_storage[task_id]
    
    return TaskStatusResponse(
        task_id=task_info["task_id"],
        status=task_info["status"],
        progress=task_info["progress"],
        message=task_info["message"],
        result=task_info.get("result"),
        error=task_info.get("error"),
        updated_at=task_info["updated_at"]
    )

@router.get("/v1/result/{task_id}", summary="获取纯净的章节结果")
async def get_unified_sections(task_id: str):
    """
    获取纯净的章节结果（unified_sections格式）
    
    - **task_id**: 任务ID
    
    返回处理后的章节结果，格式为嵌套的章节结构
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = task_storage[task_id]
    
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    # 从结果中获取unified_sections文件路径并读取内容
    result = task_info.get("result", {})
    if isinstance(result, dict) and "unified_sections_file" in result:
        unified_sections_file_relative = result["unified_sections_file"]
        base_dir = Path(__file__).parent.parent.parent
        unified_sections_file = base_dir / unified_sections_file_relative.lstrip('./')
        
        try:
            import json
            with open(unified_sections_file, 'r', encoding='utf-8') as f:
                unified_sections_data = json.load(f)
            return unified_sections_data
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="unified_sections文件不存在")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="未找到unified_sections文件")

@router.get("/v1/optimized/{task_id}", summary="获取优化后的markdown文档")
async def get_optimized_markdown(task_id: str):
    """
    获取优化后的完整markdown文档
    
    - **task_id**: 任务ID
    
    返回优化后的markdown文档内容
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = task_storage[task_id]
    
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    # 从结果中获取优化后的markdown文件路径
    result = task_info.get("result", {})
    if isinstance(result, dict) and "optimized_content_file" in result:
        markdown_file_relative = result["optimized_content_file"]
        base_dir = Path(__file__).parent.parent.parent
        markdown_file = base_dir / markdown_file_relative.lstrip('./')
        
        try:
            with open(markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"content": content, "file_path": str(markdown_file)}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="优化后的markdown文件不存在")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="未找到优化后的markdown文件")

@router.get("/v1/download/{task_id}", summary="下载处理结果")
async def download_result(task_id: str):
    """
    下载任务处理结果文档
    
    - **task_id**: 任务ID
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = task_storage[task_id]
    
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    result = task_info.get("result", {})
    return {
        "task_id": task_id,
        "status": "completed",
        "files": result,
        "download_info": "请使用 /v1/result/{task_id} 和 /v1/optimized/{task_id} 获取具体文件内容"
    }
