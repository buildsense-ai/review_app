#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档优化器主程序 - 新的工作流程

实现两步式文档优化：
1. 全局分析：接收完整Markdown文档，输出分析JSON
2. 文档修改：接收原文档和分析JSON，输出优化后的Markdown
"""

import json
import logging
import sys
import os
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 如果没有安装python-dotenv，继续运行

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from document_reviewer import DocumentReviewer
from document_modifier import DocumentModifier


class DocumentOptimizer:
    """文档优化器 - 整合分析和修改功能"""
    
    def __init__(self):
        """初始化文档优化器"""
        # 先设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('document_optimization.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # 初始化其他组件
        self.reviewer = DocumentReviewer()
        self.modifier = DocumentModifier()
        
        # 初始化OpenAI客户端用于分章节生成
        api_key = os.getenv("OPENROUTER_API_KEY")
        if api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
        else:
            self.client = None
            self.logger.warning("未设置OPENROUTER_API_KEY环境变量，分章节生成功能将不可用")
        self.max_workers = 5
    
    def step1_analyze_document(self, markdown_file_path: str, output_dir: str = "./test_results") -> str:
        """
        步骤1：全局分析文档
        
        Args:
            markdown_file_path: Markdown文档路径
            output_dir: 分析结果输出目录
            
        Returns:
            str: 分析结果JSON文件路径
        """
        self.logger.info(f"🔍 步骤1：开始全局分析文档 - {markdown_file_path}")
        
        try:
            # 读取文档内容
            with open(markdown_file_path, 'r', encoding='utf-8') as f:
                document_content = f.read()
            
            # 获取文档标题
            document_title = os.path.basename(markdown_file_path)
            
            # 执行全局分析
            analysis_result = self.reviewer.analyze_document_global(document_content, document_title)
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成输出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = re.sub(r'[^\w\s-]', '', document_title).strip()
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            analysis_file_path = os.path.join(output_dir, f"analysis_{safe_title}_{timestamp}.json")
            
            # 保存分析结果
            with open(analysis_file_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            
            # 显示分析摘要
            issues_found = analysis_result.get('issues_found', 0)
            
            self.logger.info(f"✅ 步骤1完成 - 分析结果已保存: {analysis_file_path}")
            self.logger.info(f"📊 分析摘要: 发现 {issues_found} 个问题")
            
            return analysis_file_path
            
        except Exception as e:
            self.logger.error(f"❌ 步骤1失败: {e}")
            raise
    
    def step2_modify_document(self, markdown_file_path: str, analysis_file_path: str, 
                             output_dir: str = "./test_results") -> str:
        """
        步骤2：基于分析结果修改文档
        
        Args:
            markdown_file_path: 原始Markdown文档路径
            analysis_file_path: 分析结果JSON文件路径
            output_dir: 优化结果输出目录
            
        Returns:
            str: 优化后的Markdown文件路径
        """
        self.logger.info(f"🔧 步骤2：开始修改文档")
        self.logger.info(f"   原始文档: {markdown_file_path}")
        self.logger.info(f"   分析结果: {analysis_file_path}")
        
        try:
            # 读取原始文档
            with open(markdown_file_path, 'r', encoding='utf-8') as f:
                original_markdown = f.read()
            
            # 读取分析结果
            with open(analysis_file_path, 'r', encoding='utf-8') as f:
                analysis_json = json.load(f)
            
            # 执行文档修改
            modification_result = self.modifier.modify_document(original_markdown, analysis_json)
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成输出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            document_title = analysis_json.get('document_title', 'unknown_document')
            safe_title = re.sub(r'[^\w\s-]', '', document_title).strip()
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            optimized_file_path = os.path.join(output_dir, f"optimized_{safe_title}_{timestamp}.md")
            
            # 保存优化后的文档
            with open(optimized_file_path, 'w', encoding='utf-8') as f:
                f.write(modification_result['modified_markdown'])
            
            # 保存修改报告
            report_file_path = optimized_file_path.replace('.md', '_report.json')
            report_data = {
                "original_document": markdown_file_path,
                "analysis_file": analysis_file_path,
                "optimized_document": optimized_file_path,
                "modification_timestamp": modification_result.get('modification_timestamp'),
                "sections_modified": modification_result.get('sections_modified'),
                "tables_optimized": modification_result.get('tables_optimized'),
                "modifications_applied": modification_result.get('modifications_applied'),
                "table_optimizations_applied": modification_result.get('table_optimizations_applied'),
                "overall_improvement": modification_result.get('overall_improvement')
            }
            
            with open(report_file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            # 显示修改摘要
            sections_modified = modification_result.get('sections_modified', 0)
            tables_optimized = modification_result.get('tables_optimized', 0)
            overall_improvement = modification_result.get('overall_improvement', '无改进信息')
            
            self.logger.info(f"✅ 步骤2完成 - 优化文档已保存: {optimized_file_path}")
            self.logger.info(f"📝 修改摘要: 修改了 {sections_modified} 个章节，优化了 {tables_optimized} 个表格")
            self.logger.info(f"💡 整体改进: {overall_improvement}")
            self.logger.info(f"📋 修改报告: {report_file_path}")
            
            return optimized_file_path
            
        except Exception as e:
            self.logger.error(f"❌ 步骤2失败: {e}")
            raise
    
    def optimize_document_complete(self, markdown_file_path: str, 
                                  analysis_output_dir: str = "./test_results",
                                  optimized_output_dir: str = "./test_results") -> Dict[str, str]:
        """
        完整的文档优化流程（两步合一）
        
        Args:
            markdown_file_path: Markdown文档路径
            analysis_output_dir: 分析结果输出目录
            optimized_output_dir: 优化结果输出目录
            
        Returns:
            Dict[str, str]: 包含分析文件和优化文件路径的字典
        """
        self.logger.info(f"🚀 开始完整文档优化流程: {markdown_file_path}")
        
        try:
            # 步骤1：全局分析
            analysis_file_path = self.step1_analyze_document(markdown_file_path, analysis_output_dir)
            
            # 步骤2：文档修改
            optimized_file_path = self.step2_modify_document(
                markdown_file_path, analysis_file_path, optimized_output_dir
            )
            
            self.logger.info(f"🎉 完整优化流程完成！")
            
            return {
                "original_document": markdown_file_path,
                "analysis_file": analysis_file_path,
                "optimized_document": optimized_file_path
            }
            
        except Exception as e:
            self.logger.error(f"❌ 完整优化流程失败: {e}")
            raise
    
    def _call_llm_for_modification(self, section_title: str, original_content: str, suggestion: str) -> str:
        """调用LLM进行章节修改"""
        # 不再强制字数限制，让LLM专注于内容优化
        original_word_count = len(original_content)
        
        prompt = f"""你是一位专业的文档编辑，请根据以下要求优化文档章节内容。

