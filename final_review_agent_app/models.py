#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI数据模型定义
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentOptimizeRequest(BaseModel):
    """文档优化请求模型"""
    content: str = Field(..., description="Markdown文档内容")
    filename: Optional[str] = Field(None, description="文件名（可选）")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="优化选项")
    
    class Config:
        schema_extra = {
            "example": {
                "content": "# 示例文档\n\n## 项目背景\n\n这是一个示例项目...",
                "filename": "example.md",
                "options": {
                    "enable_table_optimization": True,
                    "preserve_structure": True
                }
            }
        }


class TaskResponse(BaseModel):
    """任务响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="响应消息")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        schema_extra = {
            "example": {
                "task_id": "task_123456789",
                "status": "processing",
                "message": "文档优化任务已开始处理",
                "created_at": "2024-01-01T12:00:00"
            }
        }


class TaskStatusResponse(BaseModel):
    """任务状态查询响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    progress: Optional[float] = Field(None, description="进度百分比 (0-100)")
    message: str = Field(..., description="状态消息")
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始处理时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息（如果失败）")
    
    class Config:
        schema_extra = {
            "example": {
                "task_id": "task_123456789",
                "status": "processing",
                "progress": 65.5,
                "message": "正在进行文档内容优化...",
                "created_at": "2024-01-01T12:00:00",
                "started_at": "2024-01-01T12:00:05",
                "completed_at": None,
                "error_message": None
            }
        }


class SectionResult(BaseModel):
    """统一的章节结果格式"""
    section_title: str = Field(..., description="章节标题")
    original_content: str = Field(..., description="原始内容")
    suggestion: str = Field(..., description="修改建议或分析结果")
    regenerated_content: str = Field(..., description="修改后的内容")
    word_count: int = Field(..., description="字数统计")
    status: str = Field(default="success", description="处理状态")


class OptimizationResult(BaseModel):
    """优化结果模型"""
    original_content: str = Field(..., description="原始文档内容")
    optimized_content: str = Field(..., description="优化后的文档内容")
    analysis_summary: str = Field(..., description="分析摘要")
    sections_modified: int = Field(..., description="修改的章节数")
    tables_optimized: int = Field(..., description="优化的表格数")
    modifications_applied: List[Dict[str, Any]] = Field(default_factory=list, description="应用的修改列表")
    table_optimizations_applied: List[Dict[str, Any]] = Field(default_factory=list, description="应用的表格优化列表")
    processing_time: float = Field(..., description="处理时间（秒）")
    # 新增统一格式的JSON输出
    unified_sections: Dict[str, SectionResult] = Field(default_factory=dict, description="统一格式的章节结果")
    
    class Config:
        schema_extra = {
            "example": {
                "original_content": "# 原始文档内容...",
                "optimized_content": "# 优化后的文档内容...",
                "analysis_summary": "发现3个需要优化的章节，2个表格优化机会",
                "sections_modified": 3,
                "tables_optimized": 2,
                "modifications_applied": [
                    {
                        "subtitle": "项目背景",
                        "suggestion": "优化重复表述",
                        "status": "completed"
                    }
                ],
                "table_optimizations_applied": [
                    {
                        "section_title": "人员配置",
                        "table_opportunity": "转换为表格格式",
                        "status": "completed"
                    }
                ],
                "processing_time": 45.2
            }
        }


class TaskResultResponse(BaseModel):
    """任务结果响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    result: Optional[OptimizationResult] = Field(None, description="优化结果（仅当状态为completed时）")
    error_message: Optional[str] = Field(None, description="错误信息（仅当状态为failed时）")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    class Config:
        schema_extra = {
            "example": {
                "task_id": "task_123456789",
                "status": "completed",
                "result": {
                    "original_content": "# 原始文档...",
                    "optimized_content": "# 优化后文档...",
                    "analysis_summary": "优化摘要",
                    "sections_modified": 3,
                    "tables_optimized": 2,
                    "processing_time": 45.2
                },
                "error_message": None,
                "created_at": "2024-01-01T12:00:00",
                "completed_at": "2024-01-01T12:00:45"
            }
        }


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    timestamp: datetime = Field(..., description="检查时间")
    version: str = Field(..., description="版本号")
    api_available: bool = Field(..., description="API是否可用")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-01T12:00:00",
                "version": "1.0.0",
                "api_available": True
            }
        }


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    detail: Optional[str] = Field(None, description="详细错误信息")
    timestamp: datetime = Field(..., description="错误发生时间")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "输入数据验证失败",
                "detail": "content字段不能为空",
                "timestamp": "2024-01-01T12:00:00"
            }
        }
