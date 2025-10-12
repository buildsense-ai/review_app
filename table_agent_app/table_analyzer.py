#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
表格分析器 - 识别文档中适合表格化的内容
"""

import os
import sys
import json
import logging
import re
from typing import Dict, Any, List
from datetime import datetime
from openai import OpenAI

# 导入共享异常
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from shared.exceptions import DocumentAnalysisError


class TableAnalyzer:
    """表格分析器 - 分析文档中的表格优化机会"""
    
    def __init__(self, api_key: str = None):
        """
        初始化表格分析器
        
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
        
        # 表格机会分析提示词模板（从 document_reviewer.py 提取）
        self.table_opportunity_analysis_prompt = """
# 角色
你是一名专业的文档格式优化专家，擅长识别文档中适合用表格呈现的内容。

# 任务
分析文档中是否存在适合用Markdown表格格式呈现的数字、数据等内容，特别关注以下类型：
1. 项目建设内容和规模相关数据
2. 项目建筑数据性指标
3. 人员配置情况相关数据


# 输出要求
返回JSON数组，每个对象包含：
- section_title: 章节标题
- table_opportunity: 表格优化建议

如果没有发现适合表格化的内容，返回空数组 []。

# 示例分析

## 示例 1：表格优化（文字类）

**原始文本**
```
## 六、主要建设内容

1. 综合教学楼：建筑面积 25,000 平方米，用于公共课程教学。
2. 实训大楼：建筑面积 18,000 平方米，配备实训室和实验室。
3. 学生宿舍楼：建筑面积 30,000 平方米，可容纳 3,000 名学生。
4. 食堂：建筑面积 5,000 平方米，提供 6,000 个就餐座位。
```

**期望输出**
```json
[
  {
    "section_title": "六、主要建设内容",
    "table_opportunity": "可将分项建设内容转为表格，清晰对比建筑面积与功能"
  }
]
```

待分析文档：
$document_content

请严格按照JSON格式返回结果。"""
        
        self.logger.info("✅ TableAnalyzer 初始化完成")
    
    def analyze_table_opportunities(self, document_content: str, document_title: str = "未命名文档") -> Dict[str, Any]:
        """
        分析文档中的表格优化机会
        
        Args:
            document_content: 待分析的文档内容
            document_title: 文档标题
            
        Returns:
            Dict[str, Any]: 包含 table_opportunities 的分析结果
        """
        self.logger.info(f"🔍 开始表格机会分析: {document_title}")
        
        try:
            # 检查文档内容长度
            if len(document_content.strip()) < 100:
                self.logger.warning("⚠️ 文档内容过短，可能无法进行有效分析")
                return {
                    "document_title": document_title,
                    "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "opportunities_found": 0,
                    "table_opportunities": [],
                    "analysis_summary": "文档内容过短"
                }
            
            # 调用 API 进行表格机会分析
            analysis_result = self._call_api(document_content)
            
            # 解析 API 响应
            table_opportunities = self._parse_api_response(analysis_result)
            
            opportunities_count = len(table_opportunities)
            self.logger.info(f"✅ 表格机会分析完成，发现 {opportunities_count} 个优化机会")
            
            return {
                "document_title": document_title,
                "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "opportunities_found": opportunities_count,
                "table_opportunities": table_opportunities,
                "analysis_summary": f"发现 {opportunities_count} 个表格优化机会" if opportunities_count > 0 else "未发现适合表格化的内容"
            }
            
        except Exception as e:
            self.logger.error(f"❌ 表格机会分析失败: {e}")
            raise DocumentAnalysisError(f"表格机会分析失败: {str(e)}") from e
    
    def _call_api(self, document_content: str) -> str:
        """
        调用 OpenRouter API 进行表格机会分析
        
        Args:
            document_content: 文档内容
            
        Returns:
            str: API 响应内容
        """
        try:
            self.logger.info(f"📄 文档内容长度: {len(document_content)} 字符")
            
            # 构建提示词
            prompt = self.table_opportunity_analysis_prompt.replace('$document_content', document_content)
            
            self.logger.info(f"🤖 发送表格机会分析请求到 API")
            
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
    
    def _parse_api_response(self, api_response: str) -> List[Dict[str, Any]]:
        """
        解析 API 响应为表格机会列表
        
        Args:
            api_response: API 响应内容
            
        Returns:
            List[Dict[str, Any]]: 表格机会列表
        """
        try:
            # 清理响应内容
            cleaned_response = api_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            cleaned_response = cleaned_response.strip()
            
            # 尝试提取 JSON 内容
            json_match = re.search(r'[\[\{].*[\]\}]', cleaned_response, re.DOTALL)
            if not json_match:
                self.logger.warning("⚠️ 表格机会分析响应中未找到有效的JSON内容")
                return []
            
            json_str = json_match.group(0)
            
            # 解析 JSON
            try:
                parsed_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ 表格机会分析JSON解析失败: {e}")
                return []
            
            # 处理解析结果
            table_opportunities = []
            if isinstance(parsed_data, list):
                for item in parsed_data:
                    if isinstance(item, dict):
                        table_opportunities.append({
                            "section_title": item.get('section_title', ''),
                            "table_opportunity": item.get('table_opportunity', ''),
                            "content_type": item.get('content_type', 'general'),
                            "priority": item.get('priority', 'medium')
                        })
            
            return table_opportunities
            
        except Exception as e:
            self.logger.error(f"❌ 表格机会分析响应解析失败: {e}")
            return []

