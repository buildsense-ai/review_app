#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
表格修改器 - 根据分析结果将内容转换为表格
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from shared.document_parser import DocumentParser


class TableModifier:
    """表格修改器 - 应用表格优化建议"""
    
    def __init__(self, api_key: str = None):
        """
        初始化表格修改器
        
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
        
        self.logger.info("✅ TableModifier 初始化完成")
    
    def parse_document_sections(self, markdown_content: str) -> Dict[str, Dict[str, str]]:
        """
        解析文档章节结构（使用shared的DocumentParser）
        
        Args:
            markdown_content: Markdown 文档内容
            
        Returns:
            Dict: 解析后的章节结构 {h1: {section_key: content}}
        """
        return DocumentParser.parse_sections(markdown_content, max_level=3, preserve_order=True)
    
    def apply_table_optimization(self, section_content: str, section_title: str, 
                                 table_suggestion: str) -> str:
        """
        调用 LLM 将章节内容转换为表格格式
        
        Args:
            section_content: 章节原始内容
            section_title: 章节标题
            table_suggestion: 表格优化建议
            
        Returns:
            str: 包含表格的优化后内容
        """
        self.logger.info(f"📊 开始表格优化: {section_title}")
        
        try:
            prompt = f"""你是文档格式优化专家。请将以下内容转换为Markdown表格格式。

【章节】：{section_title}
【原始内容】：
{section_content}

【表格优化建议】：
{table_suggestion}

【关键要求】：
- 识别内容中的结构化数据（如列表、枚举、数据对比等）
- 将其转换为清晰的Markdown表格格式
- 表格应包含合适的表头
- 保留原有的文字说明，将数据部分转换为表格
- 使用标准的Markdown表格语法：| 列1 | 列2 | ... |
- 表头下方使用 |---|---|---| 分隔
- 不要添加标题行（标题已经存在）
- 保持其他非结构化内容不变
- 不要使用代码块标记（如 ```markdown 或 ```），直接输出纯Markdown内容

请直接输出优化后的Markdown内容（包含表格）："""
            
            # 从环境变量获取模型名称
            model_name = os.getenv('OPENROUTER_MODEL') or os.getenv('DEFAULT_MODEL') or "deepseek/deepseek-chat-v3-0324"
            
            response = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://gauz-document-agent.com",
                    "X-Title": "GauzDocumentAgent",
                },
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000
            )
            
            modified_content = response.choices[0].message.content.strip()
            
            # 清理可能的代码块标记
            if modified_content.startswith('```markdown'):
                modified_content = modified_content[len('```markdown'):].strip()
            elif modified_content.startswith('```'):
                modified_content = modified_content[3:].strip()
            if modified_content.endswith('```'):
                modified_content = modified_content[:-3].strip()
            
            # 清理可能多余的标题行
            lines = modified_content.split('\n')
            if lines and lines[0].strip().startswith('#'):
                modified_content = '\n'.join(lines[1:]).strip()
            
            self.logger.info(f"✅ 表格优化完成: {section_title}")
            
            return modified_content
            
        except Exception as e:
            self.logger.error(f"❌ 表格优化失败 {section_title}: {e}")
            # 失败时返回原内容
            return section_content
    
    def find_section_in_parsed(self, parsed_sections: Dict[str, Dict[str, str]], 
                               target_title: str) -> Optional[tuple]:
        """
        在解析后的章节结构中查找目标章节
        
        Args:
            parsed_sections: 解析后的章节结构
            target_title: 目标章节标题
            
        Returns:
            Optional[tuple]: (h1_title, section_key, content) 或 None
        """
        # 清理目标标题
        clean_target = target_title.strip().replace('#', '').strip()
        
        for h1_title, h2_sections in parsed_sections.items():
            for section_key, content in h2_sections.items():
                # 尝试多种匹配方式
                clean_section = section_key.strip()
                
                if (clean_target == clean_section or 
                    clean_target in clean_section or 
                    clean_section in clean_target):
                    return (h1_title, section_key, content)
        
        return None
    
    def apply_modifications(self, markdown_content: str, 
                          table_opportunities: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        应用所有表格优化
        
        Args:
            markdown_content: 原始 Markdown 内容
            table_opportunities: 表格优化机会列表
            
        Returns:
            Dict: 优化后的章节数据 {section_title: {original_content, regenerated_content, suggestion, ...}}
        """
        self.logger.info(f"📊 开始应用 {len(table_opportunities)} 个表格优化")
        
        # 解析文档结构
        parsed_sections = self.parse_document_sections(markdown_content)
        
        modified_sections = {}
        
        for opportunity in table_opportunities:
            section_title = opportunity.get('section_title', '')
            table_suggestion = opportunity.get('table_opportunity', '')
            
            if not section_title or not table_suggestion:
                continue
            
            section_info = self.find_section_in_parsed(parsed_sections, section_title)
            if section_info:
                h1_title, section_key, original_content = section_info
                
                # 调用 LLM 应用表格优化
                regenerated_content = self.apply_table_optimization(
                    original_content, 
                    section_key, 
                    table_suggestion
                )
                
                full_key = f"{h1_title}:{section_key}"
                modified_sections[full_key] = {
                    "h1_title": h1_title,
                    "section_key": section_key,
                    "original_content": original_content,
                    "regenerated_content": regenerated_content,
                    "suggestion": table_suggestion,
                    "word_count": len(regenerated_content),
                    "status": "table_optimized"
                }
        
        self.logger.info(f"✅ 完成优化 {len(modified_sections)} 个章节")
        
        return modified_sections

