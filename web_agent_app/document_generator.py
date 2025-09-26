#!/usr/bin/env python3
"""
文档生成器 - 独立的文档增强和生成模块
基于证据检测结果生成增强文档
"""

import json
import os
import re
import time
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
import config

from evidence_detector import UnsupportedClaim, EvidenceResult

class DocumentGenerator:
    """文档生成器"""
    
    def __init__(self):
        """初始化文档生成器"""
        self.client = OpenAI(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=config.OPENROUTER_API_KEY
        )
        self.model = config.MODEL_NAME
        self.max_workers = 5  # 并行处理最大工作线程数
        self.thread_lock = threading.Lock()
    
    
    # 移除了并行处理方法，现在直接使用JSON数据转换
    
    # 移除了单章节处理方法，现在直接使用JSON数据
    
    # 移除了generate_section_with_evidence方法，现在直接使用JSON数据
    
    def generate_enhanced_document(self, section_results: Dict[str, Dict[str, Any]]) -> str:
        """
        基于章节处理结果生成完整的修改文档（直接JSON到Markdown转换）
        
        Args:
            section_results: 章节处理结果字典
            
        Returns:
            str: 修改后的完整文档
        """
        print("📝 开始生成修改后的完整文档（直接转换）...")
        
        if not section_results:
            print("⚠️ 没有任何章节数据")
            return "# 文档生成失败\n\n没有可用的章节数据。"
        
        # 直接从JSON数据构建Markdown，无需API调用
        final_sections = []
        skipped_count = 0
        enhanced_count = 0
        
        for section_title, result in section_results.items():
            status = result.get('status', 'unknown')
            
            if status == 'skipped' or status == 'success':
                # 对于跳过的章节，使用原内容
                if status == 'skipped':
                    content = result.get('original_content', '')
                    skipped_count += 1
                    print(f"  ⏭️ 使用原内容: {section_title}")
                else:
                    # 对于成功的章节，使用增强内容（如果有的话）
                    content = result.get('enhanced_content', result.get('original_content', ''))
                    enhanced_count += 1
                    print(f"  ✨ 使用增强内容: {section_title}")
                
                if content.strip():
                    final_sections.append(content.strip())
            else:
                # 失败的章节使用原内容作为备选
                original_content = result.get('original_content', f"## {section_title}\n\n处理失败")
                final_sections.append(original_content)
                print(f"  ⚠️ 使用备选内容: {section_title}")
        
        print(f"📝 文档生成完成！跳过章节: {skipped_count}, 增强章节: {enhanced_count}")
        return '\n\n'.join(final_sections)
    
    # 移除了generate_whole_document_from_analysis方法，现在使用直接合并器
    
    # 移除了save_enhanced_document方法，现在使用直接合并器的保存功能

# 移除了测试代码