【原始章节】：{section_title}
【原始内容】：
{original_content}

【优化建议】：
{suggestion}

【优化要求】：
1. 根据优化建议改进文档的表达方式，提升语言表达的清晰度和专业性
2. **必须保持所有重要的详细信息、数据、技术规范和政策依据，不得删除实质性内容**
3. **优化重点是改进表达方式和消除真正的重复，而不是删减内容长度**
4. **优化后的内容应保持与原文档相近的信息量，只删除真正重复的内容**
5. **特别注意表格优化**：如果建议中包含"表格优化"，请将相关的数据、参数、对比信息转换为Markdown表格格式
6. 对于数据和数字信息，优先使用表格展示，同时保持必要的文字说明
7. 保持原有的Markdown格式和章节结构
8. **对于技术细节、规范标准、具体数据等专业内容，必须完整保留**

【表格格式示例】：
| 项目 | 参数1 | 参数2 | 备注 |
|------|-------|-------|------|
| 示例1 | 数值1 | 数值2 | 说明1 |
| 示例2 | 数值3 | 数值4 | 说明2 |

**【最终提醒】**：
- 这是内容优化任务，不是内容删减任务
- 必须保持章节的完整性和专业性
- 只优化表达方式，不删除实质性信息
- 确保输出内容与原文档信息量相近

