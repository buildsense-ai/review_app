#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redundancy Agent 路由器
处理文档冗余内容优化的API端点
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
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import asyncio

# 添加 redundancy_agent_app 到Python路径
redundancy_agent_path = Path(__file__).parent.parent.parent / "redundancy_agent_app"
sys.path.insert(0, str(redundancy_agent_path))

# 添加shared到Python路径
shared_path = Path(__file__).parent.parent.parent / "shared"
sys.path.insert(0, str(shared_path))

try:
    from run_redundancy_agent import RedundancyAgent
except ImportError as e:
    logging.error(f"无法导入redundancy_agent_app模块: {e}")
    RedundancyAgent = None

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
router = APIRouter(prefix="", tags=["冗余内容优化"])

logger = logging.getLogger(__name__)

# 异步处理函数
async def process_redundancy_async(task_id: str, request: DocumentOptimizeRequest):
    """异步处理冗余优化任务"""
    try:
        update_task_status(task_id, "running", 10.0, "开始冗余分析")
        
        if not RedundancyAgent:
            raise Exception("RedundancyAgent未正确导入")
        
        # 创建agent实例
        agent = RedundancyAgent()
        
        update_task_status(task_id, "running", 30.0, "执行冗余分析")
        
        # 处理文档
        unified_sections = agent.process(request.document_content, request.document_title)
        
        update_task_status(task_id, "running", 90.0, "生成输出文件")
        
        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        # 使用统一的输出目录
        results_dir = Path(__file__).parent.parent / "outputs" / "redundancy_agent"
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        unified_sections_file = results_dir / f"redundancy_unified_{task_id}_{timestamp}.json"
        
        # 保存unified_sections JSON文件
        with open(unified_sections_file, 'w', encoding='utf-8') as f:
            json.dump(unified_sections, f, ensure_ascii=False, indent=2)
        
        # 构建结果
        sections_count = sum(len(sections) for sections in unified_sections.values())
        result = {
            "unified_sections_file": str(unified_sections_file),
            "sections_count": sections_count,
            "service_type": "redundancy_agent",
            "message": f"已生成文件: {unified_sections_file.name}",
            "timestamp": timestamp
        }
        
        update_task_status(task_id, "completed", 100.0, "冗余优化完成", result=result)
        
    except Exception as e:
        logger.error(f"冗余优化任务失败: {e}")
        import traceback
        traceback.print_exc()
        update_task_status(task_id, "failed", 0.0, "处理失败", error=str(e))

@router.get("/test", summary="Test Route")
async def test_route():
    return {"message": "Redundancy Agent 运行正常", "timestamp": datetime.now().isoformat()}

@router.post("/v1/pipeline-async", summary="异步冗余优化处理")
async def async_pipeline(request: DocumentOptimizeRequest, background_tasks: BackgroundTasks):
    """
    异步执行冗余优化流水线
    
    返回任务ID，可通过 /v1/task/{task_id} 查询进度
    """
    task_id = create_task_id()
    
    # 初始化任务状态
    task_manager.create_task(task_id)
    update_task_status(task_id, "pending", 0.0, "任务已创建，等待处理")
    
    # 添加后台任务
    background_tasks.add_task(process_redundancy_async, task_id, request)
    
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

@router.get("/v1/result/{task_id}", summary="获取冗余优化结果")
async def get_unified_sections(task_id: str):
    """
    获取冗余优化结果（unified_sections格式）
    
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

@router.get("/v1/result-flat/{task_id}", summary="获取冗余优化结果（扁平结构）")
async def get_flat_result(task_id: str):
    """
    获取冗余优化结果（扁平结构，供前端使用）
    
    - **task_id**: 任务ID
    
    返回扁平化的chapters数组，格式为：
    {
        "chapters": [
            {
                "original_text": "原始文本",
                "edit_text": "优化后文本",
                "comment": "优化说明"
            }
        ]
    }
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
            
            # 转换为扁平结构
            chapters = []
            for part_name, sections in unified_sections_data.items():
                for section_name, content in sections.items():
                    if isinstance(content, dict) and content.get("status") == "modified":
                        chapters.append({
                            "original_text": content.get("original_content", ""),
                            "edit_text": content.get("regenerated_content", ""),
                            "comment": content.get("suggestion", "")
                        })
            
            return {"chapters": chapters}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="unified_sections文件不存在")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="未找到unified_sections文件")

