#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档修改器 - 基于全局分析结果修改Markdown文档

该模块接收完整的Markdown文档和全局分析JSON，
根据分析结果对原文档进行智能修改，返回优化后的Markdown文档。
"""

import json
import logging
import os
import re
import time
from typing import Dict, Any, List, Optional
from openai import OpenAI
from datetime import datetime


class ColoredLogger:
    """彩色日志记录器"""
    COLORS = {
        'RESET': '\033[0m', 'BLUE': '\033[94m', 'GREEN': '\033[92m', 
        'YELLOW': '\033[93m', 'RED': '\033[91m', 'PURPLE': '\033[95m', 
        'CYAN': '\033[96m', 'WHITE': '\033[97m',
    }
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _colorize(self, text: str, color: str) -> str:
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['RESET']}"
    
    def info(self, message: str): 
        self.logger.info(message)
    
    def error(self, message: str): 
        self.logger.error(message)
    
    def warning(self, message: str): 
        self.logger.warning(message)
    
    def debug(self, message: str): 
        self.logger.debug(message)
    
    def modification_start(self, title: str): 
        self.logger.info(self._colorize(f"\n🔧 开始文档修改: {title}", 'PURPLE'))
    
    def modification_complete(self, title: str, sections_modified: int): 
        self.logger.info(self._colorize(f"✅ 文档'{title}'修改完成 | 修改章节数: {sections_modified}", 'WHITE'))
    
    def section_modified(self, section_title: str): 
        self.logger.info(self._colorize(f"📝 章节已修改: {section_title}", 'GREEN'))
    
    def api_call(self, content: str): 
        self.logger.info(self._colorize(f"🤖 API调用: {content}", 'GREEN'))
    
    def api_response(self, content: str): 
        self.logger.info(self._colorize(f"📡 API响应: {content}", 'CYAN'))


class DocumentModifier:
    """文档修改器"""
    
    def __init__(self, api_key: str = None):
        """
        初始化文档修改器
        
        Args:
            api_key: OpenRouter API密钥
        """
        # 如果没有提供API key，从环境变量获取
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.colored_logger = ColoredLogger(__name__)
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        
        self.colored_logger.info("✅ DocumentModifier 初始化完成")
    
    def modify_document(self, original_markdown: str, analysis_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于分析结果修改文档
        
        Args:
            original_markdown: 原始Markdown文档内容
            analysis_json: 全局分析结果JSON
            
        Returns:
            Dict[str, Any]: 修改结果，包含修改后的markdown和统计信息
        """
        document_title = analysis_json.get('document_title', '未命名文档')
        modification_instructions = analysis_json.get('modification_instructions', [])
        table_opportunities = analysis_json.get('table_opportunities', [])
        
        self.colored_logger.modification_start(document_title)
        
        if not modification_instructions and not table_opportunities:
            self.colored_logger.info("📋 无需修改，返回原文档")
            return {
                "modified_markdown": original_markdown,
                "document_title": document_title,
                "modification_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sections_modified": 0,
                "tables_optimized": 0,
                "modifications_applied": [],
                "table_optimizations_applied": [],
                "overall_improvement": "文档质量良好，无需修改"
            }
        
        try:
            # 执行完整文档修改（一次性处理整个文档）
            modified_markdown, modifications_applied, table_optimizations_applied = self._apply_complete_document_optimization(
                original_markdown, modification_instructions, table_opportunities
            )
            
            sections_modified = len(modifications_applied)
            tables_optimized = len(table_optimizations_applied)
            
            self.colored_logger.modification_complete(document_title, sections_modified)
            if tables_optimized > 0:
                self.colored_logger.info(f"📊 表格优化完成，优化了 {tables_optimized} 个表格")
            
            return {
                "modified_markdown": modified_markdown,
                "document_title": document_title,
                "modification_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sections_modified": sections_modified,
                "tables_optimized": tables_optimized,
                "modifications_applied": modifications_applied,
                "table_optimizations_applied": table_optimizations_applied,
                "overall_improvement": f"成功优化了 {sections_modified} 个章节和 {tables_optimized} 个表格，提升了文档质量"
            }
            
        except Exception as e:
            self.colored_logger.error(f"❌ 文档修改失败: {e}")
            return {
                "modified_markdown": original_markdown,
                "document_title": document_title,
                "modification_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sections_modified": 0,
                "tables_optimized": 0,
                "modifications_applied": [],
                "table_optimizations_applied": [],
                "overall_improvement": f"修改失败: {str(e)}",
                "error": str(e)
            }
    
    # 旧的按章节处理方法已移除，现在使用 _apply_complete_document_optimization 进行全文处理
    
    def _apply_complete_document_optimization(self, original_markdown: str, 
                                            modification_instructions: List[Dict[str, Any]], 
                                            table_opportunities: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        一次性处理整个文档的优化（内容修改 + 表格优化）
        
        Args:
            original_markdown: 原始Markdown内容
            modification_instructions: 修改指令列表
            table_opportunities: 表格优化机会列表
            
        Returns:
            tuple: (优化后的markdown内容, 应用的修改列表, 应用的表格优化列表)
        """
        try:
            self.colored_logger.info("🔧 开始完整文档优化...")
            
            # 构建完整的优化指令
            optimization_prompt = self._build_complete_optimization_prompt(
                original_markdown, modification_instructions, table_opportunities
            )
            
            # 调用LLM进行完整文档优化
            optimized_markdown = self._optimize_complete_document_with_llm(optimization_prompt)
            
            # 构建应用的修改列表
            modifications_applied = []
            for instruction in modification_instructions:
                modifications_applied.append({
                    "subtitle": instruction.get('subtitle', ''),
                    "suggestion": instruction.get('suggestion', ''),
                    "status": "completed"
                })
            
            # 构建应用的表格优化列表
            table_optimizations_applied = []
            for opportunity in table_opportunities:
                table_optimizations_applied.append({
                    "section_title": opportunity.get('section_title', ''),
                    "table_opportunity": opportunity.get('table_opportunity', ''),
                    "status": "completed"
                })
            
            self.colored_logger.info(f"✅ 完整文档优化完成")
            
            return optimized_markdown, modifications_applied, table_optimizations_applied
            
        except Exception as e:
            self.colored_logger.error(f"❌ 完整文档优化失败: {e}")
            return original_markdown, [], []
    
    def _build_complete_optimization_prompt(self, original_markdown: str, 
                                          modification_instructions: List[Dict[str, Any]], 
                                          table_opportunities: List[Dict[str, Any]]) -> str:
        """
        构建完整文档优化的提示词
        
        Args:
            original_markdown: 原始文档内容
            modification_instructions: 修改指令
            table_opportunities: 表格优化机会
            
        Returns:
            str: 完整的优化提示词
        """
        # 构建修改指令部分
        modification_text = ""
        if modification_instructions:
            modification_text = "\n【内容优化指令】：\n"
            for i, instruction in enumerate(modification_instructions, 1):
                subtitle = instruction.get('subtitle', '')
                suggestion = instruction.get('suggestion', '')
                # 使用字符串拼接避免f-string格式化问题
                modification_text += str(i) + ". 章节「" + str(subtitle) + "」: " + str(suggestion) + "\n"
        
        # 构建表格优化指令部分
        table_text = ""
        if table_opportunities:
            table_text = "\n【表格优化指令】：\n"
            for i, opportunity in enumerate(table_opportunities, 1):
                section_title = opportunity.get('section_title', '')
                table_opportunity = opportunity.get('table_opportunity', '')
                # 使用字符串拼接避免f-string格式化问题
                table_text += str(i) + ". 章节「" + str(section_title) + "」: " + str(table_opportunity) + "\n"
        
        # 使用字符串拼接避免f-string格式化问题
        prompt = """你是一位专业的文档优化专家，请对以下完整文档进行优化。

**【核心原则】：这是文档优化任务，不是内容删减任务。必须保持文档的完整性和专业性。**

【优化任务】：
1. 根据内容优化指令改进文档的表达方式，提升语言表达的清晰度和专业性
2. 根据表格优化指令将适合的内容转换为Markdown表格格式
3. **严格保持文档的整体结构和格式不变，完整保留所有重要的详细信息和数据**
4. 对于表格优化的部分，使用 **【表格优化】** 标记突出显示
5. 对于被转换成表格的数据，保持原有的数字表达，同时添加相应的表格
6. **重要：优化表达方式，不删减实质内容，确保信息完整性**

【优化要求】：
- **禁止删除章节：严格按照指令进行优化，不要添加或删除任何章节**
- **禁止删除段落：保持所有段落的完整性，只优化表达方式**
- **保持格式：保持原有的Markdown格式（标题层级、段落结构等）**
- **保持内容：必须保持所有重要的详细信息、数据、技术规范和政策依据，不得删除实质性内容**
- **优化目标：改进表达方式和消除真正的重复，而不是删减内容长度**
- **内容保留率：优化后的文档必须保持原文档95%以上的信息量**
- **表格要求：表格应包含合适的表头，数据排列整齐，但不能用表格替代详细的文字描述**
- **表达优化：重点优化表达方式，使内容更加清晰、准确、专业，而不是单纯删减内容**
- **数据保留：对于数据和数字信息，在转换为表格的同时必须保持原有的文字表达**
- **专业内容：对于技术细节、规范标准、具体数据等专业内容，必须100%完整保留**
- **禁止输出：绝对不要输出任何图片、媒体相关内容或链接**

【重要：综合处理指令】：
在处理每个章节时，请注意以下几点：
1. 如果多个修改指令涉及同一个章节，需要综合考虑所有相关指令
2. 对于跨章节的冗余处理指令（包含"subtitles"字段），要特别注意：
   - 仔细阅读指令中关于每个章节应该"保留什么内容"和"删除什么内容"的具体说明
   - 确保按照指令要求，在指定章节保留完整信息，在其他章节删除重复信息
   - 绝不能在所有涉及的章节中都删除相同信息，必须确保重要信息在至少一个章节中得到保留
3. 对于同章节内的冗余处理指令（只有"subtitle"字段），按照指令合并或删除章节内的重复内容
4. 在修改过程中，始终保持信息的完整性和逻辑连贯性

# 优化示例

## 示例 1：跨章节冗余处理

**假设修改指令**
```json
{
  "subtitles": ["一、项目介绍", "五、项目必要性分析"],
  "suggestion": "在「五、项目必要性分析」中保留完整的政策符合性表述（国家中长期教育发展规划、省级教育事业"十四五"规划、清远市教育发展战略），在「一、项目介绍」中删除重复的政策符合性表述，保留项目建设的具体作用描述。"
}
```

**原始文本**
```
## 一、项目介绍

本项目符合国家中长期教育发展规划，符合省级教育事业"十四五"规划，符合清远市教育发展战略。通过本项目的建设，将进一步完善清新区职业教育体系，提升职业教育整体办学水平，促进教育公平和社会和谐发展。

## 五、项目必要性分析

本项目符合国家中长期教育发展规划，符合省级教育事业"十四五"规划，符合清远市教育发展战略，符合清远市教育事业发展总体要求，对促进职业教育发展具有重要意义。
```

**期望输出（最终优化后的 Markdown）**
```
## 一、项目介绍

通过本项目的建设，将进一步完善清新区职业教育体系，提升职业教育整体办学水平，促进教育公平和社会和谐发展。

## 五、项目必要性分析

本项目符合国家中长期教育发展规划、省级教育事业"十四五"规划、清远市教育发展战略以及清远市教育事业发展总体要求，对促进职业教育发展具有重要意义。
```

## 示例 2：同章节内冗余处理

**假设修改指令**
```json
{
  "subtitle": "三、技术方案",
  "suggestion": "合并关于云计算技术的重复表述，整合为更简洁的表达。"
}
```

**原始文本**
```
## 三、技术方案

本项目采用先进的云计算技术。云计算技术能够提供强大的计算能力。我们选择的云计算平台具有高可靠性。云计算技术的优势在于弹性扩展和成本控制。
```

**期望输出（最终优化后的 Markdown）**
```
## 三、技术方案

本项目采用先进的云计算技术，该技术具有强大计算能力、高可靠性、弹性扩展和成本控制等优势。
```

## 示例 3：表格优化（结构化信息类）

**原始文本**
```
## 六、主要建设内容

1. 综合教学楼：建筑面积 25,000 平方米，用于公共课程教学。
2. 实训大楼：建筑面积 18,000 平方米，配备实训室和实验室。
3. 学生宿舍楼：建筑面积 30,000 平方米，可容纳 3,000 名学生。
4. 食堂：建筑面积 5,000 平方米，提供 6,000 个就餐座位。
```

**期望输出（最终优化 Markdown）**
```
## 六、主要建设内容

**【表格优化】**
| 建设项目     | 建筑面积（㎡） | 功能                   |
|--------------|----------------|------------------------|
| 综合教学楼   | 25,000         | 公共课程教学           |
| 实训大楼     | 18,000         | 配备实训室和实验室     |
| 学生宿舍楼   | 30,000         | 可容纳 3,000 名学生    |
| 食堂         | 5,000          | 提供 6,000 个就餐座位  |
```

""" + modification_text + """

""" + table_text + """

【原始文档】：
""" + original_markdown + """

**【最终提醒 - 必须严格遵守】**：
1. **这是文档优化任务，不是内容删减任务**
2. **必须输出完整的文档，保持所有章节的详细内容**
3. **只优化表达方式和消除真正的重复，不删除实质性信息**
4. **确保输出的文档长度与原文档相近，信息量完整**
5. **每个段落都要保留，只改进表达方式**
6. **所有技术细节、数据、规范都必须完整保留**
7. **如果不确定是否删除某个内容，请选择保留**

**【输出要求】**：
请严格参考上述示例，直接输出优化后的完整文档，保持所有章节的顺序和结构。
输出的文档应该与原文档长度相近，只是表达更清晰、更专业。"""
        
        return prompt
    
    def _optimize_complete_document_with_llm(self, optimization_prompt: str) -> str:
        """
        使用LLM优化完整文档
        
        Args:
            optimization_prompt: 优化提示词
            
        Returns:
            str: 优化后的文档内容
        """
        try:
            self.colored_logger.api_call("完整文档优化")
            
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
                        "content": optimization_prompt
                    }
                ],
                temperature=0.1,  # 低温度确保一致性
                max_tokens=16000  # 增大token限制以处理完整文档
            )
            
            optimized_content = completion.choices[0].message.content.strip()
            
            # 清洗内容
            optimized_content = self._sanitize_complete_document(optimized_content)
            
            self.colored_logger.api_response(f"完整文档优化完成，长度: {len(optimized_content)} 字符")
            
            return optimized_content
            
        except Exception as e:
            self.colored_logger.error(f"❌ LLM完整文档优化失败: {e}")
            raise
    
    def _sanitize_complete_document(self, content: str) -> str:
        """
        清洗完整文档内容
        
        Args:
            content: 原始内容
            
        Returns:
            str: 清洗后的内容
        """
        if not content:
            return content
        
        # 基本清洗，移除多余空行
        cleaned_text = re.sub(r'\n{3,}', '\n\n', content).strip()
        
        # 过滤不需要的内容行
        lines = cleaned_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # 过滤图片和媒体相关内容
            if (stripped.startswith('### 相关图片资料') or 
                stripped.startswith('### 相关表格资料') or
                stripped.startswith('图片描述:') or 
                stripped.startswith('图片来源:') or
                re.search(r'!\[.*?\]\(.*?\)', stripped) or 
                re.search(r'\[[^\]]+\]\(https?://[^\)]+\)', stripped, flags=re.IGNORECASE)):
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _sanitize_content(self, content: str) -> str:
        """
        清洗内容，移除图片/表格/媒体相关内容
        
        Args:
            content: 原始内容
            
        Returns:
            str: 清洗后的内容
        """
        if not content:
            return content
        
        cleaned_lines = []
        for line in content.splitlines():
            stripped = line.strip()
            
            # 跳过空行
            if not stripped:
                cleaned_lines.append(line)
                continue
            
            # 过滤标题行
            if stripped.startswith('#'):
                continue
            
            # 过滤表格相关内容
            if stripped.startswith('### 相关表格资料') or stripped.startswith('|'):
                continue
            
            # 过滤图片相关内容
            if (stripped.startswith('### 相关图片资料') or 
                stripped == '相关图片资料' or 
                stripped.startswith('相关图片资料') or
                stripped.startswith('图片描述:') or 
                stripped.startswith('图片来源:')):
                continue
            
            # 过滤Markdown图片和链接
            if (re.search(r'!\[.*?\]\(.*?\)', stripped) or 
                re.search(r'\[[^\]]+\]\(https?://[^\)]+\)', stripped, flags=re.IGNORECASE)):
                continue
            
            cleaned_lines.append(line)
        
        # 合并并去除多余空行
        cleaned_text = '\n'.join(cleaned_lines)
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()
        
        return cleaned_text
    
    # 章节替换方法已删除，现在使用全文处理
    
    def save_modified_document(self, result: Dict[str, Any], output_path: str = None) -> str:
        """
        保存修改后的文档
        
        Args:
            result: 修改结果
            output_path: 输出路径（可选）
            
        Returns:
            str: 保存的文件路径
        """
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                document_title = result.get('document_title', '未命名文档')
                safe_title = re.sub(r'[^\w\s-]', '', document_title).strip()
                safe_title = re.sub(r'[-\s]+', '_', safe_title)
                output_path = f"modified_{safe_title}_{timestamp}.md"
            
            # 保存修改后的Markdown文档
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result['modified_markdown'])
            
            # 保存修改报告
            report_path = output_path.replace('.md', '_report.json')
            report_data = {
                "document_title": result.get('document_title'),
                "modification_timestamp": result.get('modification_timestamp'),
                "sections_modified": result.get('sections_modified'),
                "modifications_applied": result.get('modifications_applied'),
                "overall_improvement": result.get('overall_improvement')
            }
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            self.colored_logger.info(f"💾 修改后的文档已保存:")
            self.colored_logger.info(f"   - Markdown文档: {output_path}")
            self.colored_logger.info(f"   - 修改报告: {report_path}")
            
            return output_path
            
        except Exception as e:
            self.colored_logger.error(f"❌ 保存修改后的文档失败: {e}")
            raise


def main():
    """测试文档修改器"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('document_modification.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    print("🔧 文档修改器测试")
    
    # 示例用法
    modifier = DocumentModifier()
    
    # 示例分析结果
    sample_analysis = {
        "document_title": "测试文档",
        "analysis_timestamp": "2024-01-01 12:00:00",
        "issues_found": 2,
        "modification_instructions": [
            {
                "section_title": "项目背景",
                "modification_type": "content_optimization",
                "instruction": "删除重复的项目介绍内容，保持简洁",
                "priority": "medium"
            },
            {
                "section_title": "技术方案",
                "modification_type": "content_optimization", 
                "instruction": "合并相似的技术描述，避免冗余",
                "priority": "medium"
            }
        ],
        "analysis_summary": "发现 2 个需要优化的章节"
    }
    
    # 示例Markdown文档
    sample_markdown = """# 测试文档

## 项目背景

这是一个测试项目。这是一个测试项目的背景介绍。
项目的目标是测试文档修改功能。项目的目标是测试文档修改功能。

## 技术方案

我们采用了先进的技术方案。我们采用了先进的技术方案来实现目标。
技术栈包括Python和相关框架。技术栈包括Python和相关框架。
"""
    
    # 执行修改
    result = modifier.modify_document(sample_markdown, sample_analysis)
    
    print(f"\n📊 修改结果:")
    print(f"   修改章节数: {result['sections_modified']}")
    print(f"   整体改进: {result['overall_improvement']}")


if __name__ == "__main__":
    main()
