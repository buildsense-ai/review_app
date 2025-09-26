"""
Web搜索代理
为客观性论断搜索权威证据支撑
"""

import json
import time
import requests
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
import config

@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    snippet: str
    source_domain: str
    relevance_score: float
    authority_score: float  # 信源权威性评分

@dataclass
class EvidenceCollection:
    """证据收集结果"""
    claim_id: str
    search_query: str
    search_results: List[SearchResult]
    total_results: int
    search_timestamp: str
    summary: str  # AI生成的证据摘要

class WebSearchAgent:
    """Web搜索代理"""
    
    def __init__(self):
        # 权威信源域名列表
        self.authority_domains = {
            # 学术期刊和数据库
            'scholar.google.com': 0.95,
            'pubmed.ncbi.nlm.nih.gov': 0.95,
            'ieee.org': 0.9,
            'acm.org': 0.9,
            'springer.com': 0.9,
            'elsevier.com': 0.9,
            'nature.com': 0.95,
            'science.org': 0.95,
            'cell.com': 0.9,
            
            # 政府和国际组织
            'gov': 0.9,  # 政府域名
            'edu': 0.85,  # 教育机构
            'who.int': 0.95,
            'worldbank.org': 0.9,
            'un.org': 0.9,
            'oecd.org': 0.9,
            
            # 知名媒体和智库
            'reuters.com': 0.8,
            'bbc.com': 0.8,
            'economist.com': 0.85,
            'ft.com': 0.85,
            'wsj.com': 0.8,
            'nytimes.com': 0.75,
            'brookings.edu': 0.85,
            
            # 中文权威源
            'cnki.net': 0.9,
            'wanfangdata.com.cn': 0.85,
            'cas.cn': 0.9,
            'xinhuanet.com': 0.7,
            'people.com.cn': 0.7,
        }
    
    def search_evidence_for_claim(self, claim_id: str, search_keywords: List[str], 
                                claim_text: str, max_results: int = 10) -> EvidenceCollection:
        """为特定论断搜索证据"""
        print(f"🔍 为论断 {claim_id} 搜索证据...")
        
        # 构建搜索查询
        search_query = self._build_search_query(search_keywords, claim_text)
        print(f"  📝 搜索查询: {search_query}")
        
        # 执行搜索
        search_results = self._perform_web_search(search_query, max_results)
        
        # 评估结果权威性和相关性
        evaluated_results = self._evaluate_search_results(search_results, claim_text)
        
        # 生成证据摘要
        summary = self._generate_evidence_summary(claim_text, evaluated_results)
        
        evidence_collection = EvidenceCollection(
            claim_id=claim_id,
            search_query=search_query,
            search_results=evaluated_results,
            total_results=len(evaluated_results),
            search_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            summary=summary
        )
        
        print(f"  ✅ 找到 {len(evaluated_results)} 个相关结果")
        return evidence_collection
    
    def _build_search_query(self, keywords: List[str], claim_text: str) -> str:
        """构建优化的搜索查询"""
        # 基础关键词
        base_query = " ".join(keywords[:3])  # 使用前3个关键词
        
        # 添加学术搜索修饰符
        academic_modifiers = [
            "research", "study", "analysis", "report", "data", 
            "statistics", "evidence", "findings"
        ]
        
        # 根据论断类型添加特定修饰符
        if any(word in claim_text.lower() for word in ['increase', 'decrease', 'trend', 'growth']):
            base_query += " statistics data trend"
        elif any(word in claim_text.lower() for word in ['cause', 'effect', 'impact', 'influence']):
            base_query += " causal relationship impact study"
        elif any(word in claim_text.lower() for word in ['compare', 'versus', 'than', 'better']):
            base_query += " comparison analysis study"
        
        return base_query
    
    def _perform_web_search(self, query: str, max_results: int) -> List[Dict]:
        """执行Web搜索"""
        search_results = []
        
        try:
            # 使用自定义搜索API
            custom_results = self._search_custom_api(query, max_results)
            if custom_results:
                search_results.extend(custom_results)
                print(f"  ✅ 使用自定义搜索API获得 {len(custom_results)} 个结果")
            else:
                print("⚠️ 自定义搜索API未返回结果")
            
        except Exception as e:
            print(f"⚠️ 搜索过程中出现错误: {str(e)}")
            # 如果API失败，返回空结果而不是模拟结果
            print("❌ 搜索失败，无法获取证据支撑")
        
        return search_results[:max_results]
    
    def _search_custom_api(self, query: str, max_results: int) -> List[Dict]:
        """使用同事的自定义搜索API"""
        try:
            # 从配置文件获取API设置
            api_url = getattr(config, 'CUSTOM_SEARCH_API_URL', "http://43.139.19.144:8005/search")
            engines = getattr(config, 'CUSTOM_SEARCH_ENGINES', ["serp"])
            timeout = getattr(config, 'CUSTOM_SEARCH_TIMEOUT', 30)
            
            # 构建请求数据
            request_data = {
                "query": query,
                "engines": engines
            }
            
            # 发送POST请求
            response = requests.post(
                api_url, 
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=timeout
            )
            response.raise_for_status()
            
            # 解析响应
            data = response.json()
            
            results = []
            for item in data.get('items', [])[:max_results]:
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('link', ''),
                    'snippet': item.get('content', '')[:500],  # 限制摘要长度
                    'source': f"CustomAPI-{item.get('engine', 'unknown')}"
                })
            
            print(f"  🔍 自定义API返回 {len(results)} 个结果")
            return results
            
        except requests.exceptions.Timeout:
            print(f"⚠️ 自定义搜索API超时")
            return []
        except requests.exceptions.RequestException as e:
            print(f"⚠️ 自定义搜索API请求失败: {str(e)}")
            return []
        except Exception as e:
            print(f"⚠️ 自定义搜索API解析失败: {str(e)}")
            return []
    
    
    def _evaluate_search_results(self, search_results: List[Dict], claim_text: str) -> List[SearchResult]:
        """评估搜索结果的权威性和相关性"""
        evaluated_results = []
        
        for result in search_results:
            # 计算权威性评分
            authority_score = self._calculate_authority_score(result['url'])
            
            # 计算相关性评分
            relevance_score = self._calculate_relevance_score(
                result.get('title', '') + ' ' + result.get('snippet', ''),
                claim_text
            )
            
            # 提取域名
            try:
                from urllib.parse import urlparse
                domain = urlparse(result['url']).netloc.lower()
            except:
                domain = 'unknown'
            
            search_result = SearchResult(
                title=result.get('title', ''),
                url=result.get('url', ''),
                snippet=result.get('snippet', ''),
                source_domain=domain,
                relevance_score=relevance_score,
                authority_score=authority_score
            )
            
            evaluated_results.append(search_result)
        
        # 按综合评分排序（权威性 * 0.6 + 相关性 * 0.4）
        evaluated_results.sort(
            key=lambda x: x.authority_score * 0.6 + x.relevance_score * 0.4,
            reverse=True
        )
        
        return evaluated_results
    
    def _calculate_authority_score(self, url: str) -> float:
        """计算信源权威性评分"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            
            # 检查完全匹配
            if domain in self.authority_domains:
                return self.authority_domains[domain]
            
            # 检查域名后缀匹配
            for auth_domain, score in self.authority_domains.items():
                if domain.endswith(auth_domain):
                    return score
            
            # 检查特殊域名类型
            if domain.endswith('.gov'):
                return 0.9
            elif domain.endswith('.edu'):
                return 0.85
            elif domain.endswith('.org'):
                return 0.7
            elif 'university' in domain or 'college' in domain:
                return 0.8
            elif 'research' in domain or 'institute' in domain:
                return 0.75
            else:
                return 0.5  # 默认评分
                
        except:
            return 0.3  # 解析失败的默认评分
    
    def _calculate_relevance_score(self, text: str, claim_text: str) -> float:
        """计算内容相关性评分"""
        if not text or not claim_text:
            return 0.0
        
        text_lower = text.lower()
        claim_lower = claim_text.lower()
        
        # 提取关键词
        claim_words = set(claim_lower.split())
        text_words = set(text_lower.split())
        
        # 计算词汇重叠度
        common_words = claim_words.intersection(text_words)
        if len(claim_words) == 0:
            return 0.0
        
        word_overlap = len(common_words) / len(claim_words)
        
        # 检查重要短语匹配
        important_phrases = []
        if len(claim_text) > 20:
            # 提取可能的重要短语（简化实现）
            words = claim_text.split()
            for i in range(len(words) - 1):
                phrase = f"{words[i]} {words[i+1]}".lower()
                if phrase in text_lower:
                    important_phrases.append(phrase)
        
        phrase_bonus = min(len(important_phrases) * 0.2, 0.4)
        
        return min(word_overlap + phrase_bonus, 1.0)
    
    def _generate_evidence_summary(self, claim_text: str, search_results: List[SearchResult]) -> str:
        """生成证据摘要"""
        if not search_results:
            return "未找到相关证据支撑。"
        
        # 选择前3个最相关的结果
        top_results = search_results[:3]
        
        summary_parts = []
        summary_parts.append(f"针对论断「{claim_text}」，找到以下证据支撑：\n")
        
        for i, result in enumerate(top_results, 1):
            authority_level = "高" if result.authority_score >= 0.8 else "中" if result.authority_score >= 0.6 else "低"
            relevance_level = "高" if result.relevance_score >= 0.7 else "中" if result.relevance_score >= 0.4 else "低"
            
            summary_parts.append(
                f"{i}. 【权威性：{authority_level}，相关性：{relevance_level}】\n"
                f"   来源：{result.source_domain}\n"
                f"   标题：{result.title}\n"
                f"   摘要：{result.snippet}\n"
                f"   链接：{result.url}\n"
            )
        
        return "\n".join(summary_parts)
    
    def save_evidence_collection(self, evidence: EvidenceCollection, output_path: str):
        """保存证据收集结果"""
        evidence_data = asdict(evidence)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(evidence_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 证据收集结果已保存到: {output_path}")

if __name__ == "__main__":
    # 测试用例
    agent = WebSearchAgent()
    
    # 模拟搜索
    evidence = agent.search_evidence_for_claim(
        claim_id="test_1",
        search_keywords=["artificial intelligence", "productivity", "workplace"],
        claim_text="人工智能技术显著提高了工作场所的生产效率"
    )
    
    print(f"\n📊 搜索结果摘要:")
    print(evidence.summary)
    
    # 保存结果
    agent.save_evidence_collection(evidence, "test_evidence.json")