请直接输出优化后的Markdown内容，不要包含任何解释或说明："""

        if not self.client:
            self.logger.error("OpenAI客户端未初始化，无法调用LLM")
            return original_content
            
        try:
            # 从环境变量获取模型名称，优先使用OPENROUTER_MODEL
            model_name = os.getenv('OPENROUTER_MODEL') or os.getenv('DEFAULT_MODEL') or "anthropic/claude-3.5-sonnet"
            
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"LLM调用失败: {e}")
            return original_content
    
    def regenerate_section(self, section_title: str, original_content: str, suggestion: str, original_json_data: dict) -> dict:
        """重新生成单个章节"""
        self.logger.info(f"开始处理章节: {section_title}")
        
        try:
            # 调用LLM生成新内容
            new_content = self._call_llm_for_modification(section_title, original_content, suggestion)
            
            # 构建返回结果
            result = {
                "section_title": section_title,
                "original_content": original_content,
                "suggestion": suggestion,
                "regenerated_content": new_content,
                "word_count": len(new_content),
                "status": "success"
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"章节 {section_title} 处理失败: {e}")
            return {
                "section_title": section_title,
                "original_content": original_content,
                "suggestion": suggestion,
                "regenerated_content": original_content,  # 失败时返回原内容
                "word_count": len(original_content),
                "status": "failed",
                "error": str(e)
            }
    
    def regenerate_document_sections(self, evaluation_file: str, document_file: str) -> Dict[str, Any]:
        """并行重新生成文档章节"""
        self.logger.info(f"开始分章节重新生成文档")
        self.logger.info(f"评估文件: {evaluation_file}")
        self.logger.info(f"原始文档: {document_file}")
        
        # 读取评估结果
        with open(evaluation_file, 'r', encoding='utf-8') as f:
            evaluation_data = json.load(f)
        
        # 读取原始文档
        with open(document_file, 'r', encoding='utf-8') as f:
            original_document = f.read()
        
        # 解析章节内容
        sections = self._parse_document_sections(original_document)
        
        # 准备任务列表
        tasks = []
        modification_instructions = evaluation_data.get('modification_instructions', [])
        table_opportunities = evaluation_data.get('table_opportunities', [])
        
        # 创建章节到建议的映射
        section_suggestions = {}
        section_table_opportunities = {}
        
        # 收集修改建议
        for instruction in modification_instructions:
            subtitle = instruction.get('subtitle', '')
            suggestion = instruction.get('suggestion', '')
            if subtitle not in section_suggestions:
                section_suggestions[subtitle] = []
            section_suggestions[subtitle].append(suggestion)
        
        # 收集表格优化机会
        for table_opp in table_opportunities:
            section_title = table_opp.get('section_title', '')
            table_suggestion = table_opp.get('table_opportunity', '')
            if section_title not in section_table_opportunities:
                section_table_opportunities[section_title] = []
            section_table_opportunities[section_title].append(table_suggestion)
        
        # 合并所有需要处理的章节
        all_sections = set(section_suggestions.keys())
        
        # 为表格优化机会找到匹配的章节
        for table_section_title in section_table_opportunities.keys():
            matched_sections = []
            
            # 根据表格机会的章节标题找到对应的实际章节
            if "项目需求分析与产出方案" in table_section_title:
                # 匹配需求分析和产出方案相关章节
                for section_key in sections.keys():
                    if any(keyword in section_key for keyword in ["需求分析", "产出方案", "建设内容和规模"]):
                        matched_sections.append(section_key)
            elif "项目选址与要素保障" in table_section_title:
                # 匹配选址相关章节
                for section_key in sections.keys():
                    if any(keyword in section_key for keyword in ["选址", "选线"]):
                        matched_sections.append(section_key)
            elif "项目建设方案" in table_section_title:
                # 匹配建设方案相关章节
                for section_key in sections.keys():
                    if any(keyword in section_key for keyword in ["建设内容", "建设方案", "数字化方案", "建设管理", "工程方案", "设备方案"]):
                        matched_sections.append(section_key)
            elif "（二）项目单位概况" in table_section_title:
                # 直接匹配项目单位概况
                for section_key in sections.keys():
                    if "项目单位概况" in section_key:
                        matched_sections.append(section_key)
            else:
                # 通用匹配逻辑
                for section_key in sections.keys():
                    if table_section_title in section_key or section_key in table_section_title:
                        matched_sections.append(section_key)
            
            # 将匹配到的章节添加到处理列表
            all_sections.update(matched_sections)
        
        # 如果没有任何章节需要处理，说明可能是分析失败，返回原始章节内容
        if not all_sections:
            self.logger.warning("没有找到需要处理的章节，可能是分析结果为空，返回原始内容")
            # 返回原始章节内容，确保有内容可以显示
            result = {}
            for section_title, section_data in sections.items():
                result[section_title] = {
                    "content": section_data['content'],
                    "quality_score": 1.0,
                    "word_count": len(section_data['content'].split()),
                    "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "original",
                    "note": "分析失败，保留原始内容"
                }
            return result
        
        # 为每个章节创建任务
        for section_title in all_sections:
            section_content = self._find_section_content(sections, section_title)
            if section_content:
                # 合并该章节的所有建议
                combined_suggestions = []
                
                # 添加修改建议
                if section_title in section_suggestions:
                    combined_suggestions.extend([f"表达优化：{s}" for s in section_suggestions[section_title]])
                
                # 添加表格优化建议
                for table_section_title, table_opps in section_table_opportunities.items():
                    # 检查当前章节是否应该包含这些表格优化建议
                    should_include = False
                    
                    if "项目需求分析与产出方案" in table_section_title:
                        if any(keyword in section_title for keyword in ["需求分析", "产出方案", "建设内容和规模"]):
                            should_include = True
                    elif "项目选址与要素保障" in table_section_title:
                        if any(keyword in section_title for keyword in ["选址", "选线"]):
                            should_include = True
                    elif "项目建设方案" in table_section_title:
                        if any(keyword in section_title for keyword in ["建设内容", "建设方案", "数字化方案", "建设管理"]):
                            should_include = True
                    else:
                        if table_section_title in section_title or section_title in table_section_title:
                            should_include = True
                    
                    if should_include:
                        combined_suggestions.extend([f"表格优化：{s}" for s in table_opps])
                
                if combined_suggestions:
                    tasks.append({
                        'section_title': section_title,
                        'original_content': section_content,
                        'suggestion': '\n'.join(combined_suggestions),
                        'original_json_data': evaluation_data
                    })
        
        # 并行处理章节
        regeneration_results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(
                    self.regenerate_section,
                    task['section_title'],
                    task['original_content'],
                    task['suggestion'],
                    task['original_json_data']
                ): task for task in tasks
            }
            
            completed_count = 0
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                section_title = task['section_title']
                try:
                    result = future.result()
                    regeneration_results[section_title] = result
                    completed_count += 1
                    self.logger.info(f"完成章节 ({completed_count}/{len(tasks)}): {section_title}")
                except Exception as e:
                    self.logger.error(f"处理章节失败 {section_title}: {e}")
                    regeneration_results[section_title] = {
                        "section_title": section_title,
                        "status": "failed",
                        "error": str(e)
                    }
        
        return regeneration_results
    
    def _parse_document_sections(self, document_content: str) -> Dict[str, str]:
        """解析文档章节，保持层级结构"""
        sections = {}
        lines = document_content.split('\n')
        current_section = None
        current_content = []
        current_h1 = None  # 当前一级标题
        
        for line in lines:
            # 检查是否是标题
            if line.strip().startswith('#'):
                # 保存上一个章节
                if current_section:
                    sections[current_section] = {
                        'content': '\n'.join(current_content).strip(),
                        'h1_parent': current_h1,
                        'full_title': current_section
                    }
                
                # 判断标题级别
                if line.strip().startswith('# ') and not line.strip().startswith('## '):
                    # 一级标题
                    current_h1 = line.strip().replace('# ', '').strip()
                    current_section = current_h1
                elif line.strip().startswith('## '):
                    # 二级标题
                    current_section = line.strip().replace('## ', '').strip()
                else:
                    # 其他级别标题，按二级处理
                    current_section = line.strip().replace('#', '').strip()
                
                current_content = [line]
            else:
                if current_section:
                    current_content.append(line)
        
        # 保存最后一个章节
        if current_section:
            sections[current_section] = {
                'content': '\n'.join(current_content).strip(),
                'h1_parent': current_h1,
                'full_title': current_section
            }
        
        return sections
    
    def _find_section_content(self, sections: Dict[str, dict], section_title: str) -> Optional[str]:
        """查找章节内容"""
        # 直接匹配
        if section_title in sections:
            return sections[section_title]['content']
        
        # 模糊匹配
        for title, section_data in sections.items():
            if section_title in title or title in section_title:
                return section_data['content']
        
        return None
    
    def regenerate_and_merge_document(self, evaluation_file: str, document_file: str, 
                                    output_dir: str = "./test_results", auto_merge: bool = False) -> Dict[str, str]:
        """重新生成并合并文档"""
        self.logger.info("开始重新生成并合并文档")
        
        # 重新生成章节
        regeneration_results = self.regenerate_document_sections(evaluation_file, document_file)
        
        # 生成输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(document_file))[0]
        
        # 保存重新生成的章节到JSON
        regenerated_json_path = os.path.join(output_dir, f"regenerated_sections_{timestamp}.json")
        with open(regenerated_json_path, 'w', encoding='utf-8') as f:
            json.dump(regeneration_results, f, ensure_ascii=False, indent=2)
        
        # 生成Markdown文档
        regenerated_md_path = os.path.join(output_dir, f"regenerated_sections_{timestamp}.md")
        self._generate_markdown_document(regeneration_results, regenerated_md_path, document_file)
        
        return {
            "regenerated_sections": regenerated_md_path,
            "regenerated_json": regenerated_json_path,
            "original_document": document_file,
            "evaluation_file": evaluation_file
        }
    
    def _generate_markdown_document(self, regeneration_results: Dict[str, Any], output_path: str, original_document_path: str):
        """生成Markdown文档，保持原始层级结构"""
        # 读取原始文档
        with open(original_document_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # 如果没有重新生成的内容，直接复制原文档
        if not regeneration_results:
            self.logger.info("没有重新生成的内容，保持原文档结构")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            return
        
        # 解析原始文档的章节结构
        original_sections = self._parse_document_sections(original_content)
        
        # 重建完整文档结构
        with open(output_path, 'w', encoding='utf-8') as f:
            lines = original_content.split('\n')
            i = 0
            
            while i < len(lines):
                line = lines[i]
                
                if line.strip().startswith('# ') and not line.strip().startswith('## '):
                    # 一级标题，直接写入
                    f.write(f"{line}\n\n")
                    i += 1
                    
                elif line.strip().startswith('## '):
                    # 二级标题
                    h2_title = line.strip().replace('## ', '').strip()
                    
                    # 检查是否有重新生成的内容
                    if h2_title in regeneration_results and regeneration_results[h2_title].get('status') == 'success':
                        # 写入标题
                        f.write(f"{line}\n\n")
                        
                        # 写入重新生成的内容
                        content = regeneration_results[h2_title].get('regenerated_content', '')
                        # 移除内容开头的标题行
                        content_lines = content.split('\n')
                        if content_lines and content_lines[0].strip().startswith('#'):
                            content = '\n'.join(content_lines[1:]).strip()
                        
                        f.write(f"{content}\n\n")
                        
                        # 跳过原始内容，直到下一个标题
                        i += 1
                        while i < len(lines) and not lines[i].strip().startswith('#'):
                            i += 1
                    else:
                        # 使用原始内容，写入标题
                        f.write(f"{line}\n")
                        i += 1
                        
                        # 写入原始内容直到下一个标题
                        while i < len(lines) and not lines[i].strip().startswith('#'):
                            f.write(f"{lines[i]}\n")
                            i += 1
                        f.write("\n")  # 章节间空行
                        
                elif line.strip().startswith('#'):
                    # 其他级别标题，直接写入
                    f.write(f"{line}\n")
                    i += 1
                else:
                    # 非标题行，在一级标题下直接写入
                    f.write(f"{line}\n")
                    i += 1
    
    def _find_original_title_format(self, original_content: str, section_title: str) -> Optional[str]:
        """查找原始文档中的标题格式"""
        lines = original_content.split('\n')
        for line in lines:
            if line.strip().startswith('#') and section_title in line:
                return line.strip()
        return None


def main():
    """主函数 - 统一启动入口"""
    # 默认测试文档路径
    default_document_path = "/Users/wangzijian/Desktop/gauz/keyan/final_review_agent_app/final_markdown_merged_document_20250904_162736.md"
    
    if len(sys.argv) < 2:
        print("🚀 文档优化器 - 统一启动入口")
        print()
        print("📋 使用方法:")
        print("  1. 快速优化（推荐）- 分章节并行处理，保持80-90%字数:")
        print("    python run_document_optimizer.py")
        print("    python run_document_optimizer.py <markdown文件路径>")
        print()
        print("  2. 传统全文优化:")
        print("    python run_document_optimizer.py --full <markdown文件路径>")
        print("    python run_document_optimizer.py --step1 <markdown文件路径>")
        print("    python run_document_optimizer.py --step2 <markdown文件路径> <分析结果json路径>")
        print()
        print("  3. 仅分析不修改:")
        print("    python run_document_optimizer.py --analyze-only <markdown文件路径>")
        print()
        print("📝 示例:")
        print("  python run_document_optimizer.py                    # 使用默认文档，快速优化")
        print("  python run_document_optimizer.py document.md        # 快速优化指定文档")
        print("  python run_document_optimizer.py --full document.md # 传统全文优化")
        print()
        print("🧪 默认配置:")
        print(f"  默认文档: {default_document_path}")
        print("  输出目录: ./test_results")
        print("  优化方式: 分章节并行处理（保持80-90%字数）")
        print()
        
        # 使用默认文档进行快速优化
        print(f"🚀 使用默认文档进行快速优化: {default_document_path}")
        print("=" * 60)
        
        # 先分析
        optimizer = DocumentOptimizer()
        analysis_file = optimizer.step1_analyze_document(default_document_path, "./test_results")
        
        # 然后分章节优化
        result_paths = optimizer.regenerate_and_merge_document(
            evaluation_file=analysis_file,
            document_file=default_document_path,
            output_dir="./test_results",
            auto_merge=False  # 不自动合并，因为是Markdown文档
        )
        
        print(f"\n🎉 快速优化完成！")
        print(f"📄 原始文档: {default_document_path}")
        print(f"📊 分析结果: {analysis_file}")
        print(f"📝 优化章节: {result_paths.get('regenerated_sections')}")
        return
    
    optimizer = DocumentOptimizer()
    
    try:
        if sys.argv[1] == "--full":
            # 传统全文优化模式
            if len(sys.argv) < 3:
                print("❌ 缺少Markdown文件路径")
                return
            
            markdown_file = sys.argv[2]
            print(f"🔄 使用传统全文优化模式: {markdown_file}")
            result = optimizer.optimize_document_complete(
                markdown_file,
                analysis_output_dir="./test_results",
                optimized_output_dir="./test_results"
            )
            
            print(f"\n🎉 传统全文优化完成！")
            print(f"📄 原始文档: {result['original_document']}")
            print(f"📊 分析结果: {result['analysis_file']}")
            print(f"✨ 优化文档: {result['optimized_document']}")
            
        elif sys.argv[1] == "--step1":
            # 仅执行步骤1：全局分析
            if len(sys.argv) < 3:
                print("❌ 缺少Markdown文件路径")
                return
            
            markdown_file = sys.argv[2]
            analysis_file = optimizer.step1_analyze_document(markdown_file, "./test_results")
            
            print(f"\n🎯 步骤1完成！")
            print(f"📄 原始文档: {markdown_file}")
            print(f"📊 分析结果: {analysis_file}")
            print(f"\n💡 下一步可以运行:")
            print(f"   python run_document_optimizer.py --step2 {markdown_file} {analysis_file}")
            print(f"   或者: python regenerate_sections.py {analysis_file}")
            
        elif sys.argv[1] == "--step2":
            # 仅执行步骤2：文档修改
            if len(sys.argv) < 4:
                print("❌ 缺少Markdown文件路径或分析结果文件路径")
                return
            
            markdown_file = sys.argv[2]
            analysis_file = sys.argv[3]
            optimized_file = optimizer.step2_modify_document(markdown_file, analysis_file, "./test_results")
            
            print(f"\n🎯 步骤2完成！")
            print(f"📄 原始文档: {markdown_file}")
            print(f"📊 分析结果: {analysis_file}")
            print(f"✨ 优化文档: {optimized_file}")
            
        elif sys.argv[1] == "--analyze-only":
            # 仅分析不修改
            if len(sys.argv) < 3:
                print("❌ 缺少Markdown文件路径")
                return
            
            markdown_file = sys.argv[2]
            analysis_file = optimizer.step1_analyze_document(markdown_file, "./test_results")
            
            print(f"\n📊 分析完成！")
            print(f"📄 原始文档: {markdown_file}")
            print(f"📊 分析结果: {analysis_file}")
            print(f"\n💡 如需优化，可以运行:")
            print(f"   python regenerate_sections.py {analysis_file}")
            
        else:
            # 快速优化模式（默认推荐）
            markdown_file = sys.argv[1]
            print(f"🚀 使用快速优化模式: {markdown_file}")
            print("=" * 60)
            
            # 先分析
            analysis_file = optimizer.step1_analyze_document(markdown_file, "./test_results")
            
            # 然后分章节优化
            result_paths = optimizer.regenerate_and_merge_document(
                evaluation_file=analysis_file,
                document_file=markdown_file,
                output_dir="./test_results",
                auto_merge=False  # 不自动合并，因为是Markdown文档
            )
            
            print(f"\n🎉 快速优化完成！")
            print(f"📄 原始文档: {markdown_file}")
            print(f"📊 分析结果: {analysis_file}")
            print(f"📝 优化章节: {result_paths.get('regenerated_sections')}")
            
    except Exception as e:
        print(f"\n❌ 优化过程失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
