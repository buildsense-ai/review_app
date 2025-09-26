#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论点一致性检查系统 FastAPI 应用

提供RESTful API接口，支持：
1. 论点提取
2. 一致性检查  
3. 文档修正
4. 完整流水线处理
"""

import os
import json
import logging
import tempfile
import uuid
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 导入系统核心模块
from thesis_extractor import ThesisExtractor, ThesisStatement
from thesis_consistency_checker import ThesisConsistencyChecker, ConsistencyAnalysis, ConsistencyIssue
from document_regenerator import ThesisDocumentRegenerator
from config import config

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('thesis_api.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="论点一致性检查系统 API",
    description="智能论文论点一致性检查和修正系统，确保文档逻辑一致性",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建临时文件目录
TEMP_DIR = Path("./temp_files")
TEMP_DIR.mkdir(exist_ok=True)

# 全局任务存储（生产环境建议使用Redis等）
task_storage = {}


# ==================== 数据模型定义 ====================

class SectionResult(BaseModel):
    """统一的章节结果格式"""
    section_title: str = Field(..., description="章节标题")
    original_content: str = Field(..., description="原始内容")
    suggestion: str = Field(..., description="修改建议或分析结果")
    regenerated_content: str = Field(..., description="修改后的内容")
    word_count: int = Field(..., description="字数统计")
    status: str = Field(default="success", description="处理状态")


# ==================== 辅助函数 ====================

def generate_unified_sections(original_content: str, corrected_content: str, 
                            consistency_issues: List[ConsistencyIssue],
                            regenerated_sections: Dict[str, Dict[str, Any]] = None) -> Dict[str, SectionResult]:
    """生成统一格式的章节结果"""
    unified_sections = {}
    
    # 解析原始内容的章节
    original_sections = parse_sections(original_content)
    
    # 如果有regenerated_sections，优先使用它们的详细信息
    if regenerated_sections:
        # 处理所有有一致性问题的章节
        for issue in consistency_issues:
            section_title = issue.section_title
            
            # 从regenerated_sections获取详细信息
            if section_title in regenerated_sections:
                section_data = regenerated_sections[section_title]
                
                # 获取原始内容（从原始文档中提取）
                original_section_content = original_sections.get(section_title, "")
                
                # 获取修正后的内容
                regenerated_content = section_data.get('content', original_section_content)
                
                # 获取建议
                suggestion = issue.suggestion or "论点一致性分析完成"
                
                # 计算字数
                word_count = section_data.get('word_count', len(regenerated_content.replace(' ', '').replace('\n', '')))
                
                unified_sections[section_title] = SectionResult(
                    section_title=section_title,
                    original_content=original_section_content,
                    suggestion=suggestion,
                    regenerated_content=regenerated_content,
                    word_count=word_count,
                    status="success"
                )
        
        # 处理没有一致性问题的章节（保持原样）
        for section_title, original_section_content in original_sections.items():
            if section_title not in unified_sections:
                # 计算字数
                word_count = len(original_section_content.replace(' ', '').replace('\n', ''))
                
                unified_sections[section_title] = SectionResult(
                    section_title=section_title,
                    original_content=original_section_content,
                    suggestion="论点一致性良好，无需修改",
                    regenerated_content=original_section_content,
                    word_count=word_count,
                    status="success"
                )
    else:
        # 如果没有regenerated_sections，使用原来的逻辑
        # 解析修正后内容的章节
        corrected_sections = parse_sections(corrected_content) if corrected_content else original_sections
        
        # 为每个章节生成结果
        for section_title, original_section_content in original_sections.items():
            corrected_section_content = corrected_sections.get(section_title, original_section_content)
            
            # 查找该章节的一致性问题和建议
            suggestion = ""
            for issue in consistency_issues:
                if issue.section_title == section_title:
                    if suggestion:
                        suggestion += "; " + issue.suggestion
                    else:
                        suggestion = issue.suggestion
            
            if not suggestion:
                suggestion = "论点一致性良好，无需修改"
            
            # 计算字数
            word_count = len(corrected_section_content.replace(' ', '').replace('\n', ''))
            
            unified_sections[section_title] = SectionResult(
                section_title=section_title,
                original_content=original_section_content,
                suggestion=suggestion,
                regenerated_content=corrected_section_content,
                word_count=word_count,
                status="success"
            )
    
    return unified_sections


def parse_sections(content: str) -> Dict[str, str]:
    """解析Markdown内容的章节"""
    sections = {}
    
    # 使用正则表达式匹配二级标题
    section_pattern = r'^## (.+?)$'
    lines = content.split('\n')
    
    current_section = None
    current_content = []
    
    for line in lines:
        match = re.match(section_pattern, line)
        if match:
            # 保存前一个章节
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            
            # 开始新章节
            current_section = match.group(1).strip()
            current_content = [line]  # 包含标题行
        else:
            if current_section:
                current_content.append(line)
    
    # 保存最后一个章节
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections


# ==================== 数据模型定义 ====================

class ThesisStatementModel(BaseModel):
    """核心论点数据模型"""
    main_thesis: str = Field(..., description="核心论点")
    supporting_arguments: List[str] = Field(default_factory=list, description="支撑论据")
    key_concepts: List[str] = Field(default_factory=list, description="关键概念")


class ConsistencyIssueModel(BaseModel):
    """一致性问题数据模型"""
    section_title: str = Field(..., description="章节标题")
    issue_type: str = Field(..., description="问题类型")
    description: str = Field(..., description="问题描述")
    evidence: str = Field(..., description="支撑证据")
    suggestion: str = Field(..., description="修改建议")


class SectionResult(BaseModel):
    """统一的章节结果格式"""
    section_title: str = Field(..., description="章节标题")
    original_content: str = Field(..., description="原始内容")
    suggestion: str = Field(..., description="修改建议或分析结果")
    regenerated_content: str = Field(..., description="修改后的内容")
    word_count: int = Field(..., description="字数统计")
    status: str = Field(default="success", description="处理状态")


class ConsistencyAnalysisModel(BaseModel):
    """一致性分析结果数据模型"""
    overall_consistency_score: float = Field(..., description="整体一致性评分")
    total_issues_found: int = Field(..., description="发现问题总数")
    consistency_issues: List[ConsistencyIssueModel] = Field(default_factory=list, description="一致性问题列表")
    well_aligned_sections: List[str] = Field(default_factory=list, description="一致性良好的章节")
    improvement_suggestions: List[str] = Field(default_factory=list, description="改进建议")


class DocumentAnalysisRequest(BaseModel):
    """文档分析请求模型"""
    document_content: str = Field(..., description="文档内容")
    document_title: Optional[str] = Field(None, description="文档标题")


class ThesisExtractionResponse(BaseModel):
    """论点提取响应模型"""
    status: str = Field(..., description="处理状态")
    document_title: str = Field(..., description="文档标题")
    thesis_statement: ThesisStatementModel = Field(..., description="提取的论点")
    processing_time: float = Field(..., description="处理时间（秒）")


class ConsistencyCheckRequest(BaseModel):
    """一致性检查请求模型"""
    document_content: str = Field(..., description="文档内容")
    thesis_statement: ThesisStatementModel = Field(..., description="核心论点")
    document_title: Optional[str] = Field(None, description="文档标题")


class ConsistencyCheckResponse(BaseModel):
    """一致性检查响应模型"""
    status: str = Field(..., description="处理状态")
    document_title: str = Field(..., description="文档标题")
    thesis_statement: ThesisStatementModel = Field(..., description="核心论点")
    consistency_analysis: ConsistencyAnalysisModel = Field(..., description="一致性分析结果")
    processing_time: float = Field(..., description="处理时间（秒）")


class DocumentCorrectionRequest(BaseModel):
    """文档修正请求模型"""
    document_content: str = Field(..., description="原始文档内容")
    thesis_statement: ThesisStatementModel = Field(..., description="核心论点")
    consistency_issues: List[ConsistencyIssueModel] = Field(..., description="需要修正的一致性问题")
    document_title: Optional[str] = Field(None, description="文档标题")


class DocumentCorrectionResponse(BaseModel):
    """文档修正响应模型"""
    status: str = Field(..., description="处理状态")
    document_title: str = Field(..., description="文档标题")
    corrected_document: str = Field(..., description="修正后的完整文档")
    sections_corrected: int = Field(..., description="修正的章节数量")
    processing_time: float = Field(..., description="处理时间（秒）")


class PipelineRequest(BaseModel):
    """完整流水线请求模型"""
    document_content: str = Field(..., description="文档内容")
    document_title: Optional[str] = Field(None, description="文档标题")
    auto_correct: bool = Field(True, description="是否自动修正问题")


class PipelineResponse(BaseModel):
    """完整流水线响应模型"""
    status: str = Field(..., description="处理状态")
    document_title: str = Field(..., description="文档标题")
    thesis_statement: ThesisStatementModel = Field(..., description="提取的论点")
    consistency_analysis: ConsistencyAnalysisModel = Field(..., description="一致性分析结果")
    corrected_document: Optional[str] = Field(None, description="修正后的文档（如果启用自动修正）")
    sections_corrected: int = Field(0, description="修正的章节数量")
    total_processing_time: float = Field(..., description="总处理时间（秒）")
    # 新增统一格式的JSON输出
    unified_sections: Dict[str, SectionResult] = Field(default_factory=dict, description="统一格式的章节结果")


class TaskStatusResponse(BaseModel):
    """任务状态响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    progress: float = Field(..., description="进度百分比")
    message: str = Field(..., description="状态消息")
    result: Optional[Dict[str, Any]] = Field(None, description="任务结果")
    error: Optional[str] = Field(None, description="错误信息")


