"""
论点一致性检查服务路由
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from typing import Optional, Dict, Any
import os
import sys
import uuid
import time
import logging
from datetime import datetime
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 添加thesis_agent_app到Python路径
thesis_agent_path = Path("/Users/wangzijian/Desktop/gauz/keyan/review_agent_save/thesis_agent_app")
if thesis_agent_path.exists():
    sys.path.insert(0, str(thesis_agent_path))
    logger.info(f"已添加路径到sys.path: {thesis_agent_path}")
else:
    logger.error(f"thesis_agent_app路径不存在: {thesis_agent_path}")

# 导入thesis_agent_app模块
main_task_storage = {}
main_update_task_status = None
main_process_pipeline_async = None
PipelineRequest = None
TaskStatusResponse = None

try:
    # 尝试导入主应用模块
    import main as thesis_main
    
    # 获取需要的对象
    main_task_storage = getattr(thesis_main, 'task_storage', {})
    main_update_task_status = getattr(thesis_main, 'update_task_status', None)
    main_process_pipeline_async = getattr(thesis_main, 'process_pipeline_async', None)
    PipelineRequest = getattr(thesis_main, 'PipelineRequest', None)
    TaskStatusResponse = getattr(thesis_main, 'TaskStatusResponse', None)
    
    logger.info("成功导入thesis_agent_app模块")
    logger.info(f"task_storage类型: {type(main_task_storage)}")
    logger.info(f"update_task_status: {main_update_task_status is not None}")
    logger.info(f"process_pipeline_async: {main_process_pipeline_async is not None}")
    
except ImportError as e:
    logger.error(f"无法导入thesis_agent_app模块: {e}")
    
# 如果导入失败，定义基础模型作为后备
if not PipelineRequest:
    from pydantic import BaseModel
    
    class PipelineRequest(BaseModel):
        document_content: str
        document_title: Optional[str] = None
        auto_correct: bool = True

if not TaskStatusResponse:
    from pydantic import BaseModel
    
    class TaskStatusResponse(BaseModel):
        task_id: str
        status: str
        progress: float
        message: str
        result: Optional[Dict[str, Any]] = None
        error: Optional[str] = None
        updated_at: str

# 创建路由器
router = APIRouter(tags=["论点一致性检查"])

# 任务存储 - 使用主应用的task_storage
task_storage = main_task_storage if main_task_storage else {}

def create_task_id() -> str:
    """生成唯一任务ID"""
    return str(uuid.uuid4())

def update_task_status(task_id: str, status: str, progress: float, message: str, 
                      result: Optional[Dict] = None, error: Optional[str] = None):
    """更新任务状态"""
    if main_update_task_status:
        # 使用主应用的update_task_status函数
        main_update_task_status(task_id, status, progress, message, result, error)
    else:
        # 后备方案
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
    """异步处理流水线任务 - 直接调用主应用函数"""
    try:
        if main_process_pipeline_async:
            # 直接调用主应用的处理函数
            await main_process_pipeline_async(task_id, request)
        else:
            # 后备方案：简单的错误处理
            update_task_status(task_id, "failed", 0.0, "主应用模块未正确加载", error="thesis_agent_app模块导入失败")
        
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
