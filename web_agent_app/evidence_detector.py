#!/usr/bin/env python3
"""
证据检测器 - 统一的论断检测和证据填充系统
替代原有的claim_detector.py和evidence_analyzer.py
主要逻辑：AI找出所有没有论据的claims -> websearch找证据 -> 填入文档
"""

import json
import re
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from openai import OpenAI
import config

# 配置HTTP请求日志
def setup_http_logging():
    """设置HTTP请求日志"""
    if getattr(config, 'ENABLE_HTTP_LOGS', True):
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.INFO)
        
        if not httpx_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            httpx_logger.addHandler(handler)

setup_http_logging()

@dataclass
class UnsupportedClaim:
    """缺乏证据支撑的论断"""
    claim_id: str
    claim_text: str
    section_title: str
    claim_type: str  # 'factual', 'statistical', 'causal', 'comparative', 'historical'
    confidence_level: float  # 0.0-1.0，表示需要证据支撑的紧迫程度
    context: str  # 论断的上下文
    search_keywords: List[str]  # 搜索关键词
    original_position: int  # 在原文中的位置（行号或段落号）

@dataclass
class EvidenceResult:
    """证据搜索结果"""
    claim_id: str
    claim_text: str
    section_title: str
    search_query: str
    evidence_sources: List[Dict[str, Any]]  # 搜索到的证据来源
    enhanced_text: str  # 增强后的文本（包含证据）
    confidence_score: float  # 证据可信度评分
    processing_status: str  # 'success', 'partial', 'failed'

class EvidenceDetector:
    """统一的证据检测器"""
    
    def __init__(self):
        """初始化证据检测器"""
        self.client = OpenAI(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=config.OPENROUTER_API_KEY
        )
        self.model = config.MODEL_NAME
        
        # 并行处理配置
        self.max_workers = getattr(config, 'MAX_WORKERS', 5)
        self.thread_lock = threading.Lock()
        
        # 导入web搜索代理
        from web_search_agent import WebSearchAgent
        self.web_search_agent = WebSearchAgent()
    
    def process_section(self, section_title: str, section_content: str, 
                       max_claims: int = 10) -> Dict[str, Any]:
        """
        处理单个章节：检测缺乏证据的论断 -> 搜索证据 -> 生成增强文档
        
        Args:
            section_title: 章节标题
            section_content: 章节内容
            max_claims: 最大处理论断数
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        print(f"🔍 处理章节: {section_title}")
        start_time = time.time()
        
        try:
            # 第一步：检测缺乏证据支撑的论断
            unsupported_claims = self._detect_unsupported_claims(section_title, section_content)
            
            if len(unsupported_claims) > max_claims:
                # 按置信度排序，取前N个
                unsupported_claims.sort(key=lambda x: x.confidence_level, reverse=True)
                unsupported_claims = unsupported_claims[:max_claims]
                print(f"  📊 限制处理论断数量为 {max_claims} 个（按置信度排序）")
            
            if not unsupported_claims:
                print(f"  ✅ 章节 '{section_title}' 未发现需要证据支撑的论断")
                return {
                    'section_title': section_title,
                    'status': 'success',
                    'message': '未发现需要证据支撑的论断',
                    'unsupported_claims': [],
                    'evidence_results': [],
                    'enhanced_content': section_content,
                    'original_content': section_content,
                    'processing_time': time.time() - start_time,
                    'statistics': {
                        'claims_detected': 0,
                        'evidence_found': 0,
                        'claims_enhanced': 0
                    }
                }
            
            print(f"  📋 检测到 {len(unsupported_claims)} 个缺乏证据支撑的论断")
            
            # 第二步：并行搜索证据
            evidence_results = self._batch_search_evidence(unsupported_claims)
            
            # 第三步：生成增强内容（将证据整合到原文中）
            enhanced_content = self._enhance_content_with_evidence(section_content, evidence_results)
            
            # 统计信息
            successful_evidence = sum(1 for er in evidence_results if er.processing_status == 'success')
            total_evidence_sources = sum(len(er.evidence_sources) for er in evidence_results)
            
            processing_time = time.time() - start_time
            
            # 简化日志输出，详细统计由上层流水线处理
            # print(f"  ✅ 章节 '{section_title}' 处理完成")
            # print(f"     - 检测论断: {len(unsupported_claims)} 个")
            # print(f"     - 成功搜索: {successful_evidence} 个")
            # print(f"     - 证据来源: {total_evidence_sources} 条")
            # print(f"     - 处理时间: {processing_time:.2f} 秒")
            
            return {
                'section_title': section_title,
                'status': 'success',
                'message': f'成功处理 {len(unsupported_claims)} 个论断',
                'unsupported_claims': [asdict(claim) for claim in unsupported_claims],
                'evidence_results': [asdict(result) for result in evidence_results],
                'enhanced_content': enhanced_content,
                'original_content': section_content,
                'processing_time': processing_time,
                'statistics': {
                    'claims_detected': len(unsupported_claims),
                    'evidence_found': total_evidence_sources,
                    'claims_enhanced': successful_evidence,
                    'success_rate': (successful_evidence / len(unsupported_claims) * 100) if unsupported_claims else 0
                }
            }
            
        except Exception as e:
            error_msg = f"处理章节 '{section_title}' 时出错: {str(e)}"
            print(f"  ❌ {error_msg}")
            
            return {
                'section_title': section_title,
                'status': 'failed',
                'message': error_msg,
                'unsupported_claims': [],
                'evidence_results': [],
                'enhanced_content': section_content,
                'original_content': section_content,
                'processing_time': time.time() - start_time,
                'error': str(e)
            }
    
    def _detect_unsupported_claims(self, section_title: str, section_content: str) -> List[UnsupportedClaim]:
        """检测章节中缺乏证据支撑的论断"""
        
        prompt = f"""你是一个专业的学术写作分析专家。请仔细分析以下章节内容，找出所有缺乏充分证据支撑的论断。

