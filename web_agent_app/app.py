#!/usr/bin/env python3
"""
论据支持度评估系统 FastAPI 应用 - 重构版
按照新的API v1结构设计
"""

import os
import json
import time
import tempfile
import shutil
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
import traceback

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from whole_document_pipeline import WholeDocumentPipeline
from evidence_detector import UnsupportedClaim, EvidenceResult

# 创建FastAPI应用
app = FastAPI(
    title="论据支持度评估系统",
    description="基于AI的智能文档分析系统，用于验证学术文档中论点的事实支撑",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
pipeline = None
processing_tasks = {}


# =============================================================================
# 辅助函数
# =============================================================================

def generate_unified_sections(original_content: str, enhanced_content: str, 
                            evidence_analysis: Dict[str, Any]) -> Dict[str, dict]:
    """生成统一格式的章节结果 - 使用一级标题嵌套二级标题的结构"""
    unified_sections = {}
    
    # 解析原始内容的层级章节
    original_hierarchy = parse_hierarchical_sections(original_content)
    # 解析增强后内容的层级章节
    enhanced_hierarchy = parse_hierarchical_sections(enhanced_content) if enhanced_content else original_hierarchy
    
    # 从证据分析中提取章节信息
    section_claims = {}
    if evidence_analysis and 'claims' in evidence_analysis:
        for claim in evidence_analysis['claims']:
            section_title = claim.get('section_title', '未知章节')
            if section_title not in section_claims:
                section_claims[section_title] = []
            section_claims[section_title].append(claim)
    
    # 为每个一级标题生成结果
    for h1_title, h2_sections in original_hierarchy.items():
        unified_sections[h1_title] = {}
        
        # 为每个二级标题生成结果
        for h2_title, original_section_content in h2_sections.items():
            enhanced_section_content = enhanced_hierarchy.get(h1_title, {}).get(h2_title, original_section_content)
            
            # 生成该章节的建议
            suggestion = ""
            # 尝试多种匹配方式查找claims
            claims = []
            for section_title, section_claims_list in section_claims.items():
                if (section_title == h2_title or 
                    section_title == f"{h1_title} {h2_title}" or
                    section_title == f"{h1_title}_{h2_title}" or
                    h2_title in section_title or
                    section_title in h2_title):
                    claims.extend(section_claims_list)
            
            if claims:
                claim_count = len(claims)
                evidence_count = sum(len(claim.get('evidence_sources', [])) for claim in claims)
                suggestion = f"检测到{claim_count}个论断，找到{evidence_count}条支撑证据"
            else:
                if original_section_content != enhanced_section_content:
                    suggestion = "内容已增强"
                else:
                    # 跳过无需修改的章节，不包含在输出中
                    continue
            
            # 只有有论断分析或内容变化的章节才包含在输出中
            # 计算字数
            word_count = len(enhanced_section_content.replace(' ', '').replace('\n', ''))
            
            # 确保一级标题存在
            if h1_title not in unified_sections:
                unified_sections[h1_title] = {}
            
            unified_sections[h1_title][h2_title] = {
                "original_content": original_section_content,
                "suggestion": suggestion,
                "regenerated_content": enhanced_section_content,
                "word_count": word_count,
                "status": "success"
            }
    
    return unified_sections


def parse_hierarchical_sections(content: str) -> Dict[str, Dict[str, str]]:
    """解析Markdown内容的层级章节结构"""
    hierarchy = {}
    lines = content.split('\n')
    
    current_h1 = None
    current_h2 = None
    current_content = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # 检测一级标题 (# 标题)
        if line_stripped.startswith('# ') and not line_stripped.startswith('## '):
            # 保存之前的二级标题内容
            if current_h1 and current_h2:
                if current_h1 not in hierarchy:
                    hierarchy[current_h1] = {}
                hierarchy[current_h1][current_h2] = '\n'.join(current_content).strip()
            
            # 开始新的一级标题
            current_h1 = line_stripped[2:].strip()
            current_h2 = None
            current_content = []
            
        # 检测二级标题 (## 标题)
        elif line_stripped.startswith('## '):
            # 保存之前的二级标题内容
            if current_h1 and current_h2:
                if current_h1 not in hierarchy:
                    hierarchy[current_h1] = {}
                hierarchy[current_h1][current_h2] = '\n'.join(current_content).strip()
            
            # 开始新的二级标题
            if current_h1:  # 确保有一级标题
                current_h2 = line_stripped[3:].strip()
                current_content = [line]  # 包含标题行
            else:
                # 如果没有一级标题，创建默认的
                current_h1 = "文档内容"
                current_h2 = line_stripped[3:].strip()
                current_content = [line]
                
        else:
            # 普通内容行
            if current_h1 and current_h2:
                current_content.append(line)
            elif current_h1 and not current_h2:
                # 一级标题下没有二级标题的内容，跳过空行，等待二级标题
                if line.strip():  # 只有非空行才创建默认二级标题
                    current_h2 = "概述"
                    current_content = [line]
    
    # 保存最后一个章节
    if current_h1 and current_h2:
        if current_h1 not in hierarchy:
            hierarchy[current_h1] = {}
        hierarchy[current_h1][current_h2] = '\n'.join(current_content).strip()
    
    return hierarchy

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

# =============================================================================
# Pydantic模型定义
# =============================================================================

class SectionResult(BaseModel):
    """统一的章节结果格式"""
    section_title: str = Field(..., description="章节标题")
    original_content: str = Field(..., description="原始内容")
    suggestion: str = Field(..., description="修改建议或分析结果")
    regenerated_content: str = Field(..., description="修改后的内容")
    word_count: int = Field(..., description="字数统计")
    status: str = Field(default="success", description="处理状态")

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
    # 新增统一格式的JSON输出
    unified_sections: Dict[str, SectionResult] = Field(default_factory=dict, description="统一格式的章节结果")

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
    # 新增统一格式的JSON输出
    unified_sections: Dict[str, SectionResult] = Field(default_factory=dict, description="统一格式的章节结果")

# =============================================================================
# 启动和基础端点
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global pipeline
    try:
        print("🚀 初始化论据支持度评估系统...")
        pipeline = WholeDocumentPipeline()
        print("✅ 系统初始化完成")
    except Exception as e:
        print(f"❌ 系统初始化失败: {str(e)}")
        raise

@app.get("/", response_model=SystemInfoResponse)
async def root():
    """系统信息"""
    return SystemInfoResponse()

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "pipeline_ready": pipeline is not None
    }

