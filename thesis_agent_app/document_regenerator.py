#!/usr/bin/env python3
"""
基于论点一致性修正结果重新生成完整文档的脚本

该脚本读取论点一致性检查结果，对有问题的章节进行重新生成，
然后生成一个完整的修正后文档。
"""

import json
import logging
import os
import sys
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Tuple
from datetime import datetime
from openai import OpenAI

# 导入相关模块
from config import config


class ThesisDocumentRegenerator:
    """
    基于论点一致性的文档重新生成器
    
    读取一致性检查结果，重新生成有问题的章节，并输出完整文档
    """
    
    def __init__(self, max_workers: int = 5):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 多线程配置
        self.max_workers = max_workers
        self._thread_local = threading.local()
        self._lock = threading.Lock()
        
        # 进度跟踪
        self._progress = {
            'total_sections': 0,
            'completed_sections': 0,
            'failed_sections': 0
        }
        
        self.logger.info(f"✅ ThesisDocumentRegenerator 初始化完成 (最大工作线程: {max_workers})")
    
    def _get_client(self) -> OpenAI:
        """
        获取线程本地的OpenAI客户端
        
        Returns:
            OpenAI: 线程本地的客户端实例
        """
        if not hasattr(self._thread_local, 'client'):
            self._thread_local.client = OpenAI(
                base_url=config.openrouter_base_url,
                api_key=config.openrouter_api_key,
            )
        return self._thread_local.client
    
    def _update_progress(self, completed: bool = True, failed: bool = False):
        """
        线程安全地更新进度
        
        Args:
            completed: 是否成功完成
            failed: 是否失败
        """
        with self._lock:
            if completed:
                self._progress['completed_sections'] += 1
            if failed:
                self._progress['failed_sections'] += 1
            
            total = self._progress['total_sections']
            completed_count = self._progress['completed_sections']
            failed_count = self._progress['failed_sections']
            
            if total > 0:
                progress_pct = (completed_count + failed_count) / total * 100
                self.logger.info(
                    f"📊 进度更新: {completed_count}/{total} 完成 "
                    f"({failed_count} 失败) - {progress_pct:.1f}%"
                )
    
    def load_consistency_analysis(self, analysis_file: str) -> tuple[Dict, Dict]:
        """
        加载一致性分析结果文件
        
        Args:
            analysis_file: 一致性分析结果JSON文件路径
            
        Returns:
            tuple: (一致性分析数据, 核心论点数据)
        """
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取一致性分析和核心论点信息
            consistency_data = data.get('consistency_analysis', {})
            thesis_data = data.get('thesis_statement', {})
            
            consistency_issues = consistency_data.get('consistency_issues', [])
            
            self.logger.info(f"成功加载一致性分析结果，共{len(consistency_issues)}个需要修正的章节")
            return consistency_data, thesis_data
            
        except Exception as e:
            self.logger.error(f"加载一致性分析结果失败: {e}")
            return {}, {}
    
    def load_original_document(self, document_file: str) -> tuple[str, Dict]:
        """
        加载原始文档
        
        Args:
            document_file: 原始文档文件路径
            
        Returns:
            tuple: (文档内容, JSON数据)
        """
        try:
            json_data = {}
            
            if document_file.endswith('.json'):
                # 处理JSON文档
                with open(document_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                content_parts = []
                report_guide = json_data.get('report_guide', [])
                total_sections = 0
                
                for part in report_guide:
                    sections = part.get('sections', [])
                    
                    for section in sections:
                        subtitle = section.get('subtitle', '')
                        generated_content = section.get('generated_content', '')
                        if subtitle and generated_content:
                            content_parts.append(f"## {subtitle}\n\n{generated_content}")
                            total_sections += 1
                
                content = "\n\n".join(content_parts)
                self.logger.info(f"成功加载JSON文档: {document_file}，提取了{total_sections}个章节")
                return content, json_data
            else:
                # 处理Markdown文档
                with open(document_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.logger.info(f"成功加载Markdown文档: {document_file}")
                return content, json_data
                
        except Exception as e:
            self.logger.error(f"加载原始文档失败: {e}")
            return "", {}
    
    def extract_section_content(self, document_content: str, section_title: str) -> str:
        """
        从文档中提取指定章节的内容
        
        Args:
            document_content: 完整文档内容
            section_title: 章节标题（支持路径格式，如 "一、引言/1.1、编写目的"）
            
        Returns:
            str: 章节内容
        """
        try:
            # 检查是否为路径格式（包含 "/"）
            if "/" in section_title:
                # 解析路径格式
                path_parts = section_title.split("/")
                parent_title = path_parts[0].strip()
                child_title = path_parts[-1].strip()
                
                self.logger.debug(f"解析路径格式章节: 父章节='{parent_title}', 子章节='{child_title}'")
                
                # 首先找到父章节的位置
                parent_pattern = rf"(?m)^\s*#\s*{re.escape(parent_title)}\s*$"
                parent_match = re.search(parent_pattern, document_content)
                
                if parent_match:
                    # 从父章节开始的位置查找子章节
                    parent_start = parent_match.end()
                    # 找到下一个同级或更高级标题的位置作为父章节的结束
                    next_h1_pattern = r"(?m)^\s*#\s"
                    next_h1_match = re.search(next_h1_pattern, document_content[parent_start:])
                    
                    if next_h1_match:
                        parent_content = document_content[parent_start:parent_start + next_h1_match.start()]
                    else:
                        parent_content = document_content[parent_start:]
                    
                    # 在父章节内容中查找子章节
                    return self._extract_child_section(parent_content, child_title)
                else:
                    self.logger.warning(f"未找到父章节: {parent_title}")
                    # 如果找不到父章节，尝试直接匹配子章节标题
                    return self._extract_single_section(document_content, child_title)
            else:
                # 单一章节标题，使用原有逻辑
                return self._extract_single_section(document_content, section_title)
                
        except Exception as e:
            self.logger.error(f"提取章节内容失败: {e}")
            return ""
    
    def _extract_single_section(self, document_content: str, section_title: str) -> str:
        """
        提取单一章节的内容，支持灵活匹配
        """
        try:
            # 清理章节标题，移除可能的括号和特殊字符
            clean_title = section_title.strip()
            
            # 尝试多种匹配策略
            patterns_to_try = [
                # 完全匹配
                clean_title,
                # 如果包含括号，提取括号内容
                None,
                # 如果包含中文数字，尝试匹配
                None
            ]
            
            # 如果标题包含括号，提取括号内的内容
            if '（' in clean_title and '）' in clean_title:
                bracket_content = clean_title[clean_title.find('（')+1:clean_title.find('）')]
                if bracket_content:
                    patterns_to_try[1] = bracket_content
            
            # 如果标题包含数字编号，尝试提取主要部分
            if '、' in clean_title:
                main_part = clean_title.split('、', 1)[-1].strip()
                if main_part:
                    patterns_to_try[2] = main_part
            
            # 过滤掉None值
            patterns_to_try = [p for p in patterns_to_try if p]
            
            for pattern_text in patterns_to_try:
                # 尝试匹配一级标题
                pattern_h1 = rf"(?m)^\s*#\s*.*{re.escape(pattern_text)}.*$([\s\S]*?)(?=^\s*#\s|\Z)"
                match = re.search(pattern_h1, document_content)
                
                if match:
                    content_without_title = (match.group(1) or '').strip()
                    self.logger.debug(f"找到一级标题章节: {pattern_text} (原标题: {section_title})")
                    return content_without_title
                
                # 尝试匹配二级标题
                pattern_h2 = rf"(?m)^\s*##\s*.*{re.escape(pattern_text)}.*$([\s\S]*?)(?=^\s*##\s|^\s*#\s|\Z)"
                match = re.search(pattern_h2, document_content)
                
                if match:
                    content_without_title = (match.group(1) or '').strip()
                    self.logger.debug(f"找到二级标题章节: {pattern_text} (原标题: {section_title})")
                    return content_without_title
                
                # 尝试匹配三级标题
                pattern_h3 = rf"(?m)^\s*###\s*.*{re.escape(pattern_text)}.*$([\s\S]*?)(?=^\s*###\s|^\s*##\s|^\s*#\s|\Z)"
                match = re.search(pattern_h3, document_content)
                
                if match:
                    content_without_title = (match.group(1) or '').strip()
                    self.logger.debug(f"找到三级标题章节: {pattern_text} (原标题: {section_title})")
                    return content_without_title
            
            self.logger.warning(f"未找到章节: {section_title}")
            return ""
        except Exception as e:
            self.logger.error(f"提取单一章节内容失败: {e}")
            return ""
    
    def _extract_child_section(self, parent_content: str, child_title: str) -> str:
        """
        在父章节内容中提取子章节
        """
        try:
            # 在父章节内容中查找子章节（二级标题）
            pattern_h2 = rf"(?m)^\s*##\s*{re.escape(child_title)}\s*$([\s\S]*?)(?=^\s*##\s|^\s*#\s|\Z)"
            match = re.search(pattern_h2, parent_content)
            
            if match:
                content_without_title = (match.group(1) or '').strip()
                self.logger.debug(f"在父章节中找到二级标题: {child_title}")
                return content_without_title
            
            # 如果没找到二级标题，尝试匹配三级标题
            pattern_h3 = rf"(?m)^\s*###\s*{re.escape(child_title)}\s*$([\s\S]*?)(?=^\s*###\s|^\s*##\s|^\s*#\s|\Z)"
            match = re.search(pattern_h3, parent_content)
            
            if match:
                content_without_title = (match.group(1) or '').strip()
                self.logger.debug(f"在父章节中找到三级标题: {child_title}")
                return content_without_title
            else:
                self.logger.warning(f"在父章节中未找到子章节: {child_title}")
                return ""
        except Exception as e:
            self.logger.error(f"提取子章节内容失败: {e}")
            return ""
    
    def regenerate_section_with_thesis(self, section_title: str, original_content: str, 
                                     consistency_issue: Dict, thesis_data: Dict) -> Dict[str, Any]:
        """
        基于论点一致性问题重新生成章节
        
        Args:
            section_title: 章节标题
            original_content: 原始章节内容
            consistency_issue: 一致性问题信息
            thesis_data: 核心论点数据
            
        Returns:
            Dict[str, Any]: 生成结果
        """
        self.logger.info(f"开始重新生成章节: {section_title}")
        
        # 构建基于论点一致性的修正提示词
        prompt = self._build_thesis_correction_prompt(
            section_title, original_content, consistency_issue, thesis_data
        )
        
        try:
            import time
            start_time = time.time()
            
            # 使用线程本地客户端调用API进行修正
            client = self._get_client()
            completion = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": config.openrouter_http_referer,
                    "X-Title": config.openrouter_x_title,
                },
                extra_body={},
                model=config.openrouter_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=config.content_correction_temperature,
                max_tokens=config.max_tokens
            )
            
            response_content = completion.choices[0].message.content
            content = response_content.strip()
            
            # 清洗内容，移除图片/表格/媒体相关内容
            content = self._sanitize_content_remove_media(content)
            
            generation_time = time.time() - start_time
            
            result = {
                'content': content,
                'quality_score': 0.9,  # 基于论点修正，质量较高
                'word_count': len(content),
                'generation_time': f"{generation_time:.2f}s",
                'feedback': f'已根据论点一致性问题进行修正: {consistency_issue.get("issue_type", "")}',
                'subtitle': section_title,
                'original_issue': consistency_issue,
                'thesis_alignment': 'improved'
            }
            
            self.logger.info(f"章节修正完成: {section_title} ({result['word_count']}字)")
            return result
            
        except Exception as e:
            self.logger.error(f"重新生成章节失败: {e}")
            return {
                'content': f"[修正失败: {str(e)}]",
                'quality_score': 0.0,
                'word_count': 0,
                'generation_time': "0.00s",
                'feedback': f"修正失败: {str(e)}",
                'subtitle': section_title,
                'original_issue': consistency_issue,
                'thesis_alignment': 'failed'
            }
    
    def _build_thesis_correction_prompt(self, section_title: str, original_content: str, 
                                      consistency_issue: Dict, thesis_data: Dict) -> str:
        """
        构建基于论点一致性的修正提示词
        """
        main_thesis = thesis_data.get('main_thesis', '')
        supporting_arguments = thesis_data.get('supporting_arguments', [])
        key_concepts = thesis_data.get('key_concepts', [])
        
        issue_type = consistency_issue.get('issue_type', '')
        issue_description = consistency_issue.get('description', '')
        suggestion = consistency_issue.get('suggestion', '')
        
        issue_type_guidance = {
            "contradiction": "消除与核心论点的直接冲突，调整论述方向使其支持核心论点",
            "irrelevant": "增强与核心论点的关联，明确本章节如何服务于核心论点",
            "weak_support": "加强论据和逻辑链条，提供更有力的支撑证据",
            "unclear": "明确表达本章节与核心论点的关系，清晰阐述支撑作用"
        }
        
        guidance = issue_type_guidance.get(issue_type, "确保内容与核心论点保持一致")
        
        prompt = f"""你是一位专业的学术论文编辑和逻辑专家，请根据核心论点修正以下章节内容，确保其与核心论点保持逻辑一致。

【核心论点信息】
主要论点: {main_thesis}
支撑论据: {', '.join(supporting_arguments)}
关键概念: {', '.join(key_concepts)}

【章节标题】: {section_title}

【原始内容】:
{original_content}

【发现的一致性问题】:
问题类型: {issue_type}
问题描述: {issue_description}
修正建议: {suggestion}

【修正指导原则】:
{guidance}

【修正要求】:
1. 确保修正后的内容与核心论点"{main_thesis}"保持高度一致
2. 在修正过程中体现以下支撑论据: {', '.join(supporting_arguments[:3])}
3. 适当融入关键概念: {', '.join(key_concepts[:3])}
4. 保持专业、客观、严谨的学术写作风格
5. 确保逻辑清晰、论证有力、结构合理
6. 仅输出修正后的正文内容，不要包含任何标题、图片、表格或媒体相关信息
7. 字数建议控制在800-1200字之间，段落之间用一个空行分隔

请直接输出修正后的章节正文内容，确保其完全服务于核心论点："""
        
        return prompt
    
    def _regenerate_section_worker(self, section_data: Tuple[str, str, Dict, Dict]) -> Tuple[str, Dict[str, Any]]:
        """
        工作线程中执行的章节重新生成任务
        
        Args:
            section_data: (section_title, original_content, consistency_issue, thesis_data)
            
        Returns:
            Tuple[str, Dict[str, Any]]: (section_title, result)
        """
        section_title, original_content, consistency_issue, thesis_data = section_data
        
        try:
            thread_id = threading.current_thread().ident
            self.logger.info(f"📝 [线程-{thread_id}] 开始处理章节: {section_title}")
            
            result = self.regenerate_section_with_thesis(
                section_title, original_content, consistency_issue, thesis_data
            )
            
            # 更新进度
            success = result.get('thesis_alignment') != 'failed'
            self._update_progress(completed=success, failed=not success)
            
            self.logger.info(f"✅ [线程-{thread_id}] 章节处理完成: {section_title}")
            return section_title, result
            
        except Exception as e:
            self.logger.error(f"❌ [线程-{thread_id}] 章节处理失败: {section_title} - {e}")
            self._update_progress(completed=False, failed=True)
            
            # 返回错误结果
            error_result = {
                'content': f"[并行处理失败: {str(e)}]",
                'quality_score': 0.0,
                'word_count': 0,
                'generation_time': "0.00s",
                'feedback': f"并行处理失败: {str(e)}",
                'subtitle': section_title,
                'original_issue': consistency_issue,
                'thesis_alignment': 'failed'
            }
            return section_title, error_result
    
    def regenerate_sections_parallel(self, sections_data: List[Tuple[str, str, Dict, Dict]]) -> Dict[str, Dict[str, Any]]:
        """
        并行重新生成多个章节
        
        Args:
            sections_data: 章节数据列表 [(section_title, original_content, consistency_issue, thesis_data), ...]
            
        Returns:
            Dict[str, Dict[str, Any]]: 重新生成的章节结果
        """
        if not sections_data:
            return {}
        
        # 初始化进度
        with self._lock:
            self._progress['total_sections'] = len(sections_data)
            self._progress['completed_sections'] = 0
            self._progress['failed_sections'] = 0
        
        self.logger.info(f"🚀 开始并行重新生成 {len(sections_data)} 个章节（最大工作线程: {self.max_workers}）")
        
        regenerated_sections = {}
        
        # 使用ThreadPoolExecutor进行并行处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_section = {
                executor.submit(self._regenerate_section_worker, section_data): section_data[0]
                for section_data in sections_data
            }
            
            # 收集结果
            for future in as_completed(future_to_section):
                section_title = future_to_section[future]
                try:
                    result_section_title, result = future.result()
                    regenerated_sections[result_section_title] = result
                except Exception as e:
                    self.logger.error(f"❌ 线程池任务异常: {section_title} - {e}")
                    # 添加错误结果
                    regenerated_sections[section_title] = {
                        'content': f"[线程池异常: {str(e)}]",
                        'quality_score': 0.0,
                        'word_count': 0,
                        'generation_time': "0.00s",
                        'feedback': f"线程池异常: {str(e)}",
                        'subtitle': section_title,
                        'thesis_alignment': 'failed'
                    }
        
        # 输出统计信息
        with self._lock:
            total = self._progress['total_sections']
            completed = self._progress['completed_sections']
            failed = self._progress['failed_sections']
            
            self.logger.info(
                f"✅ 并行重新生成完成: 总计 {total} 个章节, "
                f"成功 {completed} 个, 失败 {failed} 个"
            )
        
        return regenerated_sections
    
    def _sanitize_content_remove_media(self, content: str) -> str:
        """
        清洗模型输出，移除图片/表格/媒体相关段落与Markdown标记
        """
        import re

        if not content:
            return content

        cleaned_lines: list[str] = []
        for line in content.splitlines():
            stripped = line.strip()

            if not stripped:
                cleaned_lines.append(line)
                continue

            # 标题行
            if stripped.startswith('#'):
                continue

            # 表格相关
            if stripped.startswith('### 相关表格资料') or stripped.startswith('|'):
                continue

            # 图片相关
            if (stripped.startswith('### 相关图片资料') or 
                stripped == '相关图片资料' or 
                stripped.startswith('相关图片资料') or
                stripped.startswith('图片描述:') or 
                stripped.startswith('图片来源:')):
                continue

            # Markdown 图片或链接
            if (re.search(r'!\[.*?\]\(.*?\)', stripped) or 
                re.search(r'\[[^\]]+\]\(https?://[^\)]+\)', stripped, flags=re.IGNORECASE)):
                continue

            cleaned_lines.append(line)

        # 合并并去除多余空行
        cleaned_text = '\n'.join(cleaned_lines)
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()
        return cleaned_text
    
    def regenerate_complete_document(self, analysis_file: str, document_file: str, 
                                   output_dir: str = None) -> Dict[str, Any]:
        """
        重新生成完整文档
        
        Args:
            analysis_file: 一致性分析结果文件路径
            document_file: 原始文档文件路径
            output_dir: 输出目录（可选）
            
        Returns:
            Dict[str, Any]: 重新生成的结果
        """
        # 加载一致性分析结果和原始文档
        consistency_data, thesis_data = self.load_consistency_analysis(analysis_file)
        if not consistency_data:
            return {'error': '无法加载一致性分析结果'}
        
        document_content, json_data = self.load_original_document(document_file)
        if not document_content:
            return {'error': '无法加载原始文档'}
        
        consistency_issues = consistency_data.get('consistency_issues', [])
        
        if not consistency_issues:
            self.logger.info("没有发现需要修正的一致性问题")
            return {'message': '文档论点一致性良好，无需修正'}
        
        # 准备并行处理的数据
        sections_data = []
        
        for issue in consistency_issues:
            section_title = issue.get('section_title', '')
            
            if not section_title:
                continue
            
            # 提取原始章节内容
            original_content = ""
            if json_data:
                # 从JSON结构中提取
                try:
                    for part in json_data.get('report_guide', []):
                        for sec in part.get('sections', []):
                            if sec.get('subtitle', '').strip() == section_title.strip():
                                original_content = (sec.get('generated_content') or '').strip()
                                break
                except:
                    pass
            
            if not original_content:
                # 从Markdown内容中提取
                original_content = self.extract_section_content(document_content, section_title)
            
            if original_content:
                # 添加到并行处理列表
                sections_data.append((section_title, original_content, issue, thesis_data))
        
        # 使用并行处理重新生成章节
        regenerated_sections = self.regenerate_sections_parallel(sections_data)
        
        # 生成完整的修正后文档
        complete_document = self._generate_complete_document(
            document_content, json_data, regenerated_sections, thesis_data
        )
        
        # 保存结果
        if output_dir:
            saved_files = self._save_regeneration_results(
                regenerated_sections, complete_document, thesis_data, output_dir
            )
            return {
                'regenerated_sections': regenerated_sections,
                'complete_document': complete_document,
                'saved_files': saved_files,
                'sections_count': len(regenerated_sections)
            }
        
        return {
            'regenerated_sections': regenerated_sections,
            'complete_document': complete_document,
            'sections_count': len(regenerated_sections)
        }
    
    def _generate_complete_document(self, original_content: str, json_data: Dict, 
                                  regenerated_sections: Dict, thesis_data: Dict) -> str:
        """
        生成完整的修正后文档
        
        Args:
            original_content: 原始文档内容
            json_data: 原始JSON数据
            regenerated_sections: 重新生成的章节
            thesis_data: 核心论点数据
            
        Returns:
            str: 完整的修正后文档
        """
        self.logger.info("开始生成完整的修正后文档")
        
        # 如果有JSON数据，基于JSON结构生成
        if json_data and 'report_guide' in json_data:
            return self._generate_from_json_structure(json_data, regenerated_sections, thesis_data)
        else:
            # 基于Markdown内容生成
            return self._generate_from_markdown_content(original_content, regenerated_sections, thesis_data)
    
    def _generate_from_json_structure(self, json_data: Dict, regenerated_sections: Dict, 
                                    thesis_data: Dict) -> str:
        """
        基于JSON结构生成完整文档
        """
        document_lines = []
        
        # 添加文档标题和论点说明
        if json_data.get('title'):
            document_lines.append(f"# {json_data['title']}")
            document_lines.append("")
        
        # 添加核心论点说明
        main_thesis = thesis_data.get('main_thesis', '')
        if main_thesis:
            document_lines.append("## 📋 核心论点")
            document_lines.append(f"**本文档的核心论点**: {main_thesis}")
            document_lines.append("")
            document_lines.append("*以下各章节内容均围绕此核心论点展开，确保逻辑一致性。*")
            document_lines.append("")
        
        # 遍历JSON结构生成内容
        report_guide = json_data.get('report_guide', [])
        
        for part in report_guide:
            part_title = part.get('title', '')
            if part_title:
                document_lines.append(f"# {part_title}")
                document_lines.append("")
            
            sections = part.get('sections', [])
            for section in sections:
                subtitle = section.get('subtitle', '')
                
                if subtitle:
                    document_lines.append(f"## {subtitle}")
                    document_lines.append("")
                    
                    # 使用修正后的内容或原始内容
                    if subtitle in regenerated_sections:
                        content = regenerated_sections[subtitle]['content']
                        document_lines.append("*[本章节已根据论点一致性要求进行修正]*")
                        document_lines.append("")
                    else:
                        content = section.get('generated_content', '')
                    
                    if content:
                        document_lines.append(content)
                        document_lines.append("")
                    
                    # 添加图片和表格（如果有）
                    if section.get('retrieved_image'):
                        document_lines.append("### 相关图片资料")
                        document_lines.append("")
                        for img in section['retrieved_image']:
                            if isinstance(img, dict):
                                desc = img.get('description', '')
                                url = img.get('url', '')
                                if desc and url:
                                    document_lines.append(f"![{desc}]({url})")
                        document_lines.append("")
                    
                    if section.get('retrieved_table'):
                        document_lines.append("### 相关表格资料")
                        document_lines.append("")
                        for table in section['retrieved_table']:
                            if isinstance(table, str):
                                document_lines.append(table)
                        document_lines.append("")
        
        return "\n".join(document_lines)
    
    def _generate_from_markdown_content(self, original_content: str, regenerated_sections: Dict, 
                                      thesis_data: Dict) -> str:
        """
        基于Markdown内容生成完整文档
        """
        lines = original_content.split('\n')
        new_lines = []
        current_section = None
        in_section_content = False
        
        # 添加核心论点说明
        main_thesis = thesis_data.get('main_thesis', '')
        if main_thesis:
            new_lines.extend([
                "## 📋 核心论点",
                f"**本文档的核心论点**: {main_thesis}",
                "",
                "*以下各章节内容均围绕此核心论点展开，确保逻辑一致性。*",
                "",
            ])
        
        for line in lines:
            # 检查是否是标题（一级、二级、三级）
            if line.startswith('### '):
                # 三级标题处理
                if current_section and current_section in regenerated_sections:
                    # 添加修正后的内容
                    new_lines.append("*[本章节已根据论点一致性要求进行修正]*")
                    new_lines.append("")
                    new_lines.append(regenerated_sections[current_section]['content'])
                    new_lines.append("")
                
                # 开始新章节
                current_section = line[4:].strip()
                new_lines.append(line)
                new_lines.append("")
                in_section_content = True
                
                # 如果这个章节需要修正，跳过原始内容
                if current_section in regenerated_sections:
                    continue
                    
            elif line.startswith('## '):
                # 二级标题处理
                if current_section and current_section in regenerated_sections:
                    # 添加修正后的内容
                    new_lines.append("*[本章节已根据论点一致性要求进行修正]*")
                    new_lines.append("")
                    new_lines.append(regenerated_sections[current_section]['content'])
                    new_lines.append("")
                
                # 开始新章节
                current_section = line[3:].strip()
                new_lines.append(line)
                new_lines.append("")
                in_section_content = True
                
                # 如果这个章节需要修正，跳过原始内容
                if current_section in regenerated_sections:
                    continue
            
            elif line.startswith('# ') or (current_section and current_section in regenerated_sections and in_section_content):
                # 一级标题或需要修正的章节内容，直接跳过原始内容
                if line.startswith('# '):
                    in_section_content = False
                    new_lines.append(line)
                continue
            else:
                # 其他内容直接添加
                new_lines.append(line)
        
        # 处理最后一个章节
        if current_section and current_section in regenerated_sections:
            new_lines.append("*[本章节已根据论点一致性要求进行修正]*")
            new_lines.append("")
            new_lines.append(regenerated_sections[current_section]['content'])
        
        return "\n".join(new_lines)
    
    def _save_regeneration_results(self, regenerated_sections: Dict, complete_document: str, 
                                 thesis_data: Dict, output_dir: str) -> Dict[str, str]:
        """
        保存重新生成的结果（简化版，只保存完整文档）
        
        Returns:
            Dict[str, str]: 保存的文件路径
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved_files = {}
            
            # 只保存完整的修正后文档
            complete_doc_file = os.path.join(output_dir, f"thesis_corrected_complete_document_{timestamp}.md")
            with open(complete_doc_file, 'w', encoding='utf-8') as f:
                f.write(complete_document)
            saved_files['complete_document'] = complete_doc_file
            
            self.logger.info(f"完整修正后文档已保存到: {complete_doc_file}")
            return saved_files
            
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")
            return {}
    
    def _generate_correction_summary(self, regenerated_sections: Dict, thesis_data: Dict) -> str:
        """
        生成修正摘要报告
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        main_thesis = thesis_data.get('main_thesis', '')
        
        lines = [
            "# 论点一致性修正摘要报告",
            "",
            f"**修正时间**: {timestamp}",
            f"**核心论点**: {main_thesis}",
            f"**修正章节数**: {len(regenerated_sections)}",
            "",
            "## 📊 修正统计",
            ""
        ]
        
        # 统计问题类型
        issue_types = {}
        total_words = 0
        
        for section_title, result in regenerated_sections.items():
            issue = result.get('original_issue', {})
            issue_type = issue.get('issue_type', 'unknown')
            
            if issue_type not in issue_types:
                issue_types[issue_type] = 0
            issue_types[issue_type] += 1
            
            total_words += result.get('word_count', 0)
        
        lines.extend([
            f"**修正问题类型分布**:",
            ""
        ])
        
        for issue_type, count in issue_types.items():
            type_names = {
                'contradiction': '直接矛盾',
                'irrelevant': '偏离主题', 
                'weak_support': '论证薄弱',
                'unclear': '表述不清'
            }
            type_name = type_names.get(issue_type, issue_type)
            lines.append(f"- {type_name}: {count} 个章节")
        
        lines.extend([
            "",
            f"**总修正字数**: {total_words:,} 字",
            "",
            "## 📋 修正章节列表",
            ""
        ])
        
        for i, (section_title, result) in enumerate(regenerated_sections.items(), 1):
            issue = result.get('original_issue', {})
            lines.extend([
                f"### {i}. {section_title}",
                f"**原始问题**: {issue.get('issue_type', '')} ({issue.get('severity', '')})",
                f"**修正质量**: {result.get('quality_score', 0):.2f}",
                f"**修正字数**: {result.get('word_count', 0)} 字",
                f"**论点对齐**: {result.get('thesis_alignment', '未知')}",
                ""
            ])
        
        lines.extend([
            "## 💡 修正效果",
            "",
            "通过本次论点一致性修正，文档的以下方面得到了改善：",
            "",
            "1. **逻辑一致性**: 所有章节现在都围绕核心论点展开",
            "2. **论证强度**: 消除了与核心论点矛盾的内容",
            "3. **主题聚焦**: 减少了偏离主题的论述",
            "4. **表达清晰**: 明确了各章节与核心论点的关系",
            "",
            "## 📁 输出文件",
            "",
            "- `thesis_corrected_sections_*.json` - 修正后章节详细数据",
            "- `thesis_corrected_sections_*.md` - 修正后章节可读格式", 
            "- `thesis_corrected_complete_document_*.md` - 完整修正后文档",
            "- `thesis_correction_summary_*.md` - 本摘要报告",
            "",
            "---",
            "*本报告由Gauz论点一致性Agent自动生成*"
        ])
        
        return "\n".join(lines)


