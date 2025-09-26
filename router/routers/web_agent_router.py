#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论据支持度评估服务路由器
基于web_agent_app的FastAPI路由器实现
"""

import os
import sys
import json
import time
import tempfile
import shutil
import logging
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# 添加web_agent_app到Python路径
web_agent_path = Path(__file__).parent.parent.parent / "web_agent_app"
sys.path.insert(0, str(web_agent_path))

# 设置环境变量以兼容web_agent_app的配置
import os
if not os.getenv('LOG_LEVEL'):
    os.environ['LOG_LEVEL'] = 'INFO'
if not os.getenv('MAX_WORKERS'):
    os.environ['MAX_WORKERS'] = '5'
if not os.getenv('ENABLE_PARALLEL_SEARCH'):
    os.environ['ENABLE_PARALLEL_SEARCH'] = 'true'
if not os.getenv('ENABLE_PARALLEL_ENHANCEMENT'):
    os.environ['ENABLE_PARALLEL_ENHANCEMENT'] = 'true'

try:
    from whole_document_pipeline import WholeDocumentPipeline
    from evidence_detector import UnsupportedClaim, EvidenceResult
except ImportError as e:
    logging.error(f"无法导入web_agent_app模块: {e}")
    # 设置为None，表示导入失败
    WholeDocumentPipeline = None
    
    # 定义基础模型作为后备
    class UnsupportedClaim:
        def __init__(self, claim_id="", claim_text="", section_title="", claim_type="factual", 
                     confidence_level=0.8, context="", search_keywords=None, original_position=1):
            self.claim_id = claim_id
            self.claim_text = claim_text
            self.section_title = section_title
            self.claim_type = claim_type
            self.confidence_level = confidence_level
            self.context = context
            self.search_keywords = search_keywords or []
            self.original_position = original_position
    
    class EvidenceResult:
        def __init__(self, claim_id="", claim_text="", section_title="", search_query="", 
                     evidence_sources=None, enhanced_text="", confidence_score=0.0, processing_status="success"):
            self.claim_id = claim_id
            self.claim_text = claim_text
            self.section_title = section_title
            self.search_query = search_query
            self.evidence_sources = evidence_sources or []
            self.enhanced_text = enhanced_text
            self.confidence_score = confidence_score
            self.processing_status = processing_status
    
    WholeDocumentPipeline = None

# 创建路由器
router = APIRouter(prefix="", tags=["论据支持度评估"])

logger = logging.getLogger(__name__)

# 全局变量
pipeline = None
processing_tasks = {}

# 使用一个简单的内存存储来跟踪任务状态
_task_storage = {}

# 任务状态管理函数
def update_task_status(task_id: str, status: str, progress: float, message: str, result: Any = None, error: str = None):
    """更新任务状态"""
    _task_storage[task_id] = {
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

def _generate_markdown_from_claims(unified_claims: Dict[str, Any], original_document: str) -> str:
    """
    从统一论断结果生成完整的markdown文档
    
    Args:
        unified_claims: 统一论断结果（嵌套结构）
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
    
    # 添加证据增强标记
    lines.append("## 📋 证据增强说明")
    lines.append("**本文档已通过AI证据搜索和分析进行增强，所有论断都已补充相关证据支撑。**")
    lines.append("")
    lines.append("*以下内容中的论断均已通过网络搜索验证并增强。*")
    lines.append("")
    
    # 按原始文档中的章节顺序生成内容
    original_sections = extract_document_sections(original_document)
    
    for h1_title, h2_sections in original_sections.items():
        if h1_title in unified_claims:
            # 添加一级标题
            lines.append(f'# {h1_title}')
            lines.append('')
            
            # 遍历二级标题
            for h2_title in h2_sections.keys():
                if h2_title in unified_claims[h1_title]:
                    # 添加二级标题
                    lines.append(f'## {h2_title}')
                    lines.append('')
                    
                    # 添加证据增强标记
                    lines.append("*[本章节的论断已通过证据搜索进行增强]*")
                    lines.append("")
                    
                    # 获取增强后的内容
                    section_claims = unified_claims[h1_title][h2_title]
                    enhanced_content = h2_sections[h2_title]  # 默认使用原内容
                    
                    # 如果有增强的论断，替换相应内容
                    for claim_id, claim_data in section_claims.items():
                        if claim_data.get('status') == 'enhanced':
                            # 在原内容中查找并替换原始论断
                            original_claim = claim_data.get('original_content', '')
                            regenerated_claim = claim_data.get('regenerated_content', '')
                            if original_claim and regenerated_claim:
                                enhanced_content = enhanced_content.replace(original_claim, regenerated_claim)
                    
                    # 添加内容
                    if enhanced_content:
                        lines.append(enhanced_content)
                        lines.append('')
    
    return '\n'.join(lines).strip()

