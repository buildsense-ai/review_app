#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冗余分析器 - 识别文档中的冗余和重复内容
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from openai import OpenAI

# 导入共享异常
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from shared.exceptions import DocumentAnalysisError


class RedundancyAnalyzer:
    """冗余分析器 - 分析文档中的冗余内容"""
    
    def __init__(self, api_key: str = None):
        """
        初始化冗余分析器
        
        Args:
            api_key: OpenRouter API密钥
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.logger = logging.getLogger(__name__)
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        
        # 冗余分析提示词模板（从 document_reviewer.py 提取）
        self.redundancy_analysis_prompt = """
你是文档冗余分析专家。任务：找出文档中所有重复、冗余的内容并提出修改建议。

# 分析范围
只分析正文段落，忽略：图片、表格、代码块等非正文内容。

# 冗余类型
1. **跨章节重复**：不同章节说了相同的话
2. **章节内重复**：同一章节反复说同样的事

# 输出格式
只返回JSON数组，无其他文字：

**跨章节重复：**
```json
[{"subtitles": ["章节1", "章节2"], "suggestion": "在「章节1」保留...，在「章节2」删除..."}]
```

**章节内重复：**
```json
[{"subtitle": "章节名", "suggestion": "合并重复表述..."}]
```

# 关键要求
- 积极寻找：相同句子、相似表述、重复概念
- 重点关注：项目名称、地点、目标、意义等易重复内容
- 宁可多找，不要遗漏
- **必须至少提出1个优化建议，即使是微小的改进（如语言精炼、表述优化、结构调整等）**
- **禁止返回空数组[]，必须找到至少一个可改进点**

待分析文档：
$document_content

请仔细检查每个章节，找出所有重复内容，只返回JSON结果。"""
        
        self.logger.info("✅ RedundancyAnalyzer 初始化完成")
    
    def analyze_redundancy(self, document_content: str, document_title: str = "未命名文档") -> Dict[str, Any]:
        """
        分析文档中的冗余内容
        
        Args:
            document_content: 待分析的文档内容
            document_title: 文档标题
            
        Returns:
            Dict[str, Any]: 包含 modification_instructions 的分析结果
        """
        self.logger.info(f"🔍 开始冗余分析: {document_title}")
        
        try:
            # 检查文档内容长度
            if len(document_content.strip()) < 100:
                self.logger.warning("⚠️ 文档内容过短，可能无法进行有效分析")
                return {
                    "document_title": document_title,
                    "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "issues_found": 0,
                    "modification_instructions": [],
                    "analysis_summary": "文档内容过短，无需修改"
                }
            
            # 调用 API 进行冗余分析
            analysis_result = self._call_api(document_content)
            
            # 解析 API 响应
            result = self._parse_api_response(analysis_result, document_title)
            
            modification_count = len(result.get('modification_instructions', []))
            self.logger.info(f"✅ 冗余分析完成，发现 {modification_count} 个需要修改的地方")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 冗余分析失败: {e}")
            raise DocumentAnalysisError(f"冗余分析失败: {str(e)}") from e
    
    def _call_api(self, document_content: str) -> str:
        """
        调用 OpenRouter API 进行冗余分析
        
        Args:
            document_content: 文档内容
            
        Returns:
            str: API 响应内容
        """
        try:
            self.logger.info(f"📄 文档内容长度: {len(document_content)} 字符")
            
            # 构建提示词
            prompt = self.redundancy_analysis_prompt.replace('$document_content', document_content)
            
            self.logger.info(f"🤖 发送冗余分析请求到 API")
            
            # 从环境变量获取模型名称
            model_name = os.getenv('OPENROUTER_MODEL') or os.getenv('DEFAULT_MODEL') or "deepseek/deepseek-chat-v3-0324"
            
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://gauz-document-agent.com",
                    "X-Title": "GauzDocumentAgent",
                },
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            response_content = completion.choices[0].message.content.strip()
            
            self.logger.info(f"📡 API 调用成功，响应长度: {len(response_content)} 字符")
            
            return response_content
            
        except Exception as e:
            self.logger.error(f"❌ API 调用失败: {e}")
            raise
    
    def _parse_api_response(self, api_response: str, document_title: str) -> Dict[str, Any]:
        """
        解析 API 响应为分析结果格式
        
        Args:
            api_response: API 响应内容
            document_title: 文档标题
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        import re
        
        try:
            # 清理响应内容
            cleaned_response = api_response.strip()
            
            # 移除开头的代码块标记
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:].strip()
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:].strip()
            
            # 移除结尾的代码块标记
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3].strip()
            
            cleaned_response = cleaned_response.strip()
            
            # 尝试提取 JSON 内容
            json_match = re.search(r'[\[\{].*[\]\}]', cleaned_response, re.DOTALL)
            if not json_match:
                self.logger.error(f"❌ API响应中未找到有效的JSON内容")
                return {
                    "document_title": document_title,
                    "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "issues_found": 0,
                    "modification_instructions": [],
                    "analysis_summary": "API响应格式错误"
                }
            
            json_str = json_match.group(0)
            
            # 解析 JSON
            try:
                parsed_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ JSON解析失败: {e}")
                return {
                    "document_title": document_title,
                    "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "issues_found": 0,
                    "modification_instructions": [],
                    "analysis_summary": "AI分析响应格式错误，跳过分析"
                }
            
            # 构建分析结果
            modification_instructions = []
            
            if isinstance(parsed_data, list):
                for item in parsed_data:
                    # 处理单章节冗余（subtitle字段）
                    subtitle = item.get('subtitle', '')
                    # 处理多章节冗余（subtitles字段）
                    subtitles = item.get('subtitles', [])
                    suggestion = item.get('suggestion', '')
                    
                    if subtitle and suggestion:
                        # 单章节冗余
                        modification_instructions.append({
                            "subtitle": subtitle,
                            "suggestion": suggestion
                        })
                    elif subtitles and suggestion:
                        # 多章节冗余
                        modification_instructions.append({
                            "subtitles": subtitles,
                            "suggestion": suggestion
                        })
            
            issues_count = len(modification_instructions)
            
            return {
                "document_title": document_title,
                "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "issues_found": issues_count,
                "modification_instructions": modification_instructions,
                "analysis_summary": f"发现 {issues_count} 个需要优化的章节" if issues_count > 0 else "文档质量良好，无需修改"
            }
            
        except Exception as e:
            self.logger.error(f"❌ 响应解析失败: {e}")
            return {
                "document_title": document_title,
                "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "issues_found": 0,
                "modification_instructions": [],
                "analysis_summary": "响应解析失败，跳过分析"
            }

