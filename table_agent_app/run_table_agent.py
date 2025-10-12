#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Table Agent 主流程
整合分析和修改功能，实现完整的表格优化流程
"""

import os
import sys
import logging
from typing import Dict, Any
from datetime import datetime

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from table_analyzer import TableAnalyzer
from table_modifier import TableModifier

# 导入共享模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from shared.document_parser import DocumentParser


class TableAgent:
    """Table Agent - 完整的表格优化流程"""
    
    def __init__(self):
        """初始化 Table Agent"""
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 初始化组件
        self.analyzer = TableAnalyzer()
        self.modifier = TableModifier()
        
        self.logger.info("✅ TableAgent 初始化完成")
    
    def process(self, markdown_content: str, document_title: str = "文档") -> Dict[str, Any]:
        """
        处理文档表格优化的完整流程
        
        Args:
            markdown_content: Markdown 文档内容
            document_title: 文档标题
            
        Returns:
            Dict: unified_sections 格式的结果
        """
        self.logger.info(f"🚀 开始处理文档: {document_title}")
        
        try:
            # 步骤1：分析表格机会
            self.logger.info("📊 步骤1: 分析表格优化机会")
            analysis_result = self.analyzer.analyze_table_opportunities(markdown_content, document_title)
            
            table_opportunities = analysis_result.get('table_opportunities', [])
            
            if not table_opportunities:
                self.logger.info("✅ 未发现表格优化机会，返回空结果")
                return {}
            
            # 步骤2：解析文档章节
            self.logger.info("📖 步骤2: 解析文档章节")
            parsed_sections = self.modifier.parse_document_sections(markdown_content)
            
            # 步骤3：应用表格优化
            self.logger.info(f"📊 步骤3: 应用 {len(table_opportunities)} 个表格优化")
            modified_sections = self.modifier.apply_modifications(
                markdown_content, 
                table_opportunities
            )
            
            # 步骤4：构建 unified_sections 输出格式
            self.logger.info("📦 步骤4: 构建输出格式")
            unified_sections = self.build_unified_output(
                parsed_sections, 
                modified_sections,
                analysis_result
            )
            
            self.logger.info(f"🎉 处理完成！优化了 {len(modified_sections)} 个章节")
            
            return unified_sections
            
        except Exception as e:
            self.logger.error(f"❌ 处理失败: {e}")
            raise
    
    def build_unified_output(self, 
                            parsed_sections: Dict[str, Dict[str, str]], 
                            modified_sections: Dict[str, Dict[str, Any]],
                            analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建 unified_sections 格式的输出
        
        Args:
            parsed_sections: 解析后的原始章节
            modified_sections: 修改后的章节数据
            analysis_result: 分析结果
            
        Returns:
            Dict: unified_sections 格式
        """
        unified_sections = {}
        
        # 按 h1 标题组织
        for h1_title in parsed_sections.keys():
            unified_sections[h1_title] = {}
        
        # 填充修改后的章节
        for full_key, section_data in modified_sections.items():
            h1_title = section_data['h1_title']
            section_key = section_data['section_key']
            
            if h1_title not in unified_sections:
                unified_sections[h1_title] = {}
            
            unified_sections[h1_title][section_key] = {
                "original_content": section_data['original_content'],
                "suggestion": section_data['suggestion'],
                "regenerated_content": section_data['regenerated_content'],
                "word_count": section_data['word_count'],
                "status": section_data['status']
            }
        
        return unified_sections


def main():
    """测试主函数"""
    print("🧪 Table Agent 测试")
    
    # 示例文档
    sample_markdown = """# 项目概述

## 主要建设内容

1. 综合教学楼：建筑面积 25,000 平方米，用于公共课程教学。
2. 实训大楼：建筑面积 18,000 平方米，配备实训室和实验室。
3. 学生宿舍楼：建筑面积 30,000 平方米，可容纳 3,000 名学生。
"""
    
    agent = TableAgent()
    result = agent.process(sample_markdown, "测试文档")
    
    print(f"\n📊 结果: {len(result)} 个 H1 标题")
    for h1, sections in result.items():
        print(f"\n  {h1}: {len(sections)} 个章节被优化")
        for section_key in sections.keys():
            print(f"    - {section_key}")


if __name__ == "__main__":
    main()