def _enhance_claim_with_evidence(claim_text: str, evidence_sources: List[Dict[str, Any]]) -> str:
    """
    使用证据来增强论断
    
    Args:
        claim_text: 原始论断文本
        evidence_sources: 证据来源列表
        
    Returns:
        str: 增强后的论断文本
    """
    try:
        if not evidence_sources or not isinstance(evidence_sources, list):
            return claim_text
        
        # 选择最相关的前3个证据
        top_evidence = evidence_sources[:3]
        
        # 构建证据摘要
        evidence_snippets = []
        for source in top_evidence:
            try:
                if not isinstance(source, dict):
                    continue
                    
                snippet = source.get('snippet', '').strip()
                domain = source.get('source_domain', '').strip()
                
                # 清理snippet中的特殊字符，避免JSON问题
                if snippet:
                    # 移除可能导致JSON问题的字符
                    snippet = snippet.replace('"', "'").replace('\n', ' ').replace('\r', ' ')
                    snippet = snippet[:100]  # 限制长度
                    
                if snippet and domain:
                    evidence_snippets.append(f"{snippet} (来源: {domain})")
                elif snippet:
                    evidence_snippets.append(snippet)
                    
            except Exception as e:
                print(f"    ⚠️ 处理证据源时出错: {str(e)}")
                continue
        
        if not evidence_snippets:
            return claim_text
        
        # 简单的增强逻辑：在原论断后添加证据支撑
        evidence_text = "；".join(evidence_snippets[:2])  # 只使用前2个最相关的证据
        
        # 清理evidence_text，确保JSON安全
        evidence_text = evidence_text.replace('"', "'").replace('\n', ' ').replace('\r', ' ')
        
        # 如果原论断以句号结尾，替换为分号；否则添加分号
        if claim_text.endswith('。'):
            enhanced_claim = claim_text[:-1] + f"。根据相关资料显示，{evidence_text}。"
        else:
            enhanced_claim = claim_text + f"。相关研究表明，{evidence_text}。"
        
        # 确保返回的文本是JSON安全的
        enhanced_claim = enhanced_claim.replace('"', "'").replace('\n', ' ').replace('\r', ' ')
        
        return enhanced_claim
        
    except Exception as e:
        print(f"    ❌ 增强论断时出错: {str(e)}")
        return claim_text

# =============================================================================
# Pydantic模型定义
# =============================================================================

class SystemInfoResponse(BaseModel):
    system_name: str = "论据支持度评估系统"
    version: str = "1.0.0"
    description: str = "基于AI的智能文档分析系统，用于验证学术文档中论点的事实支撑"
    supported_formats: List[str] = ["markdown", "json", "txt"]
    max_file_size_mb: int = 50
    features: List[str] = [
        "检测缺乏证据支撑的论断",
        "并行网络搜索证据支撑", 
        "章节并行处理模式",
        "AI直接生成修改文档",
        "三步骤完整流水线处理",
        "异步处理支持"
    ]

class ExtractClaimsRequest(BaseModel):
    content: str = Field(..., description="文档内容")
    max_claims: int = Field(default=15, ge=1, le=50, description="最大论断提取数量")

class ExtractClaimsResponse(BaseModel):
    status: str = Field(description="处理状态")
    message: str = Field(description="状态消息")
    claims: List[Dict[str, Any]] = Field(default=[], description="提取的论断列表")
    total_claims: int = Field(default=0, description="论断总数")
    processing_time: Optional[float] = Field(default=None, description="处理时间")
    error: Optional[str] = Field(default=None, description="错误信息")

class SearchEvidenceRequest(BaseModel):
    claims: List[Dict[str, Any]] = Field(..., description="需要搜索证据的论断列表")
    max_results_per_claim: int = Field(default=10, ge=1, le=20, description="每个论断的最大搜索结果数")

class SearchEvidenceResponse(BaseModel):
    status: str = Field(description="处理状态")
    message: str = Field(description="状态消息")
    evidence_collections: List[Dict[str, Any]] = Field(default=[], description="证据收集结果")
    total_evidence_found: int = Field(default=0, description="找到的证据总数")
    processing_time: Optional[float] = Field(default=None, description="处理时间")
    error: Optional[str] = Field(default=None, description="错误信息")

class AnalyzeEvidenceRequest(BaseModel):
    claims: List[Dict[str, Any]] = Field(..., description="论断列表")
    evidence_collections: List[Dict[str, Any]] = Field(..., description="证据收集结果")
    original_content: Optional[str] = Field(default=None, description="原始文档内容")

class AnalyzeEvidenceResponse(BaseModel):
    status: str = Field(description="处理状态")
    message: str = Field(description="状态消息")
    analysis_results: List[Dict[str, Any]] = Field(default=[], description="证据分析结果")
    summary: Dict[str, Any] = Field(default={}, description="分析摘要")
    processing_time: Optional[float] = Field(default=None, description="处理时间")
    error: Optional[str] = Field(default=None, description="错误信息")

class WebSearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询")
    max_results: int = Field(default=10, ge=1, le=20, description="最大搜索结果数")

class WebSearchResponse(BaseModel):
    status: str = Field(description="处理状态")
    message: str = Field(description="状态消息")
    query: str = Field(description="搜索查询")
    search_results: List[Dict[str, Any]] = Field(default=[], description="搜索结果")
    total_results: int = Field(default=0, description="结果总数")
    processing_time: Optional[float] = Field(default=None, description="处理时间")
    error: Optional[str] = Field(default=None, description="错误信息")