# ==================== 辅助函数 ====================

def convert_thesis_statement(thesis: ThesisStatement) -> ThesisStatementModel:
    """转换论点数据结构"""
    return ThesisStatementModel(
        main_thesis=thesis.main_thesis,
        supporting_arguments=thesis.supporting_arguments,
        key_concepts=thesis.key_concepts
    )


def convert_consistency_analysis(analysis: ConsistencyAnalysis) -> ConsistencyAnalysisModel:
    """转换一致性分析数据结构"""
    issues = [
        ConsistencyIssueModel(
            section_title=issue.section_title,
            issue_type=issue.issue_type,
            description=issue.description,
            evidence=issue.evidence,
            suggestion=issue.suggestion
        )
        for issue in analysis.consistency_issues
    ]
    
    return ConsistencyAnalysisModel(
        overall_consistency_score=analysis.overall_consistency_score,
        total_issues_found=analysis.total_issues_found,
        consistency_issues=issues,
        well_aligned_sections=analysis.well_aligned_sections,
        improvement_suggestions=analysis.improvement_suggestions
    )


def save_temp_file(content: str, suffix: str = ".md") -> str:
    """保存临时文件"""
    temp_file = tempfile.NamedTemporaryFile(
        mode='w', 
        suffix=suffix, 
        delete=False, 
        dir=TEMP_DIR,
        encoding='utf-8'
    )
    temp_file.write(content)
    temp_file.close()
    return temp_file.name