# =============================================================================
# API v1 端点
# =============================================================================

@app.post("/api/v1/extract-claims", response_model=ExtractClaimsResponse)
async def extract_claims(request: ExtractClaimsRequest):
    """提取核心论点"""
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

@app.post("/api/v1/search-evidence", response_model=SearchEvidenceResponse)
async def search_evidence(request: SearchEvidenceRequest):
    """为论断搜索证据支撑"""
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

@app.post("/api/v1/analyze-evidence", response_model=AnalyzeEvidenceResponse)
async def analyze_evidence(request: AnalyzeEvidenceRequest):
    """分析证据并生成增强内容"""
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

@app.post("/api/v1/websearch", response_model=WebSearchResponse)
async def websearch(request: WebSearchRequest):
    """网络搜索接口"""
    if not pipeline:
        raise HTTPException(status_code=503, detail="系统未初始化")
    
    start_time = time.time()
    
    try:
        print(f"🔍 执行网络搜索: {request.query}")
        
        # 使用web搜索代理执行搜索
        from web_search_agent import EvidenceCollection
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

@app.post("/api/v1/pipeline", response_model=PipelineResponse)
async def pipeline_sync(request: PipelineRequest):
    """完整流水线处理（同步）"""
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
            
            # 生成统一格式的章节结果
            unified_sections = generate_unified_sections(
                request.content,
                enhanced_document,
                evidence_analysis
            )
            
            return PipelineResponse(
                status="success",
                message="完整流水线处理成功完成",
                enhanced_document=enhanced_document,
                evidence_analysis=evidence_analysis,
                statistics=result.get('statistics', {}),
                processing_time=processing_time,
                unified_sections=unified_sections
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

@app.post("/api/v1/upload", response_model=AsyncTaskResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_claims: int = Form(default=15),
    max_search_results: int = Form(default=10),
    use_section_based_processing: bool = Form(default=True)
):
    """文件上传处理（异步）"""
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

@app.post("/api/v1/pipeline-async", response_model=AsyncTaskResponse)
async def pipeline_async(
    background_tasks: BackgroundTasks,
    request: PipelineRequest
):
    """异步流水线处理"""
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

@app.get("/api/v1/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """查询任务状态"""
    if task_id not in processing_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_info = processing_tasks[task_id]
    
    result = None
    if task_info["status"] == "completed" and "result" in task_info:
        task_result = task_info["result"]
        result = {
            "status": task_result.status,
            "message": task_result.message,
            "processing_time": task_result.processing_time,
            "statistics": task_result.statistics,
            "output_files": task_result.output_files,
            "error": task_result.error,
            "unified_sections": {k: v.dict() for k, v in task_result.unified_sections.items()} if task_result.unified_sections else {}
        }
    elif task_info["status"] == "failed" and "result" in task_info:
        task_result = task_info["result"]
        result = {
            "status": task_result.status,
            "message": task_result.message,
            "error": task_result.error
        }
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task_info["status"],
        progress=task_info.get("progress"),
        result=result,
        created_at=task_info.get("created_at"),
        completed_at=task_info.get("completed_at")
    )

@app.get("/api/v1/download/{task_id}")
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
# 后台处理函数和异常处理
# =============================================================================

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
            # 读取原始内容和增强后的内容来生成统一格式的JSON
            original_content = ""
            enhanced_content = ""
            evidence_analysis = {}
            
            try:
                # 读取原始文档内容
                with open(document_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # 读取增强后的文档内容
                output_files = result.get('output_files', {})
                if 'enhanced_document' in output_files and os.path.exists(output_files['enhanced_document']):
                    with open(output_files['enhanced_document'], 'r', encoding='utf-8') as f:
                        enhanced_content = f.read()
                else:
                    enhanced_content = original_content
                
                # 读取证据分析结果
                if 'evidence_analysis' in output_files and os.path.exists(output_files['evidence_analysis']):
                    with open(output_files['evidence_analysis'], 'r', encoding='utf-8') as f:
                        evidence_analysis = json.load(f)
            except Exception as e:
                print(f"⚠️ 读取文件内容失败: {str(e)}")
            
            # 生成统一格式的章节结果
            unified_sections = generate_unified_sections(
                original_content,
                enhanced_content,
                evidence_analysis
            )
            
            # 生成两个输出文件
            import os
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 1. 生成unified_sections JSON文件
            results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "router", "outputs", "web_evidence")
            os.makedirs(results_dir, exist_ok=True)
            unified_sections_file = os.path.join(results_dir, f"unified_sections_{timestamp}.json")
            with open(unified_sections_file, 'w', encoding='utf-8') as f:
                json.dump(unified_sections, f, ensure_ascii=False, indent=2)
            
            # 2. 生成增强后的markdown文件
            enhanced_md_file = os.path.join(results_dir, f"enhanced_content_{task_id}.md")
            with open(enhanced_md_file, 'w', encoding='utf-8') as f:
                f.write(enhanced_content)
            
            # 构建简化的结果 - 只返回文件路径和基本信息
            unified_result = {
                "unified_sections_file": unified_sections_file,
                "optimized_content_file": enhanced_md_file,
                "processing_time": result['processing_time'],
                "sections_count": len(unified_sections),
                "service_type": "web_agent",
                "message": f"已生成2个文件: {os.path.basename(unified_sections_file)}, {os.path.basename(enhanced_md_file)}"
            }
            
            processing_tasks[task_id].update({
                "status": "completed",
                "progress": "处理完成",
                "completed_at": datetime.now().isoformat(),
                "result": unified_result
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

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    print(f"❌ 全局异常: {str(exc)}")
    traceback.print_exc()
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "内部服务器错误",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
