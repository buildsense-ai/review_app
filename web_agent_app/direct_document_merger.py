#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接文档合并器 - 基于JSON数据直接生成Markdown文档

该模块接收章节处理结果JSON，直接转换为完整的Markdown文档，
无需额外的API调用，类似用户提供的代码逻辑。
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional


class DirectDocumentMerger:
    """直接文档合并器"""
    
    def __init__(self):
        """初始化合并器"""
        pass
    
    def merge_sections_to_markdown(self, section_results: Dict[str, Dict[str, Any]], 
                                 section_order: List[str] = None) -> str:
        """
        将章节处理结果直接转换为Markdown文档
        
        Args:
            section_results: 章节处理结果字典
            section_order: 章节顺序列表，如果提供则按此顺序排列
            
        Returns:
            str: 完整的Markdown文档
        """
        print("📝 开始直接合并章节为Markdown文档...")
        
        if not section_results:
            print("⚠️ 没有章节数据")
            return "# 文档生成失败\n\n没有可用的章节数据。"
        
        final_sections = []
        stats = {
            'total_sections': len(section_results),
            'skipped_sections': 0,
            'enhanced_sections': 0,
            'failed_sections': 0
        }
        
        # 如果提供了章节顺序，按顺序处理；否则按字典顺序
        if section_order:
            print(f"📋 按指定顺序处理章节: {section_order}")
            sections_to_process = [(title, section_results.get(title)) for title in section_order if title in section_results]
        else:
            print("📋 按字典顺序处理章节")
            sections_to_process = list(section_results.items())
        
        # 按顺序处理每个章节
        for section_title, result in sections_to_process:
            if result is None:
                print(f"⚠️ 章节 '{section_title}' 未找到处理结果")
                continue
                
            content = self._get_section_content(section_title, result, stats)
            if content.strip():
                final_sections.append(content.strip())
        
        # 生成最终文档
        final_document = '\n\n'.join(final_sections)
        
        # 清理文档格式
        final_document = self._clean_document_format(final_document)
        
        print(f"✅ 文档合并完成！")
        print(f"   总章节数: {stats['total_sections']}")
        print(f"   跳过章节: {stats['skipped_sections']}")
        print(f"   增强章节: {stats['enhanced_sections']}")
        print(f"   失败章节: {stats['failed_sections']}")
        
        return final_document
    
    def _get_section_content(self, section_title: str, result: Dict[str, Any], stats: Dict[str, int]) -> str:
        """
        获取章节内容
        
        Args:
            section_title: 章节标题
            result: 章节处理结果
            stats: 统计信息
            
        Returns:
            str: 章节内容
        """
        status = result.get('status', 'unknown')
        
        if status == 'skipped':
            # 跳过的章节使用原内容
            content = result.get('original_content', '')
            stats['skipped_sections'] += 1
            print(f"  ⏭️ 跳过章节: {section_title}")
            
        elif status == 'success':
            # 成功的章节使用增强内容
            content = result.get('enhanced_content', result.get('original_content', ''))
            stats['enhanced_sections'] += 1
            print(f"  ✨ 增强章节: {section_title}")
            
            # 如果有证据结果，可以在这里添加引用信息
            evidence_results = result.get('evidence_results', [])
            if evidence_results:
                content = self._add_evidence_enhancements(content, evidence_results)
                
        else:
            # 失败或未知状态的章节使用原内容
            content = result.get('original_content', f"## {section_title}\n\n处理失败")
            stats['failed_sections'] += 1
            print(f"  ⚠️ 失败章节: {section_title}")
        
        return content
    
    def _add_evidence_enhancements(self, content: str, evidence_results: List[Dict[str, Any]]) -> str:
        """
        为内容添加证据增强
        
        Args:
            content: 原始内容
            evidence_results: 证据结果列表
            
        Returns:
            str: 增强后的内容
        """
        # 这里可以根据证据结果对内容进行增强
        # 例如添加引用、数据支撑等
        enhanced_content = content
        
        for evidence in evidence_results:
            if evidence.get('processing_status') == 'success':
                enhanced_text = evidence.get('enhanced_text', '')
                if enhanced_text and enhanced_text != evidence.get('claim_text', ''):
                    # 如果有增强文本，可以替换原文中的对应部分
                    claim_text = evidence.get('claim_text', '')
                    if claim_text in enhanced_content:
                        enhanced_content = enhanced_content.replace(claim_text, enhanced_text)
        
        return enhanced_content
    
    def _clean_document_format(self, document: str) -> str:
        """
        清理文档格式
        
        Args:
            document: 原始文档
            
        Returns:
            str: 清理后的文档
        """
        # 移除多余的空行
        cleaned = re.sub(r'\n{3,}', '\n\n', document)
        
        # 确保标题前后有适当的空行
        cleaned = re.sub(r'\n(#{1,6}\s)', r'\n\n\1', cleaned)
        cleaned = re.sub(r'^(#{1,6}\s)', r'\1', cleaned)  # 文档开头的标题不需要前置空行
        
        # 移除行尾空格
        lines = cleaned.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        
        return '\n'.join(cleaned_lines).strip()
    
    def save_enhanced_document(self, document: str, output_path: str) -> str:
        """
        保存增强文档
        
        Args:
            document: 文档内容
            output_path: 输出路径
            
        Returns:
            str: 保存的文件路径
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(document)
            
            print(f"✅ 增强文档已保存: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ 保存文档失败: {e}")
            raise
    
    def generate_evidence_analysis(self, section_results: Dict[str, Dict[str, Any]], 
                                 output_path: str, timestamp: str) -> str:
        """
        生成简化的证据分析报告：只包含论断和证据结果
        
        Args:
            section_results: 章节处理结果
            output_path: 输出路径
            timestamp: 时间戳
            
        Returns:
            str: 保存的文件路径
        """
        try:
            # 收集所有章节的论断和证据结果
            all_unsupported_claims = []
            all_evidence_results = []
            
            for section_title, result in section_results.items():
                # 添加缺乏证据支撑的论断
                unsupported_claims = result.get('unsupported_claims', [])
                all_unsupported_claims.extend(unsupported_claims)
                
                # 添加证据搜索结果
                evidence_results = result.get('evidence_results', [])
                all_evidence_results.extend(evidence_results)
            
            # 简化的分析数据：只包含两个字段
            analysis_data = {
                'unsupported_claims': all_unsupported_claims,
                'evidence_results': all_evidence_results
            }
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 证据分析报告已保存: {output_path}")
            print(f"   📋 论断总数: {len(all_unsupported_claims)}")
            print(f"   🔍 证据结果: {len(all_evidence_results)}")
            
            return output_path
            
        except Exception as e:
            print(f"❌ 生成证据分析报告失败: {e}")
            raise


def main():
    """测试直接文档合并器"""
    print("🔧 直接文档合并器测试")
    
    # 示例章节结果
    sample_section_results = {
        "一、概述": {
            "status": "skipped",
            "original_content": "# 一、概述\n\n这是概述章节的内容。",
            "processing_time": 0,
            "statistics": {"claims_detected": 0, "evidence_found": 0, "claims_enhanced": 0}
        },
        "（一）项目概况": {
            "status": "success",
            "original_content": "## （一）项目概况\n\n这是项目概况的原始内容。",
            "enhanced_content": "## （一）项目概况\n\n这是项目概况的增强内容，包含了更多详细信息。",
            "processing_time": 2.5,
            "statistics": {"claims_detected": 2, "evidence_found": 3, "claims_enhanced": 2},
            "evidence_results": [
                {
                    "claim_text": "原始论断",
                    "enhanced_text": "增强后的论断",
                    "processing_status": "success",
                    "evidence_sources": ["来源1", "来源2"]
                }
            ]
        }
    }
    
    # 测试合并
    merger = DirectDocumentMerger()
    document = merger.merge_sections_to_markdown(sample_section_results)
    
    print(f"\n📄 生成的文档:")
    print("=" * 50)
    print(document)
    print("=" * 50)


if __name__ == "__main__":
    main()
