"""
整体文档处理流水线
一次性处理整个文档，进行claim检测、证据搜索、分析和增强
"""

import json
import os
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from evidence_detector import EvidenceDetector, UnsupportedClaim, EvidenceResult
from dataclasses import asdict
from document_generator import DocumentGenerator
from direct_document_merger import DirectDocumentMerger
from web_search_agent import WebSearchAgent, EvidenceCollection
# 确保导入当前目录的config模块
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 强制重新导入config模块
import importlib
try:
    import config
    # 重新加载config模块以确保获取最新的环境变量
    importlib.reload(config)
except:
    # 如果重新加载失败，直接导入
    import config

# 配置日志
def setup_logging():
    """设置日志配置，包括HTTP请求日志"""
    # 安全地获取LOG_LEVEL，如果不存在则使用默认值
    log_level = getattr(config, 'LOG_LEVEL', 'INFO')
    if isinstance(log_level, str):
        log_level = log_level.upper()
    else:
        log_level = 'INFO'
    
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 安全地检查ENABLE_HTTP_LOGS
    enable_http_logs = getattr(config, 'ENABLE_HTTP_LOGS', True)
    if enable_http_logs:
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.INFO)
        openai_logger = logging.getLogger("openai")
        openai_logger.setLevel(logging.INFO)
        print("🔍 HTTP请求日志已启用")

setup_logging()