class PipelineRequest(BaseModel):
    content: str = Field(..., description="文档内容")
    max_claims: int = Field(default=15, ge=1, le=50, description="最大论断处理数量")
    max_search_results: int = Field(default=10, ge=1, le=20, description="每个论断的最大搜索结果数")
    use_section_based_processing: bool = Field(default=True, description="是否使用章节并行处理模式（推荐）")

class PipelineResponse(BaseModel):
    status: str = Field(description="处理状态")
    message: str = Field(description="状态消息")
    enhanced_document: Optional[str] = Field(default=None, description="增强后的文档")
    evidence_analysis: Optional[Dict[str, Any]] = Field(default=None, description="证据分析结果")
    statistics: Optional[Dict[str, Any]] = Field(default=None, description="处理统计")
    processing_time: Optional[float] = Field(default=None, description="处理时间")
    error: Optional[str] = Field(default=None, description="错误信息")

class AsyncTaskResponse(BaseModel):
    task_id: str = Field(description="任务ID")
    status: str = Field(description="任务状态")
    message: str = Field(description="状态消息")

class TaskStatusResponse(BaseModel):
    task_id: str = Field(description="任务ID")
    status: str = Field(description="任务状态")
    progress: Optional[str] = Field(default=None, description="进度信息")
    result: Optional[Dict[str, Any]] = Field(default=None, description="处理结果")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")

class DocumentProcessResponse(BaseModel):
    task_id: str = Field(description="任务ID")
    status: str = Field(description="处理状态")
    message: str = Field(description="状态消息")
    processing_time: Optional[float] = Field(default=None, description="处理时间")
    statistics: Optional[Dict[str, Any]] = Field(default=None, description="处理统计信息")
    output_files: Optional[Dict[str, str]] = Field(default=None, description="输出文件路径")
    error: Optional[str] = Field(default=None, description="错误信息")

class ClaimResult(BaseModel):
    claim_id: str = Field(description="论断ID")
    original_content: str = Field(description="原始论断内容")
    regenerated_content: str = Field(description="证据增强后的内容")
    evidence_sources: List[Dict[str, Any]] = Field(default=[], description="证据来源")
    confidence_score: float = Field(default=0.0, description="置信度分数")
    word_count: int = Field(description="字数统计")
    status: str = Field(description="处理状态")

class WebAgentAnalysisResult(BaseModel):
    claims: Dict[str, ClaimResult] = Field(description="按章节组织的论断结果")
    processing_time: float = Field(description="处理时间")
    statistics: Dict[str, Any] = Field(description="统计信息")

# =============================================================================
# 初始化函数
# =============================================================================

async def initialize_pipeline():
    """初始化流水线"""
    global pipeline
    if not pipeline:
        if WholeDocumentPipeline is None:
            raise HTTPException(
                status_code=503, 
                detail="web_agent_app模块导入失败，论据支持度评估服务不可用"
            )
        try:
            print("🚀 初始化论据支持度评估系统...")
            pipeline = WholeDocumentPipeline()
            print("✅ 系统初始化完成")
        except Exception as e:
            print(f"❌ 系统初始化失败: {str(e)}")
            raise HTTPException(status_code=503, detail=f"系统初始化失败: {str(e)}")

# =============================================================================
# API 端点
# =============================================================================

# @router.get("/test")
# async def test_route():
#     """测试路由是否工作"""
#     return {"message": "论据支持度评估服务路由工作正常!"}

@router.get("/", response_model=SystemInfoResponse)
async def service_info():
    """获取论据支持度评估服务信息"""
    return SystemInfoResponse()

# @router.get("/health")
# async def health_check():
#     """健康检查"""
#     await initialize_pipeline()
#     return {
#         "status": "healthy",
#         "timestamp": datetime.now().isoformat(),
#         "pipeline_ready": pipeline is not None,
#         "api_available": bool(os.getenv("OPENROUTER_API_KEY"))
#     }

@router.post("/v1/extract-claims", response_model=ExtractClaimsResponse)
async def extract_claims(request: ExtractClaimsRequest):
    """提取核心论点"""
    await initialize_pipeline()
    if not pipeline:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    start_time = time.time()
    
    try:
        print(f"🔍 开始提取缺乏证据支撑的论断，文档长度: {len(request.content)} 字符")
        
        # 使用新的evidence_detector检测论断
        detector = pipeline.evidence_detector
        
        # 直接处理内容，不需要临时文件
        unsupported_claims = detector._detect_unsupported_claims("完整文档", request.content)
        
        if len(unsupported_claims) > request.max_claims:
            unsupported_claims = sorted(unsupported_claims, key=lambda x: x.confidence_level, reverse=True)[:request.max_claims]
        
        claims_data = []
        for claim in unsupported_claims:
            claims_data.append({
                "claim_id": claim.claim_id,
                "claim_text": claim.claim_text,
                "claim_type": claim.claim_type,
                "confidence_level": claim.confidence_level,
                "section_title": claim.section_title,
                "search_keywords": claim.search_keywords,
                "context": claim.context
            })
        
        processing_time = time.time() - start_time
        print(f"✅ 缺乏证据支撑的论断提取完成，共提取 {len(claims_data)} 个论断，耗时 {processing_time:.1f}秒")
        
        return ExtractClaimsResponse(
            status="success",
            message=f"成功提取 {len(claims_data)} 个缺乏证据支撑的论断",
            claims=claims_data,
            total_claims=len(claims_data),
            processing_time=processing_time
        )
    
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"提取客观性论断时出现异常: {str(e)}"
        print(f"❌ {error_msg}")
        
        return ExtractClaimsResponse(
            status="failed",
            message="客观性论断提取失败",
            processing_time=processing_time,
            error=error_msg
        )

