#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论点一致性检查服务路由器
基于thesis_agent_app的FastAPI路由器实现
"""

import os
import sys
import json
import logging
import tempfile
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# 添加thesis_agent_app到Python路径
thesis_agent_path = Path(__file__).parent.parent.parent / "thesis_agent_app"
sys.path.insert(0, str(thesis_agent_path))

try:
    from thesis_extractor import ThesisExtractor, ThesisStatement
    from thesis_consistency_checker import ThesisConsistencyChecker, ConsistencyAnalysis, ConsistencyIssue
    from document_regenerator import ThesisDocumentRegenerator
    from config import config
except ImportError as e:
    logging.error(f"无法导入thesis_agent_app模块: {e}")
    # 定义基础模型作为后备
    class ThesisStatement:
        def __init__(self, main_thesis="", supporting_arguments=None, key_concepts=None):
            self.main_thesis = main_thesis
            self.supporting_arguments = supporting_arguments or []
            self.key_concepts = key_concepts or []
    
    class ConsistencyIssue:
        def __init__(self, section_title="", issue_type="", description="", evidence="", suggestion=""):
            self.section_title = section_title
            self.issue_type = issue_type
            self.description = description
            self.evidence = evidence
            self.suggestion = suggestion
    
    class ConsistencyAnalysis:
        def __init__(self):
            self.overall_consistency_score = 0.0
            self.total_issues_found = 0
            self.consistency_issues = []
            self.well_aligned_sections = []
            self.improvement_suggestions = []
    
    ThesisExtractor = None
    ThesisConsistencyChecker = None
    ThesisDocumentRegenerator = None
    config = None

# 创建路由器
router = APIRouter(prefix="", tags=["论点一致性检查"])

logger = logging.getLogger(__name__)

# 创建临时文件目录
TEMP_DIR = Path("./temp_files")
TEMP_DIR.mkdir(exist_ok=True)

# 全局任务存储
task_storage = {}

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

class SectionResult(BaseModel):
    """统一的章节结果格式"""
    section_title: str = Field(..., description="章节标题")
    original_content: str = Field(..., description="原始内容")
    suggestion: str = Field(..., description="修改建议或分析结果")
    regenerated_content: str = Field(..., description="修改后的内容")
    status: str = Field(default="success", description="处理状态")

class ThesisAnalysisResult(BaseModel):
    """论点分析结果模型"""
    original_content: str = Field(..., description="原始文档内容")
    corrected_document: Optional[str] = Field(None, description="修正后的文档内容")
    thesis_statement: ThesisStatementModel = Field(..., description="提取的论点")
    consistency_analysis: ConsistencyAnalysisModel = Field(..., description="一致性分析结果")
    sections_corrected: int = Field(0, description="修正的章节数量")
    processing_time: float = Field(..., description="处理时间（秒）")
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

def extract_document_sections(document_content: str) -> Dict[str, Dict[str, str]]:
    """提取文档中的章节内容，按一级标题和二级标题嵌套组织"""
    sections = {}
    lines = document_content.split('\n')
    current_h1 = None
    current_h2 = None
    current_content = []
    
    for line in lines:
        # 检查是否是一级标题
        if line.strip().startswith('# ') and not line.strip().startswith('## '):
            # 保存前一个二级章节
            if current_h1 and current_h2 and current_content:
                if current_h1 not in sections:
                    sections[current_h1] = {}
                sections[current_h1][current_h2] = '\n'.join(current_content).strip()
            
            # 开始新的一级标题
            current_h1 = line.strip().replace('# ', '').strip()
            current_h2 = None
            current_content = []
            
        # 检查是否是二级标题
        elif line.strip().startswith('## '):
            # 保存前一个二级章节
            if current_h1 and current_h2 and current_content:
                if current_h1 not in sections:
                    sections[current_h1] = {}
                sections[current_h1][current_h2] = '\n'.join(current_content).strip()
            
            # 开始新的二级标题
            current_h2 = line.strip().replace('## ', '').strip()
            current_content = []
            
        elif current_h2:
            # 添加到当前二级章节内容
            current_content.append(line)
    
    # 保存最后一个章节
    if current_h1 and current_h2 and current_content:
        if current_h1 not in sections:
            sections[current_h1] = {}
        sections[current_h1][current_h2] = '\n'.join(current_content).strip()
    
    return sections

def _generate_markdown_from_sections(unified_sections: Dict[str, Any], original_document: str) -> str:
    """
    从统一章节结果生成完整的markdown文档
    
    Args:
        unified_sections: 统一章节结果（嵌套结构）
        original_document: 原始文档内容
        
    Returns:
        str: 生成的markdown文档
    """
    lines = []
    
    # 提取文档开头的非章节内容（如标题、摘要等）
    doc_lines = original_document.split('\n')
    header_lines = []
    
    for line in doc_lines:
        if line.strip().startswith('# ') and not line.strip().startswith('## '):
            break
        header_lines.append(line)
    
    # 添加文档头部
    if header_lines:
        lines.extend(header_lines)
        lines.append('')
    
    # 按原始文档中的章节顺序生成内容
    original_sections = extract_document_sections(original_document)
    
    for h1_title, h2_sections in original_sections.items():
        if h1_title in unified_sections:
            # 添加一级标题
            lines.append(f'# {h1_title}')
            lines.append('')
            
            # 遍历二级标题
            for h2_title in h2_sections.keys():
                if h2_title in unified_sections[h1_title]:
                    section_data = unified_sections[h1_title][h2_title]
                    # 使用regenerated_content（如果有修改）或original_content
                    content = section_data.get('regenerated_content', section_data.get('original_content', ''))
                    
                    # 添加二级标题
                    lines.append(f'## {h2_title}')
                    lines.append('')
                    
                    # 添加内容
                    if content:
                        lines.append(content)
                        lines.append('')
    
    return '\n'.join(lines).strip()

# ==================== API 端点 ====================

@router.get("/test")
async def test_route():
    """测试路由是否工作"""
    return {"message": "论点一致性检查服务路由工作正常!"}

# @router.get("/", summary="服务信息")
# async def service_info():
#     """获取论点一致性检查服务信息"""
#     return {
#         "service": "论点一致性检查服务",
#         "description": "智能论文论点一致性检查和修正系统，确保文档逻辑一致性",
#         "version": "1.0.0",
#         "endpoints": {
#             "thesis_extraction": "/v1/extract-thesis",
#             "consistency_check": "/v1/check-consistency", 
#             "document_correction": "/v1/correct-document",
#             "full_pipeline": "/v1/pipeline",
#             "file_upload": "/v1/upload",
#             "task_status": "/v1/task/{task_id}"
#         }
#     }

# @router.get("/health", summary="健康检查")
# async def health_check():
#     """系统健康检查"""
#     try:
#         # 检查配置
#         if config:
#             errors = config.validate_config()
#             if errors:
#                 return JSONResponse(
#                     status_code=503,
#                     content={
#                         "status": "unhealthy",
#                         "errors": errors,
#                         "timestamp": datetime.now().isoformat()
#                     }
#                 )
        
#         api_available = bool(os.getenv("OPENROUTER_API_KEY"))
        
#         return {
#             "status": "healthy" if api_available else "degraded",
#             "timestamp": datetime.now().isoformat(),
#             "api_available": api_available,
#             "config": {
#                 "model": getattr(config, 'openrouter_model', 'N/A') if config else 'N/A',
#                 "output_dir": getattr(config, 'default_output_dir', './test_results') if config else './test_results',
#                 "auto_correct": getattr(config, 'default_auto_correct', True) if config else True
#             }
#         }
#     except Exception as e:
#         return JSONResponse(
#             status_code=503,
#             content={
#                 "status": "unhealthy",
#                 "error": str(e),
#                 "timestamp": datetime.now().isoformat()
#             }
#         )

@router.post("/v1/extract-thesis", 
          response_model=ThesisExtractionResponse,
          summary="提取核心论点")
async def extract_thesis(request: DocumentAnalysisRequest):
    """
    从文档中提取核心论点
    
    - **document_content**: 文档内容（Markdown格式）
    - **document_title**: 文档标题（可选）
    """
    if not ThesisExtractor:
        raise HTTPException(status_code=503, detail="论点提取器未初始化")
    
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

@router.post("/v1/check-consistency",
          response_model=ConsistencyCheckResponse,
          summary="检查论点一致性")
async def check_consistency(request: ConsistencyCheckRequest):
    """
    检查文档与核心论点的一致性
    
    - **document_content**: 文档内容
    - **thesis_statement**: 核心论点
    - **document_title**: 文档标题（可选）
    """
    if not ThesisConsistencyChecker:
        raise HTTPException(status_code=503, detail="一致性检查器未初始化")
    
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

@router.post("/v1/correct-document",
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
    if not ThesisDocumentRegenerator:
        raise HTTPException(status_code=503, detail="文档修正器未初始化")
    
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

@router.post("/v1/pipeline",
          response_model=PipelineResponse,
          summary="完整流水线处理")
async def full_pipeline(request: PipelineRequest):
    """
    执行完整的论点一致性检查流水线
    
    - **document_content**: 文档内容
    - **document_title**: 文档标题（可选）
    - **auto_correct**: 是否自动修正问题
    """
    if not all([ThesisExtractor, ThesisConsistencyChecker]):
        raise HTTPException(status_code=503, detail="系统组件未完全初始化")
    
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
        
        if request.auto_correct and consistency_analysis.total_issues_found > 0 and ThesisDocumentRegenerator:
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
        
        return PipelineResponse(
            status="success",
            document_title=document_title,
            thesis_statement=convert_thesis_statement(thesis_statement),
            consistency_analysis=convert_consistency_analysis(consistency_analysis),
            corrected_document=corrected_document,
            sections_corrected=sections_corrected,
            total_processing_time=total_processing_time
        )
        
    except Exception as e:
        logger.error(f"流水线处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"流水线处理失败: {str(e)}")

@router.post("/v1/upload", summary="文件上传处理")
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
    """异步处理流水线任务"""
    start_time = time.time()
    try:
        update_task_status(task_id, "running", 10.0, "开始提取论点")
        
        # 设置默认标题
        document_title = request.document_title or "未命名文档"
        
        # 第一步：提取论点
        if ThesisExtractor:
            extractor = ThesisExtractor()
            thesis_statement = extractor.extract_thesis_from_document(
                request.document_content,
                document_title
            )
        else:
            raise Exception("论点提取器未初始化")
        
        update_task_status(task_id, "running", 40.0, "论点提取完成，开始一致性检查")
        
        # 第二步：检查一致性
        if ThesisConsistencyChecker:
            checker = ThesisConsistencyChecker()
            consistency_analysis = checker.check_consistency(
                request.document_content,
                thesis_statement,
                document_title
            )
        else:
            raise Exception("一致性检查器未初始化")
        
        update_task_status(task_id, "running", 70.0, "一致性检查完成，开始文档修正")
        
        # 调试日志：输出一致性检查结果
        logger.info(f"一致性检查结果: 发现 {consistency_analysis.total_issues_found} 个问题")
        for issue in consistency_analysis.consistency_issues:
            logger.info(f"问题: {issue.section_title} - {issue.issue_type} - {issue.description}")
        
        # 第三步：修正文档（如果需要）
        corrected_document = None
        sections_corrected = 0
        regenerated_sections = {}  # 初始化为空字典
        
        if request.auto_correct and consistency_analysis.total_issues_found > 0 and ThesisDocumentRegenerator:
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
        
        # 构建统一格式的章节结果
        unified_sections = {}
        processing_time = time.time() - start_time
        
        # 提取文档章节（嵌套结构）
        sections = extract_document_sections(request.document_content)
        
        # 将问题和重生成结果按章节标题索引，方便查找
        issues_map = {issue.section_title: issue for issue in consistency_analysis.consistency_issues}
        
        # 遍历一级标题和二级标题
        for h1_title, h2_sections in sections.items():
            unified_sections[h1_title] = {}
            
            for h2_title, original_content in h2_sections.items():
                status = "success"
                suggestion = "未找到对应的分析结果"
                regenerated_content = original_content

                # 检查该章节是否有问题
                if h2_title in issues_map:
                    issue = issues_map[h2_title]
                    suggestion = f"一致性问题: {issue.description}. 建议: {issue.suggestion}"
                    status = "identified" # 默认为已识别问题

                # 检查该章节是否有重写的内容
                if request.auto_correct and h2_title in regenerated_sections:
                    regen_data = regenerated_sections[h2_title]
                    if regen_data.get('status') == 'success':
                        regenerated_content = regen_data.get('regenerated_content', original_content)
                        status = "corrected"

                unified_sections[h1_title][h2_title] = {
                    "section_title": h2_title,
                    "original_content": original_content,
                    "suggestion": suggestion,
                    "regenerated_content": regenerated_content,
                    "word_count": len(regenerated_content),
                    "status": status
                }

        # 参考final_review_agent的逻辑，生成两个输出文件
        update_task_status(task_id, "running", 90.0, "保存结果文件...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 确保使用绝对路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        results_dir = os.path.join(base_dir, "test_results")
        os.makedirs(results_dir, exist_ok=True)
        
        # 不在router中重复保存文件，文件已在主应用中生成
        logger.info("文件生成由主应用处理，router不重复生成")
        
        # Router不再生成文件，直接使用主应用的结果
        # 主应用已经生成了文件并返回了路径信息
        final_result = unified_sections  # unified_sections实际上是主应用返回的result
        
        # 更新任务状态为完成，返回文件路径信息
        update_task_status(task_id, "completed", 100.0, "流水线处理完成", final_result)
        
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
        result=task_info["result"],
        error=task_info["error"]
    )

@router.get("/v1/result/{task_id}", summary="获取纯净的章节结果")
async def get_unified_sections(task_id: str):
    """
    获取任务的统一章节结果，直接返回章节内容，不包含任务元数据
    
    - **task_id**: 任务ID
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = task_storage[task_id]
    
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    if not task_info.get("result"):
        raise HTTPException(status_code=404, detail="结果不存在")
    
    # 从结果中读取unified_sections文件
    result = task_info["result"]
    if isinstance(result, dict) and "unified_sections_file" in result:
        # 读取实际的JSON文件内容
        unified_sections_file = result["unified_sections_file"]
        try:
            import json
            with open(unified_sections_file, 'r', encoding='utf-8') as f:
                unified_sections_data = json.load(f)
            return unified_sections_data
        except Exception as e:
            logger.error(f"读取unified_sections文件失败: {e}")
            raise HTTPException(status_code=500, detail=f"读取结果文件失败: {str(e)}")
    else:
        # 兼容旧格式
        return result

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
        markdown_file_path = result["optimized_content_file"]
        try:
            with open(markdown_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"content": content, "file_path": markdown_file_path}
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