@router.post("/v1/pipeline-stream", summary="流式冗余优化处理")
async def pipeline_stream(request: DocumentOptimizeRequest):
    """
    流式执行冗余优化流水线，实时推送处理进度
    
    返回 SSE (Server-Sent Events) 流，前端可实时接收进度更新
    """
    
    def format_sse_message(event: str, data: dict) -> str:
        """格式化 SSE 消息"""
        json_data = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {json_data}\n\n"
    
    async def generate():
        """生成 SSE 事件流"""
        try:
            # 阶段1：任务提交 (0%)
            yield format_sse_message("progress", {
                "status": "submitting",
                "message": "任务已提交",
                "progress": 0
            })
            await asyncio.sleep(0.1)
            
            # 阶段2：开始分析 (10%)
            yield format_sse_message("progress", {
                "status": "analyzing",
                "message": "开始AI分析文档冗余",
                "progress": 10
            })
            
            if not RedundancyAgent:
                raise Exception("RedundancyAgent未正确导入")
            
            # 创建agent实例
            agent = RedundancyAgent()
            
            # 执行冗余分析 (在独立线程中运行同步代码)
            analysis_result = await asyncio.to_thread(
                agent.analyzer.analyze_redundancy,
                request.document_content,
                request.document_title
            )
            
            modification_instructions = analysis_result.get('modification_instructions', [])
            total_chapters = len(modification_instructions)
            
            # 阶段3：分析完成 (30%)
            if total_chapters == 0:
                yield format_sse_message("progress", {
                    "status": "completed",
                    "message": "文档无冗余问题",
                    "progress": 100
                })
                yield format_sse_message("result", {"chapters": []})
                yield format_sse_message("end", {"status": "completed"})
                return
            
            yield format_sse_message("progress", {
                "status": "analyzed",
                "message": f"分析完成，发现 {total_chapters} 个需要优化的章节",
                "progress": 30
            })
            await asyncio.sleep(0.2)
            
            # 阶段4：解析文档章节
            parsed_sections = await asyncio.to_thread(
                agent.modifier.parse_document_sections,
                request.document_content
            )
            
            # 阶段5：逐章节处理 (40-90%)
            modified_sections = {}
            
            for i, instruction in enumerate(modification_instructions, 1):
                subtitle = instruction.get('subtitle')
                suggestion = instruction.get('suggestion', '')
                
                # 计算进度 (40% -> 90%)
                progress = 40 + int((i / total_chapters) * 50)
                
                yield format_sse_message("progress", {
                    "status": "processing",
                    "message": f"正在优化章节 {i}/{total_chapters}: {subtitle}",
                    "progress": progress,
                    "current_chapter": i,
                    "total_chapters": total_chapters
                })
                
                if subtitle and suggestion:
                    section_info = agent.modifier.find_section_in_parsed(parsed_sections, subtitle)
                    if section_info:
                        h1_title, section_key, original_content = section_info
                        
                        # 在独立线程中执行章节修改
                        regenerated_content = await asyncio.to_thread(
                            agent.modifier.modify_section,
                            original_content,
                            section_key,
                            suggestion
                        )
                        
                        # 保存修改结果
                        full_key = f"{h1_title} > {section_key}"
                        modified_sections[full_key] = {
                            'h1_title': h1_title,
                            'section_key': section_key,
                            'original_content': original_content,
                            'regenerated_content': regenerated_content,
                            'suggestion': suggestion,
                            'word_count': len(regenerated_content),
                            'status': 'modified'
                        }
            
            # 阶段6：构建输出 (95%)
            yield format_sse_message("progress", {
                "status": "finalizing",
                "message": "生成最终结果",
                "progress": 95
            })
            
            # 构建 unified_sections 格式
            unified_sections = {}
            for h1_title in parsed_sections.keys():
                unified_sections[h1_title] = {}
            
            for full_key, section_data in modified_sections.items():
                h1_title = section_data['h1_title']
                section_key = section_data['section_key']
                
                if h1_title not in unified_sections:
                    unified_sections[h1_title] = {}
                
                unified_sections[h1_title][section_key] = {
                    "original_content": section_data['original_content'],
                    "suggestion": section_data['suggestion'],
                    "regenerated_content": section_data['regenerated_content'],
                    "word_count": section_data['word_count'],
                    "status": section_data['status']
                }
            
            # 转换为扁平结构
            chapters = []
            for part_name, sections in unified_sections.items():
                for section_name, content in sections.items():
                    if isinstance(content, dict) and content.get("status") == "modified":
                        chapters.append({
                            "original_text": content.get("original_content", ""),
                            "edit_text": content.get("regenerated_content", ""),
                            "comment": content.get("suggestion", "")
                        })
            
            # 阶段7：返回最终结果 (100%)
            yield format_sse_message("result", {
                "chapters": chapters,
                "summary": f"优化完成，共修改 {len(chapters)} 个章节"
            })
            
            yield format_sse_message("end", {
                "status": "completed",
                "progress": 100
            })
            
        except Exception as e:
            logger.error(f"流式处理失败: {e}")
            import traceback
            traceback.print_exc()
            yield format_sse_message("error", {
                "error": str(e),
                "message": "处理失败"
            })
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no"
        }
    )