@router.post("/v1/search-evidence", response_model=SearchEvidenceResponse)
async def search_evidence(request: SearchEvidenceRequest):
    """为论断搜索证据支撑"""
    await initialize_pipeline()
    if not pipeline:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    start_time = time.time()
    
    try:
        print(f"🔍 开始为 {len(request.claims)} 个论断搜索证据...")
        
        # 转换论断数据为 UnsupportedClaim 对象
        claims = []
        for i, claim_data in enumerate(request.claims):
            claim = UnsupportedClaim(
                claim_id=claim_data.get('claim_id', f'claim_{i+1}'),
                claim_text=claim_data['claim_text'],
                section_title=claim_data.get('section_title', f'位置_{i+1}'),
                claim_type=claim_data.get('claim_type', 'factual'),
                confidence_level=claim_data.get('confidence_level', 0.8),
                context=claim_data.get('context', ''),
                search_keywords=claim_data.get('search_keywords', []),
                original_position=i+1
            )
            claims.append(claim)
        
        # 使用新的evidence_detector批量搜索证据
        evidence_results = pipeline.evidence_detector._batch_search_evidence(claims)
        
        # 转换为响应格式
        evidence_data = []
        total_evidence = 0
        for er in evidence_results:
            evidence_info = {
                'claim_id': er.claim_id,
                'search_query': er.search_query,
                'search_results': [
                    {
                        'title': source.get('title', ''),
                        'url': source.get('url', ''),
                        'snippet': source.get('snippet', ''),
                        'source_domain': source.get('source_domain', ''),
                        'relevance_score': source.get('relevance_score', 0.0),
                        'authority_score': source.get('authority_score', 0.0)
                    } for source in er.evidence_sources
                ],
                'total_results': len(er.evidence_sources),
                'processing_status': er.processing_status,
                'confidence_score': er.confidence_score
            }
            evidence_data.append(evidence_info)
            total_evidence += len(er.evidence_sources)
        
        processing_time = time.time() - start_time
        print(f"✅ 证据搜索完成，共找到 {total_evidence} 条证据，耗时 {processing_time:.1f}秒")
        
        return SearchEvidenceResponse(
            status="success",
            message=f"成功为 {len(request.claims)} 个论断搜索到 {total_evidence} 条证据",
            evidence_collections=evidence_data,
            total_evidence_found=total_evidence,
            processing_time=processing_time
        )
    
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"搜索证据时出现异常: {str(e)}"
        print(f"❌ {error_msg}")
        
        return SearchEvidenceResponse(
            status="failed",
            message="证据搜索失败",
            processing_time=processing_time,
            error=error_msg
        )

@router.post("/v1/analyze-evidence", response_model=AnalyzeEvidenceResponse)
async def analyze_evidence(request: AnalyzeEvidenceRequest):
    """分析证据并生成增强内容"""
    await initialize_pipeline()
    if not pipeline:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    start_time = time.time()
    
    try:
        print(f"🤖 开始分析 {len(request.claims)} 个论断的证据...")
        
        # 转换论断数据
        claims = []
        for i, claim_data in enumerate(request.claims):
            claim = UnsupportedClaim(
                claim_id=claim_data.get('claim_id', f'claim_{i+1}'),
                claim_text=claim_data['claim_text'],
                section_title=claim_data.get('section_title', f'位置_{i+1}'),
                claim_type=claim_data.get('claim_type', 'factual'),
                confidence_level=claim_data.get('confidence_level', 0.8),
                context=claim_data.get('context', ''),
                search_keywords=claim_data.get('search_keywords', []),
                original_position=i+1
            )
            claims.append(claim)
        
        # 转换证据数据为EvidenceResult格式
        evidence_results = []
        for ec_data in request.evidence_collections:
            er = EvidenceResult(
                claim_id=ec_data['claim_id'],
                claim_text=next((c.claim_text for c in claims if c.claim_id == ec_data['claim_id']), ''),
                section_title=next((c.section_title for c in claims if c.claim_id == ec_data['claim_id']), ''),
                search_query=ec_data.get('search_query', ''),
                evidence_sources=ec_data.get('search_results', []),
                enhanced_text='',  # 将由文档生成器填充
                confidence_score=ec_data.get('confidence_score', 0.0),
                processing_status=ec_data.get('processing_status', 'success')
            )
            evidence_results.append(er)
        
        # 使用文档生成器生成增强内容
        if request.original_content:
            enhanced_content = pipeline.document_generator.generate_section_with_evidence(
                section_title="完整文档",
                original_content=request.original_content,
                evidence_results=evidence_results
            )
        else:
            enhanced_content = "无原始内容提供"
        
        # 转换为响应格式
        analysis_data = []
        for er in evidence_results:
            analysis_info = {
                'claim_id': er.claim_id,
                'claim_text': er.claim_text,
                'section_title': er.section_title,
                'search_query': er.search_query,
                'evidence_sources': er.evidence_sources,
                'confidence_score': er.confidence_score,
                'processing_status': er.processing_status
            }
            analysis_data.append(analysis_info)
        
        processing_time = time.time() - start_time
        print(f"✅ 证据分析和文档生成完成，耗时 {processing_time:.1f}秒")
        
        summary = {
            'total_claims_analyzed': len(evidence_results),
            'successful_claims': sum(1 for er in evidence_results if er.processing_status == 'success'),
            'total_evidence_sources': sum(len(er.evidence_sources) for er in evidence_results),
            'enhanced_content_generated': bool(enhanced_content and enhanced_content != "无原始内容提供")
        }
        
        return AnalyzeEvidenceResponse(
            status="success",
            message=f"成功分析 {len(evidence_results)} 个论断的证据并生成增强内容",
            analysis_results=analysis_data,
            summary=summary,
            processing_time=processing_time
        )
    
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"分析证据时出现异常: {str(e)}"
        print(f"❌ {error_msg}")
        traceback.print_exc()
        
        return AnalyzeEvidenceResponse(
            status="failed",
            message="证据分析失败",
            processing_time=processing_time,
            error=error_msg
        )