def create_task_id() -> str:
    """创建任务ID"""
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


# ==================== API 端点 ====================

@app.get("/", summary="系统信息")
async def root():
    """获取系统基本信息"""
    return {
        "name": "论点一致性检查系统 API",
        "version": "1.0.0",
        "description": "智能论文论点一致性检查和修正系统",
        "endpoints": {
            "thesis_extraction": "/api/v1/extract-thesis",
            "consistency_check": "/api/v1/check-consistency", 
            "document_correction": "/api/v1/correct-document",
            "full_pipeline": "/api/v1/pipeline",
            "file_upload": "/api/v1/upload",
            "task_status": "/api/v1/task/{task_id}"
        }
    }


@app.get("/health", summary="健康检查")
async def health_check():
    """系统健康检查"""
    try:
        # 检查配置
        errors = config.validate_config()
        if errors:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "errors": errors,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "config": {
                "model": config.openrouter_model,
                "output_dir": config.default_output_dir,
                "auto_correct": config.default_auto_correct
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@app.post("/api/v1/extract-thesis", 
          response_model=ThesisExtractionResponse,
          summary="提取核心论点")
async def extract_thesis(request: DocumentAnalysisRequest):
    """
    从文档中提取核心论点
    
    - **document_content**: 文档内容（Markdown格式）
    - **document_title**: 文档标题（可选）
    """
    try:
        start_time = datetime.now()
        
        # 初始化提取器
        extractor = ThesisExtractor()
        
        # 设置默认标题
        document_title = request.document_title or "未命名文档"
        
        # 提取论点
        thesis_statement = extractor.extract_thesis_from_document(
            request.document_content, 
            document_title
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return ThesisExtractionResponse(
            status="success",
            document_title=document_title,
            thesis_statement=convert_thesis_statement(thesis_statement),
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"论点提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"论点提取失败: {str(e)}")


@app.post("/api/v1/check-consistency",
          response_model=ConsistencyCheckResponse,
          summary="检查论点一致性")
async def check_consistency(request: ConsistencyCheckRequest):
    """
    检查文档与核心论点的一致性
    
    - **document_content**: 文档内容
    - **thesis_statement**: 核心论点
    - **document_title**: 文档标题（可选）
    """
    try:
        start_time = datetime.now()
        
        # 初始化检查器
        checker = ThesisConsistencyChecker()
        
        # 转换论点数据结构
        thesis = ThesisStatement(
            main_thesis=request.thesis_statement.main_thesis,
            supporting_arguments=request.thesis_statement.supporting_arguments,
            key_concepts=request.thesis_statement.key_concepts
        )
        
        # 设置默认标题
        document_title = request.document_title or "未命名文档"
        
        # 执行一致性检查
        consistency_analysis = checker.check_consistency(
            request.document_content,
            thesis,
            document_title
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return ConsistencyCheckResponse(
            status="success",
            document_title=document_title,
            thesis_statement=request.thesis_statement,
            consistency_analysis=convert_consistency_analysis(consistency_analysis),
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"一致性检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"一致性检查失败: {str(e)}")


@app.post("/api/v1/correct-document",
          response_model=DocumentCorrectionResponse,
          summary="修正文档")
async def correct_document(request: DocumentCorrectionRequest):
    """
    基于一致性问题修正文档
    
    - **document_content**: 原始文档内容
    - **thesis_statement**: 核心论点
    - **consistency_issues**: 需要修正的一致性问题
    - **document_title**: 文档标题（可选）
    """
    try:
        start_time = datetime.now()
        
        # 初始化修正器
        regenerator = ThesisDocumentRegenerator()
        
        # 设置默认标题
        document_title = request.document_title or "未命名文档"
        
        # 转换数据结构
        thesis_data = {
            "main_thesis": request.thesis_statement.main_thesis,
            "supporting_arguments": request.thesis_statement.supporting_arguments,
            "key_concepts": request.thesis_statement.key_concepts
        }
        
        # 准备章节修正数据
        sections_data = []
        for issue in request.consistency_issues:
            # 提取章节内容
            original_content = regenerator.extract_section_content(
                request.document_content, 
                issue.section_title
            )
            
            if original_content:
                issue_dict = {
                    "section_title": issue.section_title,
                    "issue_type": issue.issue_type,
                    "description": issue.description,
                    "evidence": issue.evidence,
                    "suggestion": issue.suggestion
                }
                
                sections_data.append((
                    issue.section_title,
                    original_content,
                    issue_dict,
                    thesis_data
                ))
        
        # 并行修正章节
        regenerated_sections = regenerator.regenerate_sections_parallel(sections_data)
        
        # 生成完整文档
        complete_document = regenerator._generate_complete_document(
            request.document_content,
            {},  # 没有JSON数据
            regenerated_sections,
            thesis_data
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return DocumentCorrectionResponse(
            status="success",
            document_title=document_title,
            corrected_document=complete_document,
            sections_corrected=len(regenerated_sections),
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"文档修正失败: {e}")
        raise HTTPException(status_code=500, detail=f"文档修正失败: {str(e)}")


@app.post("/api/v1/pipeline",
          response_model=PipelineResponse,
          summary="完整流水线处理")
async def full_pipeline(request: PipelineRequest):
    """
    执行完整的论点一致性检查流水线
    
    - **document_content**: 文档内容
    - **document_title**: 文档标题（可选）
    - **auto_correct**: 是否自动修正问题
    """
    try:
        start_time = datetime.now()
        
        # 设置默认标题
        document_title = request.document_title or "未命名文档"
        
        # 第一步：提取论点
        extractor = ThesisExtractor()
        thesis_statement = extractor.extract_thesis_from_document(
            request.document_content,
            document_title
        )
        
        # 第二步：检查一致性
        checker = ThesisConsistencyChecker()
        consistency_analysis = checker.check_consistency(
            request.document_content,
            thesis_statement,
            document_title
        )
        
        # 第三步：修正文档（如果需要）
        corrected_document = None
        sections_corrected = 0
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
                    issue_dict = {
                        "section_title": issue.section_title,
                        "issue_type": issue.issue_type,
                        "description": issue.description,
                        "evidence": issue.evidence,
                        "suggestion": issue.suggestion
                    }
                    
                    sections_data.append((
                        issue.section_title,
                        original_content,
                        issue_dict,
                        thesis_data
                    ))
            
            # 修正章节
            regenerated_sections = regenerator.regenerate_sections_parallel(sections_data)
            sections_corrected = len(regenerated_sections)
            
            # 生成完整文档
            corrected_document = regenerator._generate_complete_document(
                request.document_content,
                {},
                regenerated_sections,
                thesis_data
            )
        
        total_processing_time = (datetime.now() - start_time).total_seconds()
        
        # 生成统一格式的章节结果
        unified_sections = generate_unified_sections(
            request.document_content,
            corrected_document or request.document_content,
            consistency_analysis.consistency_issues,
            regenerated_sections
        )
        
        return PipelineResponse(
            status="success",
            document_title=document_title,
            thesis_statement=convert_thesis_statement(thesis_statement),
            consistency_analysis=convert_consistency_analysis(consistency_analysis),
            corrected_document=corrected_document,
            sections_corrected=sections_corrected,
            total_processing_time=total_processing_time,
            unified_sections=unified_sections
        )
        
    except Exception as e:
        logger.error(f"流水线处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"流水线处理失败: {str(e)}")


@app.post("/api/v1/upload", summary="文件上传处理")
async def upload_file(
    file: UploadFile = File(...),
    document_title: Optional[str] = Form(None),
    auto_correct: bool = Form(True)
):
    """
    上传文件并执行完整流水线处理
    
    - **file**: 上传的文档文件（支持.md, .txt格式）
    - **document_title**: 文档标题（可选）
    - **auto_correct**: 是否自动修正问题
    """
    try:
        # 检查文件类型
        if not file.filename.endswith(('.md', '.txt')):
            raise HTTPException(
                status_code=400, 
                detail="仅支持 .md 和 .txt 格式的文件"
            )
        
        # 读取文件内容
        content = await file.read()
        document_content = content.decode('utf-8')
        
        # 设置文档标题
        if not document_title:
            document_title = Path(file.filename).stem
        
        # 执行完整流水线
        pipeline_request = PipelineRequest(
            document_content=document_content,
            document_title=document_title,
            auto_correct=auto_correct
        )
        
        return await full_pipeline(pipeline_request)
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，请确保文件为UTF-8编码")
    except Exception as e:
        logger.error(f"文件上传处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


@app.post("/api/v1/pipeline-async", summary="异步流水线处理")
async def async_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """
    异步执行完整的论点一致性检查流水线
    
    返回任务ID，可通过 /api/v1/task/{task_id} 查询进度
    """
    task_id = create_task_id()
    
    # 初始化任务状态
    update_task_status(task_id, "pending", 0.0, "任务已创建，等待处理")
    
    # 添加后台任务
    background_tasks.add_task(process_pipeline_async, task_id, request)
    
    return {"task_id": task_id, "status": "pending", "message": "任务已提交，请使用task_id查询进度"}


async def process_pipeline_async(task_id: str, request: PipelineRequest):
    """异步处理流水线任务"""
    try:
        update_task_status(task_id, "running", 10.0, "开始提取论点")
        
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
        sections_corrected = 0
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
                    issue_dict = {
                        "section_title": issue.section_title,
                        "issue_type": issue.issue_type,
                        "description": issue.description,
                        "evidence": issue.evidence,
                        "suggestion": issue.suggestion
                    }
                    
                    sections_data.append((
                        issue.section_title,
                        original_content,
                        issue_dict,
                        thesis_data
                    ))
            
            # 修正章节
            regenerated_sections = regenerator.regenerate_sections_parallel(sections_data)
            sections_corrected = len(regenerated_sections)
            
            # 生成完整文档
            corrected_document = regenerator._generate_complete_document(
                request.document_content,
                {},
                regenerated_sections,
                thesis_data
            )
        
        # 生成统一格式的章节结果
        unified_sections = generate_unified_sections(
            request.document_content,
            corrected_document or request.document_content,
            consistency_analysis.consistency_issues,
            regenerated_sections
        )
        
        logger.info(f"生成的unified_sections数量: {len(unified_sections)}")
        if unified_sections:
            logger.info(f"unified_sections的键: {list(unified_sections.keys())}")
        
        # 构建结果
        try:
            unified_sections_dict = {k: v.dict() for k, v in unified_sections.items()} if unified_sections else {}
            logger.info(f"转换后的unified_sections_dict数量: {len(unified_sections_dict)}")
        except Exception as e:
            logger.error(f"转换unified_sections时出错: {e}")
            unified_sections_dict = {}
        
        result = {
            "status": "success",
            "document_title": document_title,
            "thesis_statement": convert_thesis_statement(thesis_statement).dict(),
            "consistency_analysis": convert_consistency_analysis(consistency_analysis).dict(),
            "corrected_document": corrected_document,
            "sections_corrected": sections_corrected,
            "unified_sections": unified_sections_dict
        }
        
        update_task_status(task_id, "completed", 100.0, "流水线处理完成", result)
        
    except Exception as e:
        logger.error(f"异步任务处理失败: {e}")
        update_task_status(task_id, "failed", 0.0, "处理失败", error=str(e))


@app.get("/api/v1/task/{task_id}",
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
        result=task_info["result"],
        error=task_info["error"]
    )


@app.get("/api/v1/download/{task_id}", summary="下载处理结果")
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
    
    result = task_info["result"]
    if not result or not result.get("corrected_document"):
        raise HTTPException(status_code=404, detail="没有可下载的修正文档")
    
    # 保存临时文件
    temp_file = save_temp_file(result["corrected_document"], ".md")
    
    return FileResponse(
        temp_file,
        media_type="text/markdown",
        filename=f"corrected_{result['document_title']}.md"
    )


if __name__ == "__main__":
    import uvicorn
    
    # 打印配置信息
    config.print_config_summary()
    
    # 启动服务
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