def main():
    """
    主函数
    """
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('thesis_document_regeneration.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 检查命令行参数
    if len(sys.argv) < 3:
        print("用法: python document_regenerator.py <一致性分析文件> <原始文档文件> [输出目录] [最大工作线程数]")
        print("示例: python document_regenerator.py consistency_analysis_document.json document.json ./outputs 5")
        return
    
    analysis_file = sys.argv[1]
    document_file = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "./thesis_regenerated_outputs"
    max_workers = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    
    print(f"📋 一致性分析文件: {analysis_file}")
    print(f"📄 原始文档文件: {document_file}")
    print(f"📁 输出目录: {output_dir}")
    print(f"💻 最大工作线程数: {max_workers}")
    print()
    
    # 创建重新生成器（支持多线程）
    regenerator = ThesisDocumentRegenerator(max_workers=max_workers)
    
    # 执行重新生成
    print(f"🚀 开始基于论点一致性重新生成文档（并行处理，最大{max_workers}个线程）...")
    results = regenerator.regenerate_complete_document(
        analysis_file=analysis_file,
        document_file=document_file,
        output_dir=output_dir
    )
    
    if 'error' in results:
        print(f"❌ 重新生成失败: {results['error']}")
        return
    
    if 'message' in results:
        print(f"ℹ️ {results['message']}")
        return
    
    print(f"\n✅ 文档重新生成完成！")
    print(f"   修正章节数: {results['sections_count']}")
    
    if 'saved_files' in results:
        print(f"\n📁 输出文件:")
        for file_type, file_path in results['saved_files'].items():
            print(f"   {file_type}: {file_path}")
    
    print(f"\n🎉 完整的修正后文档已生成，确保所有内容围绕核心论点展开！")


if __name__ == "__main__":
    main()