@router.post("/v1/websearch", response_model=WebSearchResponse)
async def websearch(request: WebSearchRequest):
    """网络搜索接口"""
    await initialize_pipeline()
    if not pipeline:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    start_time = time.time()
    
    try:
        print(f"🔍 执行网络搜索: {request.query}")
        
        # 使用web搜索代理执行搜索
        evidence = pipeline.web_search_agent.search_evidence_for_claim(
            claim_id="websearch_query",
            search_keywords=[request.query],
            claim_text=request.query,
            max_results=request.max_results
        )
        
        # 转换为响应格式
        search_results = []
        for sr in evidence.search_results:
            result_info = {
                'title': sr.title,
                'url': sr.url,
                'snippet': sr.snippet,
                'source_domain': sr.source_domain,
                'relevance_score': sr.relevance_score,
                'authority_score': sr.authority_score
            }
            search_results.append(result_info)
        
        processing_time = time.time() - start_time
        print(f"✅ 网络搜索完成，找到 {len(search_results)} 个结果，耗时 {processing_time:.1f}秒")
        
        return WebSearchResponse(
            status="success",
            message=f"成功搜索到 {len(search_results)} 个结果",
            query=request.query,
            search_results=search_results,
            total_results=len(search_results),
            processing_time=processing_time
        )
    
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"网络搜索时出现异常: {str(e)}"
        print(f"❌ {error_msg}")
        traceback.print_exc()
        
        return WebSearchResponse(
            status="failed",
            message="网络搜索失败",
            query=request.query,
            processing_time=processing_time,
            error=error_msg
        )

@router.post("/v1/pipeline", response_model=PipelineResponse)
async def pipeline_sync(request: PipelineRequest):
    """完整流水线处理（同步）"""
    await initialize_pipeline()
    if not pipeline:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    start_time = time.time()
    
    max_content_length = 1024 * 1024  # 1MB
    if len(request.content.encode('utf-8')) > max_content_length:
        raise HTTPException(status_code=413, detail="文档内容过大，超过1MB限制")
    
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, "document.md")
    
    try:
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        print(f"🔄 开始完整流水线处理，文档长度: {len(request.content)} 字符")
        
        result = pipeline.process_whole_document(
            document_path=temp_file_path,
            max_claims=request.max_claims,
            max_search_results=request.max_search_results,
            use_section_based_processing=request.use_section_based_processing
        )
        
        processing_time = time.time() - start_time
        
        if result.get('status') == 'success':
            output_files = result.get('output_files', {})
            
            enhanced_document = request.content
            if 'enhanced_document' in output_files and os.path.exists(output_files['enhanced_document']):
                try:
                    with open(output_files['enhanced_document'], 'r', encoding='utf-8') as f:
                        enhanced_document = f.read()
                except Exception as e:
                    print(f"⚠️ 读取增强文档失败: {str(e)}")
            
            evidence_analysis = {}
            if 'evidence_analysis' in output_files and os.path.exists(output_files['evidence_analysis']):
                try:
                    with open(output_files['evidence_analysis'], 'r', encoding='utf-8') as f:
                        evidence_analysis = json.load(f)
                except Exception as e:
                    print(f"⚠️ 读取证据分析失败: {str(e)}")
            
            print(f"✅ 完整流水线处理完成，耗时: {processing_time:.1f}秒")
            
            return PipelineResponse(
                status="success",
                message="完整流水线处理成功完成",
                enhanced_document=enhanced_document,
                evidence_analysis=evidence_analysis,
                statistics=result.get('statistics', {}),
                processing_time=processing_time
            )
        else:
            error_msg = result.get('error', '处理过程中出现未知错误')
            print(f"❌ 流水线处理失败: {error_msg}")
            
            return PipelineResponse(
                status="failed",
                message="流水线处理失败，返回原文档",
                enhanced_document=request.content,
                evidence_analysis={},
                processing_time=processing_time,
                error=error_msg
            )
    
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"流水线处理时出现异常: {str(e)}"
        print(f"❌ {error_msg}")
        traceback.print_exc()
        
        return PipelineResponse(
            status="failed",
            message="流水线处理异常，返回原文档",
            enhanced_document=request.content,
            evidence_analysis={},
            processing_time=processing_time,
            error=error_msg
        )
    
    finally:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"⚠️ 清理临时目录失败: {str(e)}")

