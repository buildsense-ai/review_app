#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冗余修改器 - 根据分析结果修改文档中的冗余内容
"""

import os
import sys
import logging
import re
from typing import Dict, Any, List, Optional
from openai import OpenAI

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from shared.document_parser import DocumentParser


class RedundancyModifier:
    """冗余修改器 - 应用冗余优化建议"""
    
    def __init__(self, api_key: str = None):
        """
        初始化冗余修改器
        
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
        
        self.logger.info("✅ RedundancyModifier 初始化完成")
    
    def parse_document_sections(self, markdown_content: str) -> Dict[str, Dict[str, str]]:
        """
        解析文档章节结构（使用shared的DocumentParser）
        
        Args:
            markdown_content: Markdown 文档内容
            
        Returns:
            Dict: 解析后的章节结构 {h1: {section_key: content}}
        """
        return DocumentParser.parse_sections(markdown_content, max_level=3, preserve_order=True)
    
    def modify_section(self, section_content: str, section_title: str, suggestion: str) -> str:
        """
        调用 LLM 修改单个章节内容
        
        Args:
            section_content: 章节原始内容
            section_title: 章节标题
            suggestion: 修改建议
            
        Returns:
            str: 修改后的内容
        """
        self.logger.info(f"🔧 开始修改章节: {section_title}")
        
        try:
            prompt = f"""你是文档优化专家。请严格按照建议修改以下内容。

【章节】：{section_title}
【原始内容】：
{section_content}

【修改建议】：
{suggestion}

【关键要求】：
- 如果建议要求删除某句话，必须完全删除
- 如果建议要求保留某内容，必须保留
- 如果建议要求合并重复内容，请精炼表述
- 保持Markdown格式
- 不要修改Markdown的主体格式，比如换行符，标题符号等等，只需要修改内容
- 不要添加标题行（标题已经存在）

请直接输出修改后的Markdown内容："""
            
            # 从环境变量获取模型名称
            model_name = os.getenv('OPENROUTER_MODEL') or os.getenv('DEFAULT_MODEL') or "deepseek/deepseek-chat-v3-0324"
            
            response = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://gauz-document-agent.com",
                    "X-Title": "GauzDocumentAgent",
                },
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000
            )
            
            modified_content = response.choices[0].message.content.strip()
            
            # 清理可能多余的标题行
            lines = modified_content.split('\n')
            if lines and lines[0].strip().startswith('#'):
                modified_content = '\n'.join(lines[1:]).strip()
            
            self.logger.info(f"✅ 章节修改完成: {section_title}")
            
            return modified_content
            
        except Exception as e:
            self.logger.error(f"❌ 章节修改失败 {section_title}: {e}")
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
                          modification_instructions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        应用所有修改指令
        
        Args:
            markdown_content: 原始 Markdown 内容
            modification_instructions: 修改指令列表
            
        Returns:
            Dict: 修改后的章节数据 {section_title: {original_content, regenerated_content, suggestion, ...}}
        """
        self.logger.info(f"📝 开始应用 {len(modification_instructions)} 个修改指令")
        
        # 解析文档结构
        parsed_sections = self.parse_document_sections(markdown_content)
        
        modified_sections = {}
        
        for instruction in modification_instructions:
            subtitle = instruction.get('subtitle')
            suggestion = instruction.get('suggestion', '')
            
            # 统一处理所有修改（单章节和跨章节都使用相同格式）
            if subtitle and suggestion:
                section_info = self.find_section_in_parsed(parsed_sections, subtitle)
                if section_info:
                    h1_title, section_key, original_content = section_info
                    
                    # 调用 LLM 修改
                    regenerated_content = self.modify_section(
                        original_content, 
                        section_key, 
                        suggestion
                    )
                    
                    full_key = f"{h1_title}:{section_key}"
                    modified_sections[full_key] = {
                        "h1_title": h1_title,
                        "section_key": section_key,
                        "original_content": original_content,
                        "regenerated_content": regenerated_content,
                        "suggestion": suggestion,
                        "word_count": len(regenerated_content),
                        "status": "modified"
                    }
        
        self.logger.info(f"✅ 完成修改 {len(modified_sections)} 个章节")
        
        return modified_sections