章节标题：{section_title}

章节内容：
{section_content}

对于每个论断，请评估：
- 搜索关键词：建议用于搜索证据的关键词（3-5个）
- 上下文：论断在文中的上下文
- 章节位置：确保标记论断所在的章节

请严格按照以下JSON格式返回结果：

{{
    "unsupported_claims": [
        {{
            "claim_text": "具体的论断文本",
            "context": "论断的上下文背景",
            "search_keywords": ["关键词1", "关键词2", "关键词3"],
            "section_title": "{section_title}"
        }}
    ]
}}

重要要求：
1. 只返回有效的JSON格式，不要添加其他解释
2. 只识别真正缺乏证据支撑的论断
3. section_title字段必须与提供的章节标题完全一致
4. 如果没有发现缺乏证据的论断，返回空数组
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000
            )
            
            result_text = response.choices[0].message.content.strip()
            print(f"    🔍 AI检测结果预览: {result_text[:150]}...")
            
            # 解析JSON结果
            cleaned_text = self._clean_json_text(result_text)
            try:
                result_json = json.loads(cleaned_text)
            except json.JSONDecodeError as json_error:
                print(f"    ⚠️ JSON解析失败: {str(json_error)}")
                print(f"    📄 原始响应: {result_text[:500]}...")
                print(f"    🧹 清理后内容: {cleaned_text[:500]}...")
                # 尝试从响应中提取可能的JSON部分
                try:
                    # 查找JSON对象的开始和结束
                    start_idx = cleaned_text.find('{')
                    if start_idx != -1:
                        # 找到最后一个完整的JSON对象
                        brace_count = 0
                        end_idx = -1
                        for i in range(start_idx, len(cleaned_text)):
                            if cleaned_text[i] == '{':
                                brace_count += 1
                            elif cleaned_text[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break
                        
                        if end_idx != -1:
                            json_part = cleaned_text[start_idx:end_idx]
                            result_json = json.loads(json_part)
                            print(f"    ✅ 成功提取JSON片段")
                        else:
                            raise json_error
                    else:
                        raise json_error
                except:
                    print(f"    ❌ 无法修复JSON，返回空结果")
                    return []
            
            claims = []
            for i, claim_data in enumerate(result_json.get('unsupported_claims', [])):
                # 确保使用正确的章节标题
                claim_section_title = claim_data.get('section_title', section_title)
                
                claim = UnsupportedClaim(
                    claim_id=f"{claim_section_title}_claim_{i+1}",
                    claim_text=claim_data['claim_text'],
                    section_title=claim_section_title,
                    claim_type='factual',  # 默认类型
                    confidence_level=0.8,  # 默认置信度
                    context=claim_data.get('context', ''),
                    search_keywords=claim_data.get('search_keywords', []),
                    original_position=i+1
                )
                claims.append(claim)
            
            return claims
            
        except Exception as e:
            print(f"    ❌ 检测论断时出错: {str(e)}")
            return []
    
    def _batch_search_evidence(self, unsupported_claims: List[UnsupportedClaim]) -> List[EvidenceResult]:
        """批量搜索证据"""
        print(f"    🔍 开始为 {len(unsupported_claims)} 个论断搜索证据...")
        
        evidence_results = []
        
        # 使用线程池并行搜索
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(unsupported_claims))) as executor:
            future_to_claim = {
                executor.submit(self._search_evidence_for_claim, claim): claim
                for claim in unsupported_claims
            }
            
            completed = 0
            for future in as_completed(future_to_claim):
                claim = future_to_claim[future]
                try:
                    evidence_result = future.result()
                    evidence_results.append(evidence_result)
                    completed += 1
                    
                    with self.thread_lock:
                        print(f"      ✅ 论断 {completed}/{len(unsupported_claims)} 证据搜索完成")
                        if evidence_result.processing_status == 'success':
                            print(f"         找到 {len(evidence_result.evidence_sources)} 条证据")
                        else:
                            print(f"         搜索失败: {evidence_result.processing_status}")
                
                except Exception as e:
                    with self.thread_lock:
                        print(f"      ❌ 论断 '{claim.claim_id}' 搜索异常: {str(e)}")
                    # 创建失败结果
                    evidence_results.append(EvidenceResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.claim_text,
                        section_title=claim.section_title,
                        search_query='',
                        evidence_sources=[],
                        enhanced_text=claim.claim_text,
                        confidence_score=0.0,
                        processing_status='failed'
                    ))
        
        return evidence_results
    
    def _search_evidence_for_claim(self, claim: UnsupportedClaim) -> EvidenceResult:
        """为单个论断搜索证据"""
        try:
            # 构建搜索查询
            search_query = ' '.join(claim.search_keywords[:3])  # 使用前3个关键词
            
            # 使用web搜索代理搜索证据
            evidence_collection = self.web_search_agent.search_evidence_for_claim(
                claim_id=claim.claim_id,
                search_keywords=claim.search_keywords,
                claim_text=claim.claim_text,
                max_results=5  # 每个论断最多5个结果
            )
            
            # 转换搜索结果格式
            evidence_sources = []
            for search_result in evidence_collection.search_results:
                evidence_sources.append({
                    'title': search_result.title,
                    'url': search_result.url,
                    'snippet': search_result.snippet,
                    'source_domain': search_result.source_domain,
                    'relevance_score': search_result.relevance_score,
                    'authority_score': search_result.authority_score
                })
            
            # 计算置信度评分
            if evidence_sources:
                confidence_score = sum(es.get('relevance_score', 0) for es in evidence_sources) / len(evidence_sources)
                processing_status = 'success'
                enhanced_text = claim.claim_text  # 不在这里生成增强文本
            else:
                confidence_score = 0.0
                processing_status = 'failed'
                enhanced_text = claim.claim_text
            
            return EvidenceResult(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                section_title=claim.section_title,
                search_query=search_query,
                evidence_sources=evidence_sources,
                enhanced_text=enhanced_text,
                confidence_score=confidence_score,
                processing_status=processing_status
            )
            
        except Exception as e:
            print(f"      ⚠️ 搜索论断 '{claim.claim_id}' 证据时出错: {str(e)}")
            return EvidenceResult(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                section_title=claim.section_title,
                search_query='',
                evidence_sources=[],
                enhanced_text=claim.claim_text,
                confidence_score=0.0,
                processing_status='failed'
            )
    
    
    def _enhance_content_with_evidence(self, original_content: str, evidence_results: List[EvidenceResult]) -> str:
        """
        将证据整合到原始内容中，生成增强版本
        
        Args:
            original_content: 原始章节内容
            evidence_results: 证据搜索结果列表
            
        Returns:
            str: 增强后的内容
        """
        # 筛选有效的证据结果
        valid_evidence = [er for er in evidence_results if er.processing_status == 'success' and er.evidence_sources]
        
        if not valid_evidence:
            return original_content
        
        try:
            # 构建证据增强提示
            evidence_text = []
            for er in valid_evidence:
                if er.evidence_sources:
                    sources_text = "\n".join([f"- {source['snippet']} (来源: {source['source_domain']})" 
                                            for source in er.evidence_sources[:3]])  # 只使用前3个证据
                    evidence_text.append(f"""
论断: {er.claim_text}
搜索到的证据:
{sources_text}
""")
            
            if not evidence_text:
                return original_content
            
            evidence_summary = "\n".join(evidence_text)
            
            prompt = f"""你是一位专业的学术写作专家。请基于提供的证据，对以下章节内容进行适当的增强和改进。

原始内容:
{original_content}

证据信息:
{evidence_summary}

请按照以下要求修改章节内容：

1. **保持原有的章节结构和格式**
2. **基于证据信息，对相关论断进行适当的增强**：
   - 可以添加具体的数据、案例或引用
   - 可以补充相关的政策法规或标准
   - 用粗体标记新增或修改的内容：**新增内容**
3. **保持学术写作的严谨性和客观性**
4. **确保修改后的内容与原文风格一致**
5. **不要删除原有的重要信息**

请直接输出修改后的完整章节内容："""

            # 调用LLM生成增强内容
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            enhanced_content = response.choices[0].message.content.strip()
            
            # 基本清理和验证
            if enhanced_content and len(enhanced_content) > 50:
                return enhanced_content
            else:
                return original_content
                
        except Exception as e:
            print(f"    ⚠️ 生成增强内容时出错: {str(e)}")
            return original_content

    def _clean_json_text(self, text: str) -> str:
        """清理JSON文本中的无效字符"""
        if not text:
            return text
        
        # 移除控制字符（保留换行符和制表符）
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        text = text.replace('\ufeff', '')
        
        # 移除markdown代码块标记
        text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'```.*?$', '', text, flags=re.MULTILINE)
        
        # 移除可能的前缀文本
        text = re.sub(r'^[^{]*?(?={)', '', text)
        
        # 修复单引号为双引号（更精确的匹配）
        text = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)':", r'"\1":', text)
        text = re.sub(r":\s*'([^'\\]*(?:\\.[^'\\]*)*)'", r': "\1"', text)
        
        # 修复常见的JSON格式问题
        text = re.sub(r',\s*}', '}', text)  # 移除多余的逗号
        text = re.sub(r',\s*]', ']', text)  # 移除数组中多余的逗号
        
        # 尝试提取完整的JSON对象
        try:
            brace_count = 0
            start_pos = -1
            end_pos = -1
            
            for i, char in enumerate(text):
                if char == '{':
                    if start_pos == -1:
                        start_pos = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_pos != -1:
                        end_pos = i
                        break
            
            if start_pos != -1 and end_pos != -1:
                text = text[start_pos:end_pos+1]
        except:
            pass
        
        return text.strip()
    

if __name__ == "__main__":
    # 测试代码
    print("🧪 证据检测器测试")
    
    detector = EvidenceDetector()
    
    # 创建测试章节
    test_section_title = "人工智能在医疗领域的应用"
    test_section_content = """
人工智能技术正在革命性地改变医疗行业。AI在医学影像诊断中的准确率已经超过90%。

深度学习算法能够识别X光片、CT扫描和MRI图像中的异常情况，帮助医生更快速、准确地诊断疾病。
机器学习算法在癌症病理诊断中表现出色，能够在几分钟内完成通常需要数小时的分析工作。

AI系统能够分析患者的基因信息、病史和生活方式，为每个患者制定个性化的治疗方案。
人工智能大大缩短了新药研发周期，从传统的10-15年缩短到5-7年。
"""
    
    # 执行测试
    result = detector.process_section(test_section_title, test_section_content)
    
    print(f"✅ 测试完成")
    print(f"   状态: {result['status']}")
    print(f"   检测论断: {result['statistics']['claims_detected']} 个")
    print(f"   找到证据: {result['statistics']['evidence_found']} 条")
    print(f"   处理时间: {result['processing_time']:.2f} 秒")