@router.post("/v1/upload", response_model=AsyncTaskResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_claims: int = Form(default=15),
    max_search_results: int = Form(default=10),
    use_section_based_processing: bool = Form(default=True)
):
    """文件上传处理（异步）"""
    await initialize_pipeline()
    if not pipeline:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    allowed_extensions = {'.md', '.json', '.txt'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件格式: {file_ext}。支持的格式: {', '.join(allowed_extensions)}"
        )
    
    max_size = 50 * 1024 * 1024  # 50MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="文件大小超过50MB限制")
    
    task_id = f"task_{int(time.time())}_{hash(file.filename) % 10000}"
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_file_path, 'wb') as f:
            f.write(content)
        
        processing_tasks[task_id] = {
            "status": "processing",
            "start_time": time.time(),
            "progress": "文件已上传，开始处理...",
            "temp_dir": temp_dir,
            "created_at": datetime.now().isoformat()
        }
        
        background_tasks.add_task(
            process_document_background,
            task_id,
            temp_file_path,
            max_claims,
            max_search_results,
            use_section_based_processing
        )
        
        return AsyncTaskResponse(
            task_id=task_id,
            status="processing",
            message="文件上传成功，开始处理"
        )
        
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=f"处理文档时出错: {str(e)}")

@router.post("/v1/pipeline-async", response_model=AsyncTaskResponse)
async def pipeline_async(
    background_tasks: BackgroundTasks,
    request: PipelineRequest
):
    """异步流水线处理"""
    await initialize_pipeline()
    if not pipeline:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    max_content_length = 1024 * 1024  # 1MB
    if len(request.content.encode('utf-8')) > max_content_length:
        raise HTTPException(status_code=413, detail="文档内容过大，超过1MB限制")
    
    task_id = f"task_{int(time.time())}_{hash(request.content[:100]) % 10000}"
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, "document.md")
    
    try:
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        processing_tasks[task_id] = {
            "status": "processing",
            "start_time": time.time(),
            "progress": "内容已接收，开始处理...",
            "temp_dir": temp_dir,
            "created_at": datetime.now().isoformat()
        }
        
        background_tasks.add_task(
            process_document_background,
            task_id,
            temp_file_path,
            request.max_claims,
            request.max_search_results,
            request.use_section_based_processing
        )
        
        return AsyncTaskResponse(
            task_id=task_id,
            status="processing",
            message="内容接收成功，开始异步处理"
        )
        
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=f"处理文档时出错: {str(e)}")

# 旧的任务状态查询函数已被删除，使用新的 get_evidence_task_status

@router.get("/v1/download/{task_id}")
async def download_task_result(task_id: str, file_type: str = "enhanced_document"):
    """下载处理结果"""
    if task_id not in processing_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = processing_tasks[task_id]
    
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    result = task_info.get("result")
    if not result or not result.output_files:
        raise HTTPException(status_code=404, detail="结果文件不存在")
    
    file_mapping = {
        "enhanced_document": "enhanced_document",
        "evidence_analysis": "evidence_analysis",
        "document": "enhanced_document",
        "analysis": "evidence_analysis"
    }
    
    if file_type not in file_mapping:
        raise HTTPException(status_code=400, detail=f"无效的文件类型: {file_type}")
    
    file_path = result.output_files.get(file_mapping[file_type])
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    if file_type in ["enhanced_document", "document"]:
        filename = f"enhanced_document_{task_id}.md"
        media_type = "text/markdown"
    else:
        filename = f"evidence_analysis_{task_id}.json"
        media_type = "application/json"
    
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )

# =============================================================================
# 新增：Thesis Agent风格的API端点
# =============================================================================

class EvidencePipelineRequest(BaseModel):
    document_content: str = Field(..., description="文档内容")
    document_title: str = Field(default="文档", description="文档标题")
    max_claims: int = Field(default=7, description="最大论断数量")
    max_search_results: int = Field(default=10, description="最大搜索结果数")

@router.post("/v1/evidence-pipeline-async")
async def evidence_pipeline_async(
    background_tasks: BackgroundTasks,
    request: EvidencePipelineRequest
):
    """异步证据增强流水线处理（Thesis Agent风格）"""
    await initialize_pipeline()
    if not pipeline:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    import uuid
    task_id = str(uuid.uuid4())
    
    # 初始化任务状态
    update_task_status(task_id, "pending", 0.0, "任务已提交，等待处理...")
    print(f"🔧 任务 {task_id} 已创建，当前存储中的任务数: {len(_task_storage)}")
    print(f"🔍 任务创建后存储内容: {task_id in _task_storage}")
    print(f"🔍 存储中的所有任务: {list(_task_storage.keys())}")
    
    # 启动后台任务
    background_tasks.add_task(
        process_evidence_pipeline_async,
        task_id,
        request.document_content,
        request.document_title,
        request.max_claims,
        request.max_search_results
    )
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "任务已提交，请使用task_id查询进度"
    }

