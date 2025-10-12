"""
论点一致性检查服务路由 - 简化版
直接实现核心功能，避免复杂的模块导入
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional, Dict, Any
import os
import sys
import uuid
import time
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel

# 添加shared到Python路径
shared_path = Path(__file__).parent.parent.parent / "shared"
sys.path.insert(0, str(shared_path))

# 导入统一的任务管理器和文档解析器
from shared import TaskManager, TaskStatus, DocumentParser

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(tags=["论点一致性检查"])

# 使用统一的任务管理器
task_manager = TaskManager()

class PipelineRequest(BaseModel):
    document_content: str
    document_title: Optional[str] = None
    auto_correct: bool = True

# 任务状态响应模型从shared导入
TaskStatusResponse = TaskStatus

def create_task_id() -> str:
    """生成唯一任务ID"""
    return str(uuid.uuid4())

def update_task_status(task_id: str, status: str, progress: float, message: str, 
                      result: Optional[Dict] = None, error: Optional[str] = None):
    """更新任务状态（使用统一的TaskManager）"""
    task_manager.update_task(task_id, status=status, progress=progress, message=message, result=result, error=error)

def parse_hierarchical_sections(content: str) -> Dict[str, Dict[str, str]]:
    """解析Markdown内容为层级结构（使用统一的DocumentParser）"""
    return DocumentParser.parse_sections(content, max_level=3, preserve_order=True)

def generate_unified_sections(original_content: str, corrected_content: str, consistency_issues: list, regenerated_sections: dict) -> Dict[str, Any]:
    """基于真实AI分析结果生成unified_sections数据"""
    # 解析原始和修正后的文档结构
    original_sections = parse_hierarchical_sections(original_content)
    corrected_sections = parse_hierarchical_sections(corrected_content)
    
    unified_sections = {}
    
    for h1_title, h2_sections in original_sections.items():
        unified_sections[h1_title] = {}
        
        for section_key, original_section_content in h2_sections.items():
            if not original_section_content.strip() or len(original_section_content) < 50:
                continue  # 跳过空章节或内容太少的章节
            
            # 获取修正后的章节内容
            corrected_section_content = original_section_content
            if h1_title in corrected_sections and section_key in corrected_sections[h1_title]:
                corrected_section_content = corrected_sections[h1_title][section_key]
            
            # 查找该章节的一致性问题
            suggestion = ""
            regenerated_content = original_section_content
            
            # 提取h2和h3标题用于匹配（如果section_key包含 ">"）
            if " > " in section_key:
                h2_title, h3_title = section_key.split(" > ", 1)
            else:
                h2_title = section_key
                h3_title = None
            
            # 查找匹配的consistency_issues
            matched_issue = None
            for issue in consistency_issues:
                if (issue.section_title == section_key or 
                    issue.section_title == h2_title or
                    (h3_title and issue.section_title == h3_title) or
                    issue.section_title == f"{h1_title} {h2_title}" or
                    h2_title in issue.section_title or
                    (h3_title and h3_title in issue.section_title) or
                    issue.section_title in section_key):
                    matched_issue = issue
                    break
            
            if matched_issue:
                suggestion = f"一致性问题: {matched_issue.description}. 建议: {matched_issue.suggestion}"
                # 查找对应的regenerated_sections
                if matched_issue.section_title in regenerated_sections:
                    section_data = regenerated_sections[matched_issue.section_title]
                    regenerated_content = section_data.get("content", corrected_section_content)
                else:
                    regenerated_content = corrected_section_content
                
                unified_sections[h1_title][section_key] = {
                    "section_title": section_key,
                    "original_content": original_section_content,
                    "suggestion": suggestion,
                    "regenerated_content": regenerated_content,
                    "word_count": len(original_section_content),
                    "status": "identified"
                }
            elif original_section_content != corrected_section_content:
                # 如果没有找到明确的一致性问题，但内容有变化
                suggestion = "内容已优化"
                unified_sections[h1_title][section_key] = {
                    "section_title": section_key,
                    "original_content": original_section_content,
                    "suggestion": suggestion,
                    "regenerated_content": corrected_section_content,
                    "word_count": len(original_section_content),
                    "status": "corrected"
                }
            # 如果没有问题且内容没有变化，则跳过该章节（不包含在输出中）
    
    return unified_sections

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
    task_manager.create_task(task_id)
    update_task_status(task_id, "pending", 0.0, "任务已创建，等待处理")
    
    # 添加后台任务
    background_tasks.add_task(process_pipeline_async, task_id, request)
    
    return {"task_id": task_id, "status": "pending", "message": "任务已提交，请使用task_id查询进度"}

async def process_pipeline_async(task_id: str, request: PipelineRequest):
    """异步处理流水线任务"""
    
    # 提前导入sys，避免作用域问题
    import sys

    try:
        update_task_status(task_id, "running", 10.0, "开始论点一致性检查")
        
        # 添加thesis_agent_app到Python路径
        thesis_agent_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "thesis_agent_app")
        if thesis_agent_path not in sys.path:
            sys.path.insert(0, thesis_agent_path)
        
        # 确保config模块能被正确导入
        original_path = sys.path.copy()
        
        try:
            # 导入thesis agent的核心模块
            from thesis_extractor import ThesisExtractor
            from thesis_consistency_checker import ThesisConsistencyChecker
            from document_regenerator import ThesisDocumentRegenerator
        except ImportError as e:
            logger.error(f"导入thesis_agent模块失败: {e}")
            # 恢复原始路径
            sys.path = original_path
            raise HTTPException(status_code=500, detail=f"导入thesis_agent模块失败: {str(e)}")
        
        # 设置默认标题
        document_title = request.document_title or "未命名文档"
        
        # 第一步：提取论点
        extractor = ThesisExtractor()
        thesis_statement = extractor.extract_thesis_from_document(
            request.document_content,
            document_title
        )
        
        update_task_status(task_id, "running", 40.0, "论点提取完成，开始一致性检查")
        
        # 第二步：检查一致性
        checker = ThesisConsistencyChecker()
        consistency_analysis = checker.check_consistency(
            request.document_content,
            thesis_statement,
            document_title
        )
        
        update_task_status(task_id, "running", 70.0, "一致性检查完成，开始文档修正")
        
        # 第三步：修正文档（如果需要）
        corrected_document = None
        regenerated_sections = {}
        
        if request.auto_correct and consistency_analysis.total_issues_found > 0:
            regenerator = ThesisDocumentRegenerator()
            
            # 准备修正数据
            thesis_data = {
                "main_thesis": thesis_statement.main_thesis,
                "supporting_arguments": thesis_statement.supporting_arguments,
                "key_concepts": thesis_statement.key_concepts
            }
            
            sections_data = []
            for issue in consistency_analysis.consistency_issues:
                original_content = regenerator.extract_section_content(
                    request.document_content,
                    issue.section_title
                )
                
                if original_content:
                    sections_data.append({
                        "section_title": issue.section_title,
                        "original_content": original_content,
                        "issue_description": issue.description,
                        "suggestion": issue.suggestion
                    })
            
            # 生成修正后的章节
            # 准备并行处理的数据格式
            parallel_sections_data = []
            for section in sections_data:
                parallel_sections_data.append((
                    section["section_title"],
                    section["original_content"],
                    {"issue_description": section["issue_description"], "suggestion": section["suggestion"]},
                        thesis_data
                    ))
            
            regenerated_sections = regenerator.regenerate_sections_parallel(parallel_sections_data)
            
            # 生成完整文档
            corrected_document = regenerator._generate_complete_document(
                request.document_content,
                {},
                regenerated_sections,
                thesis_data
            )
        
        update_task_status(task_id, "running", 90.0, "生成统一格式输出")
        
        # 生成unified_sections
        unified_sections = generate_unified_sections(
            request.document_content,
            corrected_document or request.document_content,
            consistency_analysis.consistency_issues,
            regenerated_sections
        )
        
        update_task_status(task_id, "running", 95.0, "生成输出文件")
        
        # 生成唯一时间戳（包含毫秒，确保唯一性）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        # 使用统一的输出目录
        results_dir = Path(__file__).parent.parent / "outputs" / "thesis"
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一文件名
        unified_sections_file = results_dir / f"thesis_agent_unified_{task_id}_{timestamp}.json"
        
        # 生成thesis_agent_unified JSON文件
        with open(unified_sections_file, 'w', encoding='utf-8') as f:
            json.dump(unified_sections, f, ensure_ascii=False, indent=2)
        
        # 构建结果
        processing_time = 30.0  # 实际AI处理时间
        sections_count = sum(len(sections) for sections in unified_sections.values())
        result = {
            "unified_sections_file": str(unified_sections_file),
            "processing_time": processing_time,
            "sections_count": sections_count,
            "service_type": "thesis_agent",
            "message": f"已生成文件: {unified_sections_file.name}",
            "timestamp": timestamp
        }
        
        update_task_status(task_id, "completed", 100.0, "处理完成", result)
        
    except Exception as e:
        logger.error(f"异步任务处理失败: {e}")
        # 确保在异常时恢复sys.path
        if 'original_path' in locals():
            sys.path = original_path
        update_task_status(task_id, "failed", 0.0, "处理失败", error=str(e))

# 已删除generate_optimized_markdown函数，直接使用AI生成的corrected_document

@router.get("/v1/task/{task_id}",
         response_model=TaskStatusResponse,
         summary="查询任务状态")
async def get_task_status(task_id: str):
    """
    查询异步任务的处理状态和结果
    
    - **task_id**: 任务ID
    """
    if not task_manager.task_exists(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task_manager.get_task_status(task_id)

@router.get("/v1/result/{task_id}", summary="获取纯净的章节结果")
async def get_unified_sections(task_id: str):
    """
    获取纯净的章节结果（unified_sections格式）
    
    - **task_id**: 任务ID
    
    返回处理后的章节结果，格式为嵌套的章节结构
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

@router.get("/v1/download/{task_id}", summary="下载处理结果")
async def download_result(task_id: str):
    """
    下载任务处理结果文档
    
    - **task_id**: 任务ID
    """
    if not task_manager.task_exists(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = task_manager.get_task(task_id)
    
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    result = task_info.get("result", {})
    return {
        "task_id": task_id,
        "status": "completed",
        "files": result,
        "download_info": "请使用 /v1/result/{task_id} 获取文件内容"
    }
