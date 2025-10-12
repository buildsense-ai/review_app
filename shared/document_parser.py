#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一的文档解析器
支持解析Markdown文档的1、2、3级标题结构
"""

from typing import Dict, List
from collections import OrderedDict


class DocumentParser:
    """文档解析器 - 统一解析Markdown文档结构"""
    
    @staticmethod
    def parse_sections(content: str, max_level: int = 3, preserve_order: bool = True) -> Dict[str, Dict[str, str]]:
        """
        统一的文档解析函数，支持1-3级标题
        
        Args:
            content: Markdown文档内容
            max_level: 最大标题级别 (1-3)
            preserve_order: 是否保持章节顺序
            
        Returns:
            Dict[str, Dict[str, str]]: 嵌套的章节结构
            格式: {h1: {section_key: content}}
            其中 section_key 为 "h2" 或 "h2 > h3"
        """
        if preserve_order:
            sections = OrderedDict()
        else:
            sections = {}
        
        lines = content.split('\n')
        current_h1 = None
        current_h2 = None
        current_h3 = None
        current_content = []
        section_order = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # 检查是否是1级标题
            if line_stripped.startswith('# ') and not line_stripped.startswith('## '):
                # 保存前一个章节
                if current_h1 and current_h2:
                    if current_h1 not in sections:
                        sections[current_h1] = OrderedDict() if preserve_order else {}
                    
                    # 构建章节键（如果有h3，合并为 "h2 > h3"）
                    section_key = f"{current_h2} > {current_h3}" if current_h3 else current_h2
                    sections[current_h1][section_key] = '\n'.join(current_content).strip()
                
                # 开始新的H1
                current_h1 = line_stripped[2:].strip()
                current_h2 = None
                current_h3 = None
                current_content = [line] if max_level >= 1 else []
                section_order.append(current_h1)
                
            # 检查是否是2级标题
            elif line_stripped.startswith('## ') and not line_stripped.startswith('### '):
                # 保存前一个章节
                if current_h1 and current_h2:
                    if current_h1 not in sections:
                        sections[current_h1] = OrderedDict() if preserve_order else {}
                    
                    section_key = f"{current_h2} > {current_h3}" if current_h3 else current_h2
                    sections[current_h1][section_key] = '\n'.join(current_content).strip()
                
                # 开始新的H2
                current_h2 = line_stripped[3:].strip()
                current_h3 = None
                current_content = [line] if max_level >= 2 else []
                
            # 检查是否是3级标题
            elif line_stripped.startswith('### ') and max_level >= 3:
                # 保存前一个H3章节
                if current_h1 and current_h2 and current_h3:
                    if current_h1 not in sections:
                        sections[current_h1] = OrderedDict() if preserve_order else {}
                    
                    section_key = f"{current_h2} > {current_h3}"
                    sections[current_h1][section_key] = '\n'.join(current_content).strip()
                
                # 开始新的H3
                current_h3 = line_stripped[4:].strip()
                current_content = [line]
                
            else:
                # 普通内容行
                if current_h2:  # 只有在H2或H3下才收集内容
                    current_content.append(line)
                elif not current_h1 and line.strip():
                    # 文档开头的内容（在第一个标题之前）
                    if "文档开头" not in sections:
                        sections["文档开头"] = OrderedDict() if preserve_order else {}
                    current_content.append(line)
        
        # 保存最后一个章节
        if current_h1 and current_h2:
            if current_h1 not in sections:
                sections[current_h1] = OrderedDict() if preserve_order else {}
            
            section_key = f"{current_h2} > {current_h3}" if current_h3 else current_h2
            sections[current_h1][section_key] = '\n'.join(current_content).strip()
        
        # 将章节顺序信息存储在sections对象中
        if preserve_order:
            sections._section_order = section_order
        
        return sections
    
    @staticmethod
    def parse_flat_sections(content: str, level: int = 1) -> Dict[str, str]:
        """
        扁平化解析文档，按指定级别标题分割
        
        Args:
            content: Markdown文档内容
            level: 标题级别 (1-3)
            
        Returns:
            Dict[str, str]: {section_title: section_content}
        """
        sections = OrderedDict()
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        # 根据级别确定标题标记
        if level == 1:
            header_prefix = '# '
            next_level_prefix = '##'
        elif level == 2:
            header_prefix = '## '
            next_level_prefix = '###'
        else:  # level == 3
            header_prefix = '### '
            next_level_prefix = '####'
        
        for line in lines:
            line_stripped = line.strip()
            
            # 检查是否是目标级别的标题
            if line_stripped.startswith(header_prefix) and not line_stripped.startswith(next_level_prefix):
                # 保存上一个章节
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # 开始新章节
                current_section = line_stripped[len(header_prefix):].strip()
                current_content = [line]
            else:
                if current_section:
                    current_content.append(line)
                else:
                    # 如果还没有遇到标题，将内容添加到临时章节
                    if "文档开头" not in sections:
                        current_section = "文档开头"
                        current_content = [line]
        
        # 保存最后一个章节
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    @staticmethod
    def extract_section_content(full_content: str, section_title: str, fuzzy_match: bool = True) -> str:
        """
        从完整文档中提取指定章节的内容
        
        Args:
            full_content: 完整文档内容
            section_title: 章节标题
            fuzzy_match: 是否使用模糊匹配
            
        Returns:
            str: 章节内容，如果未找到返回空字符串
        """
        import re
        
        # 清理章节标题
        clean_title = section_title.replace('##', '').replace('#', '').strip()
        
        # 尝试匹配标题（支持1-3级）
        patterns = [
            rf'^###\s+{re.escape(clean_title)}\s*$',  # 三级标题
            rf'^##\s+{re.escape(clean_title)}\s*$',   # 二级标题
            rf'^#\s+{re.escape(clean_title)}\s*$',    # 一级标题
        ]
        
        lines = full_content.split('\n')
        start_idx = None
        title_level = None
        
        # 查找标题位置
        for i, line in enumerate(lines):
            for level, pattern in enumerate(patterns, start=3):
                if re.match(pattern, line.strip(), re.IGNORECASE if fuzzy_match else 0):
                    start_idx = i
                    title_level = level
                    break
            if start_idx is not None:
                break
        
        if start_idx is None:
            # 尝试模糊匹配
            if fuzzy_match:
                for i, line in enumerate(lines):
                    if clean_title in line and line.strip().startswith('#'):
                        start_idx = i
                        # 确定标题级别
                        if line.strip().startswith('### '):
                            title_level = 3
                        elif line.strip().startswith('## '):
                            title_level = 2
                        elif line.strip().startswith('# '):
                            title_level = 1
                        break
        
        if start_idx is None:
            return ""
        
        # 提取内容直到下一个同级或更高级标题
        content_lines = [lines[start_idx]]
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            # 检查是否遇到同级或更高级标题
            if line.strip().startswith('#'):
                if title_level == 3 and line.strip().startswith('### '):
                    break
                elif title_level == 2 and line.strip().startswith('## '):
                    break
                elif title_level == 1 and line.strip().startswith('# ') and not line.strip().startswith('## '):
                    break
            content_lines.append(line)
        
        return '\n'.join(content_lines).strip()