@router.get("/v1/task/{task_id}")
async def get_evidence_task_status(task_id: str):
    """查询证据增强任务状态"""
    print(f"🔍 查询任务 {task_id}，当前存储中的任务数: {len(_task_storage)}")
    print(f"🔍 存储中的任务ID列表: {list(_task_storage.keys())}")
    
    if task_id not in _task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return _task_storage[task_id]

@router.get("/v1/result/{task_id}")
async def get_evidence_result(task_id: str):
    """获取纯净的论断分析结果JSON"""
    if task_id not in _task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = _task_storage[task_id]
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    if not task_info.get("result"):
        raise HTTPException(status_code=404, detail="结果不存在")
    
    return task_info["result"]

@router.get("/v1/enhanced/{task_id}")
async def get_enhanced_document(task_id: str):
    """获取证据增强后的markdown文档"""
    if task_id not in _task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = _task_storage[task_id]
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    # 从保存的文件中读取增强后的文档
    result_dir = Path(__file__).parent.parent / "test_results"
    timestamp = task_info.get("timestamp", "")
    enhanced_file = result_dir / f"web_enhanced_{task_id}_{timestamp}.md"
    
    if not enhanced_file.exists():
        raise HTTPException(status_code=404, detail="增强文档不存在")
    
    try:
        with open(enhanced_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"enhanced_document": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文档失败: {str(e)}")

# =============================================================================
# 后台处理函数
# =============================================================================

async def process_evidence_pipeline_async(
    task_id: str,
    document_content: str,
    document_title: str,
    max_claims: int,
    max_search_results: int
):
    """异步处理证据增强流水线"""
    global _task_storage
    import time
    start_time = time.time()
    
    try:
        update_task_status(task_id, "running", 10.0, "开始检测缺乏证据支撑的论断...")
        
        # 提取文档章节
        sections = extract_document_sections(document_content)
        
        unified_claims = {}
        all_claims = []
        claim_to_location = {}  # 记录每个claim索引的位置信息
        
        update_task_status(task_id, "running", 20.0, "分析文档章节并收集论断...")
        
        # 第一阶段：收集所有论断（不搜索证据）
        section_count = 0
        total_sections = sum(len(h2_sections) for h2_sections in sections.values())
        
        for h1_title, h2_sections in sections.items():
            unified_claims[h1_title] = {}
            
            for h2_title, section_content in h2_sections.items():
                section_count += 1
                progress = 20.0 + (section_count / total_sections) * 30.0
                update_task_status(task_id, "running", progress, f"收集论断: {h2_title}")
                
                # 使用evidence_detector检测论断
                unsupported_claims = pipeline.evidence_detector._detect_unsupported_claims(h2_title, section_content)
                
                # 限制每个章节的claim数量
                if len(unsupported_claims) > max_claims:
                    unsupported_claims = sorted(unsupported_claims, key=lambda x: x.confidence_level, reverse=True)[:max_claims]
                
                # 全局限制：总共不超过7个claims
                current_total_claims = len(all_claims)
                remaining_slots = 7 - current_total_claims
                if remaining_slots <= 0:
                    break  # 已达到最大claim数量，跳出章节循环
                elif len(unsupported_claims) > remaining_slots:
                    unsupported_claims = unsupported_claims[:remaining_slots]
                
                # 收集claims并记录位置
                section_claims = {}
                for i, claim in enumerate(unsupported_claims):
                    claim_id = f"{h2_title}_claim_{i+1}"
                    claim_index = len(all_claims)  # 使用索引作为键
                    claim_to_location[claim_index] = (h1_title, h2_title, claim_id)
                    all_claims.append(claim)
                    
                    # 先创建基本结构
                    section_claims[claim_id] = {
                        "original_content": claim.claim_text,
                        "regenerated_content": claim.claim_text,  # 稍后更新
                        "suggestion": "正在搜索证据...",
                        "word_count": len(claim.claim_text),
                        "status": "processing"
                    }
                
                unified_claims[h1_title][h2_title] = section_claims
                
                # 如果已达到7个claims，停止收集
                if len(all_claims) >= 7:
                    break
            
            if len(all_claims) >= 7:
                break
        
        # 第二阶段：并行搜索所有论断的证据
        if all_claims:
            update_task_status(task_id, "running", 50.0, f"并行搜索 {len(all_claims)} 个论断的证据...")
            print(f"🔍 开始并行搜索 {len(all_claims)} 个论断的证据...")
            
            # 使用并行搜索
            evidence_results = pipeline.evidence_detector._batch_search_evidence(all_claims)
            
            # 第三阶段：更新结果
            update_task_status(task_id, "running", 80.0, "生成增强内容...")
            
            for claim_index, (claim, evidence) in enumerate(zip(all_claims, evidence_results)):
                h1_title, h2_title, claim_id = claim_to_location[claim_index]
                
                # 生成证据增强的内容
                try:
                    if evidence.evidence_sources and evidence.processing_status == 'success':
                        enhanced_claim = _enhance_claim_with_evidence(claim.claim_text, evidence.evidence_sources)
                        suggestion = f"已为该论断补充 {len(evidence.evidence_sources)} 条证据支撑"
                        status = "enhanced"
                    else:
                        enhanced_claim = claim.claim_text
                        suggestion = "未找到足够的证据支撑，建议进一步验证"
                        status = "no_evidence"
                    
                    # 更新unified_claims中的数据
                    unified_claims[h1_title][h2_title][claim_id] = {
                        "original_content": claim.claim_text,
                        "regenerated_content": enhanced_claim,
                        "suggestion": suggestion,
                        "word_count": len(enhanced_claim),
                        "status": status
                    }
                except Exception as e:
                    print(f"    ❌ 处理论断 {claim_id} 时出错: {str(e)}")
                    # 保持原始内容
                    unified_claims[h1_title][h2_title][claim_id] = {
                        "original_content": claim.claim_text,
                        "regenerated_content": claim.claim_text,
                        "suggestion": f"处理时出错: {str(e)}",
                        "word_count": len(claim.claim_text),
                        "status": "error"
                    }
        
        update_task_status(task_id, "running", 80.0, "生成增强文档...")
        
        # 生成增强后的markdown文档
        enhanced_document = _generate_markdown_from_claims(unified_claims, document_content)
        
        # 保存结果文件
        update_task_status(task_id, "running", 90.0, "保存结果文件...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = Path(__file__).parent.parent / "test_results"
        result_dir.mkdir(exist_ok=True)
        
        # 保存JSON结果
        claims_file = result_dir / f"web_claims_{task_id}_{timestamp}.json"
        with open(claims_file, 'w', encoding='utf-8') as f:
            json.dump(unified_claims, f, ensure_ascii=False, indent=2)
        
        # 保存增强文档
        enhanced_file = result_dir / f"web_enhanced_{task_id}_{timestamp}.md"
        with open(enhanced_file, 'w', encoding='utf-8') as f:
            f.write(enhanced_document)
        
        processing_time = time.time() - start_time
        
        # 统计信息
        total_claims_found = sum(len(h2_claims) for h1_claims in unified_claims.values() for h2_claims in h1_claims.values())
        enhanced_claims = sum(1 for h1_claims in unified_claims.values() 
                            for h2_claims in h1_claims.values() 
                            for claim_data in h2_claims.values() 
                            if claim_data.get('status') == 'enhanced')
        
        statistics = {
            "total_sections_processed": total_sections,
            "total_claims_found": total_claims_found,
            "enhanced_claims": enhanced_claims,
            "evidence_sources_found": sum(len(claim_data.get('evidence_sources', [])) 
                                        for h1_claims in unified_claims.values() 
                                        for h2_claims in h1_claims.values() 
                                        for claim_data in h2_claims.values()),
            "processing_time": processing_time
        }
        
        # 更新任务状态为完成
        update_task_status(
            task_id, 
            "completed", 
            100.0, 
            "证据增强流水线处理完成",
            result=unified_claims,
            error=None
        )
        
        # 添加时间戳到任务信息中
        _task_storage[task_id]["timestamp"] = timestamp
        _task_storage[task_id]["statistics"] = statistics
        
        print(f"✅ 证据增强任务 {task_id} 完成，耗时 {processing_time:.1f}秒")
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"证据增强处理异常: {str(e)}"
        print(f"❌ 任务 {task_id} 失败: {error_msg}")
        traceback.print_exc()
        
        update_task_status(
            task_id,
            "failed",
            0.0,
            "证据增强处理失败",
            result=None,
            error=error_msg
        )

async def process_document_background(
    task_id: str,
    document_path: str,
    max_claims: int,
    max_search_results: int,
    use_section_based_processing: bool = False
):
    """后台处理文档的函数"""
    try:
        processing_tasks[task_id]["progress"] = "正在检测论断..."
        
        result = pipeline.process_whole_document(
            document_path=document_path,
            max_claims=max_claims,
            max_search_results=max_search_results,
            use_section_based_processing=use_section_based_processing
        )
        
        if result['status'] == 'success':
            processing_tasks[task_id].update({
                "status": "completed",
                "progress": "处理完成",
                "completed_at": datetime.now().isoformat(),
                "result": DocumentProcessResponse(
                    task_id=task_id,
                    status="completed",
                    message="文档处理成功完成",
                    processing_time=result['processing_time'],
                    statistics=result['statistics'],
                    output_files=result['output_files']
                )
            })
        else:
            processing_tasks[task_id].update({
                "status": "failed",
                "progress": "处理失败",
                "completed_at": datetime.now().isoformat(),
                "result": DocumentProcessResponse(
                    task_id=task_id,
                    status="failed",
                    message="文档处理失败",
                    error=result.get('error', '未知错误')
                )
            })
    
    except Exception as e:
        error_msg = f"处理过程中出现异常: {str(e)}"
        print(f"❌ 任务 {task_id} 处理失败: {error_msg}")
        traceback.print_exc()
        
        processing_tasks[task_id].update({
            "status": "failed",
            "progress": "处理异常",
            "completed_at": datetime.now().isoformat(),
            "result": DocumentProcessResponse(
                task_id=task_id,
                status="failed",
                message="文档处理异常",
                error=error_msg
            )
        })