class WholeDocumentPipeline:
    """整体文档处理流水线"""
    
    def __init__(self):
        self.evidence_detector = EvidenceDetector()
        self.direct_merger = DirectDocumentMerger()
        self.web_search_agent = WebSearchAgent()
        # 统一输出到 router/outputs/web_evidence
        from pathlib import Path
        self.output_dir = str(Path(__file__).parent.parent / "router" / "outputs" / "web_evidence")
        
        # 并行处理配置
        self.max_workers = config.MAX_WORKERS
        self.thread_lock = threading.Lock()
        self.enable_parallel_search = config.ENABLE_PARALLEL_SEARCH
        self.enable_parallel_enhancement = config.ENABLE_PARALLEL_ENHANCEMENT
    
    def process_whole_document(self, document_path: str, 
                              max_claims: Optional[int] = None,
                              max_search_results: int = 10,
                              use_section_based_processing: bool = False) -> Dict[str, Any]:
        """处理整个文档的完整流程"""
        print("🚀 开始整体文档处理流水线...")
        start_time = time.time()
        
        # 生成时间戳用于文件命名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # 如果启用章节处理模式，使用新的处理方式
        if use_section_based_processing:
            return self._process_document_by_sections(document_path, max_claims, max_search_results, timestamp)
        
        try:
            # 使用传统整体文档处理模式（回退到新的evidence_detector）
            return self._process_whole_document_legacy(document_path, max_claims, max_search_results, timestamp)
            
        except Exception as e:
            print(f"❌ 流水线执行过程中出现错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._create_error_result(document_path, str(e), timestamp)
    
    def _extract_content_from_json(self, document_data: Dict) -> str:
        """从JSON文档中提取完整内容"""
        if isinstance(document_data, dict) and 'content' in document_data:
            return document_data['content']
        elif isinstance(document_data, dict):
            # 递归提取所有文本内容
            content_parts = []
            for key, value in document_data.items():
                if isinstance(value, str) and len(value.strip()) > 50:
                    content_parts.append(f"## {key}\n\n{value}")
                elif isinstance(value, dict):
                    nested_content = self._extract_content_from_json(value)
                    if nested_content:
                        content_parts.append(f"## {key}\n\n{nested_content}")
            return "\n\n".join(content_parts)
        else:
            return str(document_data)
    
    
    def _create_empty_result(self, document_path: str, timestamp: str) -> Dict[str, Any]:
        """创建空结果"""
        return {
            "status": "no_claims_detected",
            "document_path": document_path,
            "timestamp": timestamp,
            "message": "未检测到需要证据支撑的客观性论断"
        }
    
    def _create_error_result(self, document_path: str, error_message: str, timestamp: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            "status": "error",
            "document_path": document_path,
            "timestamp": timestamp,
            "error": error_message
        }
    
    def _process_document_by_sections(self, document_path: str, 
                                    max_claims: Optional[int] = None,
                                    max_search_results: int = 10,
                                    timestamp: str = None) -> Dict[str, Any]:
        """
        按章节处理文档（新的处理方式）
        
        Args:
            document_path: 文档路径
            max_claims: 每个章节最大论断数
            max_search_results: 每个论断最大搜索结果数
            timestamp: 时间戳
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        print("🔄 使用章节并行处理模式...")
        start_time = time.time()
        
        if timestamp is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        try:
            # 读取文档内容
            with open(document_path, 'r', encoding='utf-8') as f:
                if document_path.endswith('.json'):
                    document_data = json.load(f)
                    full_content = self._extract_content_from_json(document_data)
                else:
                    full_content = f.read()
                    document_data = {"content": full_content}
            
            print(f"📊 文档长度: {len(full_content)} 字符")
            
            # 提取章节
            sections = self._extract_sections_from_content(full_content)
            
            if not sections:
                print("⚠️ 未检测到章节，回退到整体处理模式")
                return self._process_whole_document_legacy(document_path, max_claims, max_search_results, timestamp)
            
            print(f"📑 检测到 {len(sections)} 个章节")
            
            # 并行处理章节
            section_results = self._process_sections_parallel(sections, max_claims or 5, max_search_results)
            
            # 获取章节顺序
            section_order = getattr(sections, '_section_order', None)
            
            # 合并结果（文件保存已在此方法中完成）
            enhanced_content = self._merge_section_results(section_results, timestamp, document_path, section_order)
            
            # 不再需要额外的文件保存，已在_merge_section_results中完成
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # 统计信息
            total_claims = sum(result.get('statistics', {}).get('claims_detected', 0) for result in section_results.values())
            total_evidence = sum(result.get('statistics', {}).get('evidence_found', 0) for result in section_results.values())
            successful_sections = sum(1 for result in section_results.values() if result.get('status') == 'success')
            
            print(f"\n✅ 章节并行处理完成！")
            print(f"📊 处理统计:")
            print(f"   - 处理章节: {len(sections)} 个")
            print(f"   - 成功章节: {successful_sections} 个")
            print(f"   - 检测论断: {total_claims} 个")
            print(f"   - 搜索证据: {total_evidence} 条")
            print(f"   - 处理时间: {processing_time:.1f} 秒")
            # 文件路径
            enhanced_file = os.path.join(self.output_dir, f"enhanced_document_{timestamp}.md")
            analysis_file = os.path.join(self.output_dir, f"evidence_analysis_{timestamp}.json")
            
            print(f"📁 输出文件:")
            print(f"   - 增强文档: {enhanced_file}")
            print(f"   - 证据分析: {analysis_file}")
            
            return {
                'status': 'success',
                'document_path': document_path,
                'processing_time': processing_time,
                'processing_mode': 'section_based_parallel',
                'statistics': {
                    'total_sections': len(sections),
                    'successful_sections': successful_sections,
                    'total_claims_detected': total_claims,
                    'total_evidence_sources': total_evidence,
                    'total_analysis_results': len(section_results)
                },
                'output_files': {
                    'enhanced_document': os.path.join(self.output_dir, f"enhanced_document_{timestamp}.md"),
                    'evidence_analysis': os.path.join(self.output_dir, f"evidence_analysis_{timestamp}.json")
                }
            }
            
        except Exception as e:
            print(f"❌ 章节处理过程中出现错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._create_error_result(document_path, str(e), timestamp)
    
    def _extract_sections_from_content(self, content: str) -> Dict[str, str]:
        """从文档内容中提取章节 - 只按一级标题(#)分割，保持层级结构和顺序"""
        from collections import OrderedDict
        sections = OrderedDict()  # 使用有序字典保持章节顺序
        section_order = []  # 额外记录章节顺序
        current_section = None
        current_content = []
        
        lines = content.split('\n')
        
        for line in lines:
            # 只检测一级标题（# 开头）作为主要章节分割点
            header_match = re.match(r'^#\s+(.+)$', line.strip())
            if header_match:
                # 保存上一个章节
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # 开始新章节
                current_section = header_match.group(1).strip()
                section_order.append(current_section)  # 记录章节顺序
                current_content = [line]  # 包含标题行
            else:
                if current_section:
                    current_content.append(line)
                else:
                    # 如果还没有遇到一级标题，将内容添加到临时章节
                    if not current_section:
                        current_section = "文档开头"
                        section_order.append(current_section)
                        current_content = [line]
                    else:
                        current_content.append(line)
        
        # 保存最后一个章节
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        # 将章节顺序信息存储在sections对象中
        sections._section_order = section_order
        
        print(f"📑 提取章节顺序: {section_order}")
        return sections
    
    def _process_sections_parallel(self, sections: Dict[str, str], 
                                 max_claims_per_section: int,
                                 max_search_results: int) -> Dict[str, Dict[str, Any]]:
        """并行处理章节 - 简化版：直接使用evidence_detector"""
        print(f"🚀 启动并行章节处理（章节数: {len(sections)}）")
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=min(5, len(sections))) as executor:
            future_to_section = {
                executor.submit(
                    self.evidence_detector.process_section,
                    section_title,
                    section_content,
                    max_claims_per_section
                ): section_title
                for section_title, section_content in sections.items()
            }
            
            for future in as_completed(future_to_section):
                section_title = future_to_section[future]
                try:
                    result = future.result()
                    results[section_title] = result
                    print(f"  ✅ 章节处理完成: {section_title}")
                except Exception as e:
                    print(f"  ❌ 章节处理失败: {section_title} - {str(e)}")
                    results[section_title] = {
                        'section_title': section_title,
                        'status': 'failed',
                        'error': str(e),
                        'enhanced_content': sections[section_title],
                        'original_content': sections[section_title]
                    }
        
        print(f"✅ 章节处理完成，处理了 {len(results)} 个章节")
        return results
    
    def _parallel_detect_claims(self, sections: Dict[str, str], max_claims: int) -> Dict[str, List[UnsupportedClaim]]:
        """阶段1：并行检测所有章节的论断"""
        section_claims = {}
        
        with ThreadPoolExecutor(max_workers=min(10, len(sections))) as executor:
            future_to_section = {
                executor.submit(
                    self.evidence_detector._detect_unsupported_claims,
                    title,
                    content
                ): title
                for title, content in sections.items()
            }
            
            completed = 0
            total_claims = 0
            for future in as_completed(future_to_section):
                section_title = future_to_section[future]
                try:
                    claims = future.result()
                    if len(claims) > max_claims:
                        claims = sorted(claims, key=lambda x: x.confidence_level, reverse=True)[:max_claims]
                    
                    section_claims[section_title] = claims
                    completed += 1
                    total_claims += len(claims)
                    
                    with self.thread_lock:
                        print(f"  📋 章节 {completed}/{len(sections)} 论断检测完成: {section_title} ({len(claims)} 个论断)")
                
                except Exception as e:
                    with self.thread_lock:
                        print(f"  ❌ 章节 {section_title} 论断检测失败: {str(e)}")
                    section_claims[section_title] = []
        
        print(f"✅ 论断检测完成，共检测到 {total_claims} 个论断")
        return section_claims
    
    def _parallel_search_evidence(self, section_claims: Dict[str, List[UnsupportedClaim]]) -> Dict[str, List[EvidenceResult]]:
        """阶段2：并行搜索所有论断的证据"""
        section_evidence = {}
        
        # 收集所有论断
        all_claims = []
        claim_to_section = {}
        for section_title, claims in section_claims.items():
            for claim in claims:
                all_claims.append(claim)
                claim_to_section[claim.claim_id] = section_title
        
        # 全局论据数量限制
        MAX_TOTAL_CLAIMS = 25
        if len(all_claims) > MAX_TOTAL_CLAIMS:
            print(f"⚠️ 论据总数 {len(all_claims)} 超过限制 {MAX_TOTAL_CLAIMS}，按置信度排序并限制处理数量")
            # 按置信度排序，取前25个
            all_claims.sort(key=lambda x: x.confidence_level, reverse=True)
            limited_claims = all_claims[:MAX_TOTAL_CLAIMS]
            
            # 重新构建 claim_to_section 映射
            claim_to_section = {}
            for claim in limited_claims:
                claim_to_section[claim.claim_id] = claim.section_title
            
            all_claims = limited_claims
        
        if not all_claims:
            return {title: [] for title in section_claims.keys()}
        
        print(f"🔍 开始并行搜索 {len(all_claims)} 个论断的证据...")
        
        # 并行搜索所有论断的证据
        with ThreadPoolExecutor(max_workers=min(15, len(all_claims))) as executor:
            future_to_claim = {
                executor.submit(
                    self.evidence_detector._search_evidence_for_claim,
                    claim
                ): claim
                for claim in all_claims
            }
            
            # 初始化结果字典
            for section_title in section_claims.keys():
                section_evidence[section_title] = []
            
            completed = 0
            total_evidence = 0
            for future in as_completed(future_to_claim):
                claim = future_to_claim[future]
                try:
                    evidence_result = future.result()
                    section_title = claim_to_section[claim.claim_id]
                    section_evidence[section_title].append(evidence_result)
                    completed += 1
                    
                    if evidence_result.processing_status == 'success':
                        total_evidence += len(evidence_result.evidence_sources)
                    
                    with self.thread_lock:
                        print(f"  🔍 论断 {completed}/{len(all_claims)} 证据搜索完成: {claim.claim_id}")
                
                except Exception as e:
                    with self.thread_lock:
                        print(f"  ❌ 论断 {claim.claim_id} 证据搜索失败: {str(e)}")
                    section_title = claim_to_section[claim.claim_id]
                    # 创建失败的证据结果
                    failed_result = EvidenceResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.claim_text,
                        section_title=claim.section_title,
                        search_query='',
                        evidence_sources=[],
                        enhanced_text=claim.claim_text,
                        confidence_score=0.0,
                        processing_status='failed'
                    )
                    section_evidence[section_title].append(failed_result)
        
        print(f"✅ 证据搜索完成，共找到 {total_evidence} 条证据")
        return section_evidence
    
    def _parallel_generate_modifications(self, sections: Dict[str, str], 
                                       section_evidence: Dict[str, List[EvidenceResult]]) -> Dict[str, Dict[str, Any]]:
        """阶段3：并行生成所有章节的修改内容"""
        results = {}
        
        # 筛选需要修改的章节（有证据的章节）
        sections_to_modify = {}
        sections_to_skip = {}
        
        for title, content in sections.items():
            evidence_list = section_evidence.get(title, [])
            # 只有当章节有成功找到证据的论断时才需要调用API修改
            has_successful_evidence = any(er.processing_status == 'success' for er in evidence_list)
            
            if has_successful_evidence:
                sections_to_modify[title] = content
            else:
                # 跳过修改，直接返回原内容
                sections_to_skip[title] = {
                    'section_title': title,
                    'status': 'skipped',
                    'message': '无需修改（未找到有效证据）',
                    'unsupported_claims': [],
                    'evidence_results': [],
                    'enhanced_content': content,
                    'original_content': content,
                    'processing_time': 0,
                    'statistics': {
                        'claims_detected': len(evidence_list),
                        'evidence_found': 0,
                        'claims_enhanced': 0,
                        'success_rate': 0
                    }
                }
        
        print(f"📝 需要修改的章节: {len(sections_to_modify)} 个，跳过的章节: {len(sections_to_skip)} 个")
        
        # 将跳过的章节直接加入结果
        results.update(sections_to_skip)
        
        # 只对需要修改的章节进行并行API调用
        if sections_to_modify:
            # 限制并发数，避免API压力过大
            max_concurrent_api_calls = min(3, len(sections_to_modify))  # 最多3个并发API调用
            with ThreadPoolExecutor(max_workers=max_concurrent_api_calls) as executor:
                future_to_section = {
                    executor.submit(
                        self._generate_section_result,
                        title,
                        content,
                        section_evidence.get(title, [])
                    ): title
                    for title, content in sections_to_modify.items()
                }
            
            completed = 0
            for future in as_completed(future_to_section):
                section_title = future_to_section[future]
                try:
                    result = future.result()
                    results[section_title] = result
                    completed += 1
                    
                    with self.thread_lock:
                        print(f"  📝 章节 {completed}/{len(sections_to_modify)} 修改生成完成: {section_title}")
                
                except Exception as e:
                    with self.thread_lock:
                        print(f"  ❌ 章节 {section_title} 修改生成失败: {str(e)}")
                    results[section_title] = {
                        'section_title': section_title,
                        'status': 'failed',
                        'error': str(e),
                        'enhanced_content': sections_to_modify[section_title],
                        'original_content': sections_to_modify[section_title]
                    }
        
        print(f"✅ 修改生成完成，处理了 {len(results)} 个章节")
        return results
    
    def _generate_section_result(self, section_title: str, section_content: str, 
                               evidence_results: List[EvidenceResult]) -> Dict[str, Any]:
        """生成单个章节的处理结果"""
        start_time = time.time()
        
        try:
            # 直接使用原内容，增强逻辑已在evidence_detector中处理
            modified_content = section_content
            
            # 统计信息
            successful_evidence = sum(1 for er in evidence_results if er.processing_status == 'success')
            total_evidence_sources = sum(len(er.evidence_sources) for er in evidence_results)
            
            processing_time = time.time() - start_time
            
            return {
                'section_title': section_title,
                'status': 'success',
                'message': f'成功处理 {len(evidence_results)} 个论断',
                'unsupported_claims': [asdict(er) for er in evidence_results],  # 兼容性
                'evidence_results': [asdict(er) for er in evidence_results],
                'enhanced_content': modified_content,
                'original_content': section_content,
                'processing_time': processing_time,
                'statistics': {
                    'claims_detected': len(evidence_results),
                    'evidence_found': total_evidence_sources,
                    'claims_enhanced': successful_evidence,
                    'success_rate': (successful_evidence / len(evidence_results) * 100) if evidence_results else 0
                }
            }
            
        except Exception as e:
            return {
                'section_title': section_title,
                'status': 'failed',
                'error': str(e),
                'enhanced_content': section_content,
                'original_content': section_content,
                'unsupported_claims': [],
                'evidence_results': [],
                'processing_time': time.time() - start_time,
                'statistics': {
                    'claims_detected': 0,
                    'evidence_found': 0,
                    'claims_enhanced': 0
                }
            }
    
    
    def _merge_section_results(self, section_results: Dict[str, Dict[str, Any]], 
                             timestamp: str, document_path: str, section_order: List[str] = None) -> str:
        """合并章节处理结果为完整文档 - 使用新的三步骤流程"""
        print("📋 开始合并章节结果...")
        
        # 使用直接合并器生成最终文档（无需API调用），传递章节顺序
        final_document = self.direct_merger.merge_sections_to_markdown(section_results, section_order)
        
        # 只保存两个文件：
        # 1. 修改完成的markdown文档
        final_doc_path = os.path.join(self.output_dir, f"enhanced_document_{timestamp}.md")
        self.direct_merger.save_enhanced_document(final_document, final_doc_path)
        
        # 2. 证据分析报告
        analysis_json_path = os.path.join(self.output_dir, f"evidence_analysis_{timestamp}.json")
        self.direct_merger.generate_evidence_analysis(section_results, analysis_json_path, timestamp)
        
        print(f"✅ 文档处理完成")
        print(f"   📄 增强文档: {final_doc_path}")
        print(f"   📊 证据分析: {analysis_json_path}")
        
        return final_document
    
    # 移除了_generate_section_analysis_json方法，现在使用直接合并器的分析功能
    
    def _process_whole_document_legacy(self, document_path: str, 
                                     max_claims: Optional[int] = None,
                                     max_search_results: int = 10,
                                     timestamp: str = None) -> Dict[str, Any]:
        """原有的整体文档处理方式（作为备选方案）"""
        print("🔄 回退到原有的整体文档处理模式...")
        
        if timestamp is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # 使用新的evidence_detector + document_generator处理整个文档
        try:
            with open(document_path, 'r', encoding='utf-8') as f:
                if document_path.endswith('.json'):
                    document_data = json.load(f)
                    full_content = self._extract_content_from_json(document_data)
                else:
                    full_content = f.read()
                    document_data = {"content": full_content}
            
            # 将整个文档作为单一章节处理
            result = self.evidence_detector.process_section(
                section_title="完整文档",
                section_content=full_content,
                max_claims=max_claims or 20
            )
            
            if result['status'] != 'success':
                return self._create_error_result(document_path, result.get('error', '处理失败'), timestamp)
            
            # 使用文档生成器生成修改内容
            if result.get('evidence_results'):
                modified_content = self.document_generator.generate_section_with_evidence(
                    section_title="完整文档",
                    original_content=full_content,
                    evidence_results=[
                        EvidenceResult(**er_data) if isinstance(er_data, dict) else er_data
                        for er_data in result['evidence_results']
                    ]
                )
            else:
                modified_content = full_content
            
            # 确保输出目录存在
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 生成输出文档
            analysis_file = os.path.join(self.output_dir, f"evidence_analysis_{timestamp}.json")
            
            # 创建兼容的分析数据
            analysis_data = {
                'metadata': {
                    'document_path': document_path,
                    'analysis_timestamp': timestamp,
                    'processing_mode': 'legacy_whole_document',
                    'analysis_version': '8.0_evidence_detector_document_generator'
                },
                'summary': result.get('statistics', {}),
                'unsupported_claims': result.get('unsupported_claims', []),
                'evidence_results': result.get('evidence_results', []),
                'processing_notes': [
                    "使用传统整体文档处理模式",
                    "基于新的evidence_detector + document_generator系统",
                    "整个文档作为单一章节处理",
                    "使用独立的文档生成器生成增强内容"
                ]
            }
            
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            enhanced_file = os.path.join(self.output_dir, f"ai_enhanced_document_{timestamp}.md")
            
            # 使用文档生成器保存修改文档
            self.document_generator.save_enhanced_document(modified_content, enhanced_file)
            
            return {
                'status': 'success',
                'document_path': document_path,
                'processing_time': result.get('processing_time', 0),
                'statistics': result.get('statistics', {}),
                'output_files': {
                    'evidence_analysis': analysis_file,
                    'enhanced_document': enhanced_file
                }
            }
            
        except Exception as e:
            return self._create_error_result(document_path, str(e), timestamp)

if __name__ == "__main__":
    # 测试用例
    pipeline = WholeDocumentPipeline()
    
    print("整体文档处理流水线已初始化")
    print("使用方法:")
    print("pipeline.process_whole_document('your_document.md')")
