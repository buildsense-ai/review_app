#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步任务管理器
负责管理文档优化任务的生命周期
"""

import asyncio
import uuid
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from models import TaskStatus, OptimizationResult
from run_document_optimizer import DocumentOptimizer
import re
import json
import os


@dataclass
class TaskInfo:
    """任务信息数据类"""
    task_id: str
    status: TaskStatus
    content: str
    filename: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    message: str = "任务已创建"
    result: Optional[OptimizationResult] = None
    error_message: Optional[str] = None


class TaskManager:
    """异步任务管理器"""
    
    def __init__(self, max_workers: int = 3):
        """
        初始化任务管理器
        
        Args:
            max_workers: 最大并发工作线程数
        """
        self.tasks: Dict[str, TaskInfo] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.optimizer = DocumentOptimizer()
        self.logger = logging.getLogger(__name__)
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        self.logger.info(f"✅ TaskManager初始化完成，最大并发数: {max_workers}")
    
    def _generate_unified_sections(self, original_content: str, optimized_content: str, 
                                 modifications_applied: list, table_optimizations_applied: list) -> Dict[str, dict]:
        """生成统一格式的章节结果 - 使用一级标题嵌套二级标题的结构"""
        unified_sections = {}
        
        # 解析原始内容的层级章节
        original_hierarchy = self._parse_hierarchical_sections(original_content)
        # 解析优化后内容的层级章节
        optimized_hierarchy = self._parse_hierarchical_sections(optimized_content)
        
        # 为每个一级标题生成结果
        for h1_title, h2_sections in original_hierarchy.items():
            unified_sections[h1_title] = {}
            
            # 为每个二级标题生成结果
            for h2_title, original_section_content in h2_sections.items():
                optimized_section_content = optimized_hierarchy.get(h1_title, {}).get(h2_title, original_section_content)
                
                # 查找该章节的修改建议
                suggestion = ""
                
                # 调试信息
                self.logger.info(f"查找章节 '{h2_title}' 的修改建议")
                self.logger.info(f"可用的modification_instructions: {modifications_applied}")
                self.logger.info(f"可用的table_optimizations: {table_optimizations_applied}")
                
                for mod in modifications_applied:
                    # 处理单章节建议 (subtitle)
                    if 'subtitle' in mod:
                        mod_title = mod.get('subtitle', '')
                        if (mod_title == h2_title or 
                            mod_title == f"{h1_title} {h2_title}" or
                            h2_title in mod_title or
                            mod_title in h2_title):
                            suggestion = mod.get('suggestion', mod.get('instruction', ''))
                            self.logger.info(f"找到单章节匹配建议: {mod_title} -> {suggestion[:100]}...")
                            break
                    
                    # 处理跨章节建议 (subtitles)
                    elif 'subtitles' in mod:
                        subtitles = mod.get('subtitles', [])
                        for subtitle in subtitles:
                            if (subtitle == h2_title or 
                                subtitle == f"{h1_title} {h2_title}" or
                                h2_title in subtitle or
                                subtitle in h2_title):
                                suggestion = mod.get('suggestion', mod.get('instruction', ''))
                                self.logger.info(f"找到跨章节匹配建议: {subtitle} -> {suggestion[:100]}...")
                                break
                        if suggestion:  # 如果找到了跨章节建议，跳出外层循环
                            break
                
                # 查找表格优化建议
                for table_opt in table_optimizations_applied:
                    table_title = table_opt.get('section_title', '')
                    if (table_title == h2_title or 
                        table_title == f"{h1_title} {h2_title}" or
                        h2_title in table_title or
                        table_title in h2_title):
                        table_suggestion = table_opt.get('table_opportunity', '')
                        if suggestion:
                            suggestion += "; " + table_suggestion
                        else:
                            suggestion = table_suggestion
                        self.logger.info(f"找到匹配的表格优化建议: {table_title} -> {table_suggestion[:100]}...")
                        break
                
                # 如果没有找到任何AI建议，跳过该章节
                if not suggestion:
                    self.logger.info(f"章节 '{h2_title}' 没有找到AI建议，跳过")
                    continue
                
                # 检查内容是否真的被修改了
                # 去除格式差异进行比较
                original_clean = original_section_content.strip().replace('\n\n', '\n')
                optimized_clean = optimized_section_content.strip().replace('\n\n', '\n')
                
                # 如果内容完全相同（除了格式），说明LLM修改可能失败了
                if original_clean == optimized_clean:
                    self.logger.warning(f"章节 '{h2_title}' 有建议但内容未改变，可能LLM修改失败")
                    # 可以选择跳过或者标记状态
                    continue
                
                # 只有有修改建议且内容真正变化的章节才包含在输出中
                # 计算字数
                word_count = len(optimized_section_content.replace(' ', '').replace('\n', ''))
                
                # 确保一级标题存在
                if h1_title not in unified_sections:
                    unified_sections[h1_title] = {}
                
                unified_sections[h1_title][h2_title] = {
                    "original_content": original_section_content,
                    "suggestion": suggestion,
                    "regenerated_content": optimized_section_content,
                    "word_count": word_count,
                    "status": "success"
                }
        
        return unified_sections
    
    def _parse_hierarchical_sections(self, content: str) -> Dict[str, Dict[str, str]]:
        """解析Markdown内容的层级章节结构"""
        hierarchy = {}
        lines = content.split('\n')
        
        current_h1 = None
        current_h2 = None
        current_content = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # 检测一级标题 (# 标题)
            if line_stripped.startswith('# ') and not line_stripped.startswith('## '):
                # 保存之前的二级标题内容
                if current_h1 and current_h2:
                    if current_h1 not in hierarchy:
                        hierarchy[current_h1] = {}
                    hierarchy[current_h1][current_h2] = '\n'.join(current_content).strip()
                
                # 开始新的一级标题
                current_h1 = line_stripped[2:].strip()
                current_h2 = None
                current_content = []
                
            # 检测二级标题 (## 标题)
            elif line_stripped.startswith('## '):
                # 保存之前的二级标题内容
                if current_h1 and current_h2:
                    if current_h1 not in hierarchy:
                        hierarchy[current_h1] = {}
                    hierarchy[current_h1][current_h2] = '\n'.join(current_content).strip()
                
                # 开始新的二级标题
                if current_h1:  # 确保有一级标题
                    current_h2 = line_stripped[3:].strip()
                    current_content = [line]  # 包含标题行
                else:
                    # 如果没有一级标题，创建默认的
                    current_h1 = "文档内容"
                    current_h2 = line_stripped[3:].strip()
                    current_content = [line]
                    
            else:
                # 普通内容行
                if current_h1 and current_h2:
                    current_content.append(line)
                elif current_h1 and not current_h2:
                    # 一级标题下没有二级标题的内容，跳过空行，等待二级标题
                    if line.strip():  # 只有非空行才创建默认二级标题
                        current_h2 = "概述"
                        current_content = [line]
        
        # 保存最后一个章节
        if current_h1 and current_h2:
            if current_h1 not in hierarchy:
                hierarchy[current_h1] = {}
            hierarchy[current_h1][current_h2] = '\n'.join(current_content).strip()
        
        return hierarchy

    def _parse_sections(self, content: str) -> Dict[str, str]:
        """解析Markdown内容的章节"""
        sections = {}
        
        # 使用正则表达式匹配二级标题
        section_pattern = r'^## (.+?)$'
        lines = content.split('\n')
        
        current_section = None
        current_content = []
        
        for line in lines:
            match = re.match(section_pattern, line)
            if match:
                # 保存前一个章节
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # 开始新章节
                current_section = match.group(1).strip()
                current_content = [line]  # 包含标题行
            else:
                if current_section:
                    current_content.append(line)
        
        # 保存最后一个章节
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def create_task(self, content: str, filename: Optional[str] = None, 
                   options: Optional[Dict[str, Any]] = None) -> str:
        """
        创建新的优化任务
        
        Args:
            content: 文档内容
            filename: 文件名（可选）
            options: 优化选项（可选）
            
        Returns:
            str: 任务ID
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        task_info = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            content=content,
            filename=filename or f"document_{int(time.time())}.md",
            options=options or {},
            message="任务已创建，等待处理"
        )
        
        self.tasks[task_id] = task_info
        self.logger.info(f"📝 创建新任务: {task_id}")
        
        return task_id
    
    async def start_task(self, task_id: str) -> bool:
        """
        开始执行任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功开始
        """
        if task_id not in self.tasks:
            self.logger.error(f"❌ 任务不存在: {task_id}")
            return False
        
        task_info = self.tasks[task_id]
        
        if task_info.status != TaskStatus.PENDING:
            self.logger.warning(f"⚠️ 任务状态不正确: {task_id}, 当前状态: {task_info.status}")
            return False
        
        # 更新任务状态
        task_info.status = TaskStatus.PROCESSING
        task_info.started_at = datetime.now()
        task_info.message = "任务开始处理"
        task_info.progress = 10.0
        
        self.logger.info(f"🚀 开始处理任务: {task_id}")
        
        # 在线程池中异步执行任务
        loop = asyncio.get_event_loop()
        loop.run_in_executor(self.executor, self._process_task, task_id)
        
        return True
    
    def _process_task(self, task_id: str):
        """
        处理任务的核心逻辑（在线程池中执行）
        
        Args:
            task_id: 任务ID
        """
        task_info = self.tasks[task_id]
        
        try:
            self.logger.info(f"🔄 处理任务 {task_id}: 开始文档优化")
            
            # 更新进度：开始分析
            task_info.progress = 20.0
            task_info.message = "正在分析文档质量..."
            
            start_time = time.time()
            
            # 创建临时文件
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(task_info.content)
                temp_file_path = temp_file.name
            
            try:
                # 步骤1：全局分析
                self.logger.info(f"📊 任务 {task_id}: 执行全局分析")
                task_info.progress = 40.0
                task_info.message = "正在进行全局分析..."
                
                analysis_file_path = self.optimizer.step1_analyze_document(
                    temp_file_path, 
                    output_dir="./test_results"
                )
                
                # 步骤2：分章节文档优化（使用更好的方法）
                self.logger.info(f"🔧 任务 {task_id}: 执行分章节文档优化")
                task_info.progress = 70.0
                task_info.message = "正在分章节优化文档内容..."
                
                # 直接获取优化后的内容，不生成中间文件
                regeneration_results = self.optimizer.regenerate_document_sections(analysis_file_path, temp_file_path)
                self.logger.info(f"🔧 regeneration_results 包含 {len(regeneration_results)} 个章节")
                for section_title, result in regeneration_results.items():
                    status = result.get('status', 'unknown')
                    self.logger.info(f"  - {section_title}: {status}")
                
                optimized_content = self.optimizer._generate_markdown_content(regeneration_results, temp_file_path)
                self.logger.info(f"🔧 优化后内容长度: {len(optimized_content)} 字符")
                
                # 读取分析结果
                import json
                with open(analysis_file_path, 'r', encoding='utf-8') as f:
                    analysis_data = json.load(f)
                
                processing_time = time.time() - start_time
                
                # 生成统一格式的章节结果
                unified_sections = self._generate_unified_sections(
                    task_info.content,
                    optimized_content,
                    analysis_data.get('modification_instructions', []),
                    analysis_data.get('table_opportunities', [])
                )
                
                # 生成两个输出文件
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # 1. 生成unified_sections JSON文件
                unified_sections_file = f"./test_results/unified_sections_{timestamp}.json"
                os.makedirs("./test_results", exist_ok=True)
                with open(unified_sections_file, 'w', encoding='utf-8') as f:
                    json.dump(unified_sections, f, ensure_ascii=False, indent=2)
                
                # 2. 生成优化后的markdown文件
                optimized_md_file = f"./test_results/optimized_content_{task_id}.md"
                with open(optimized_md_file, 'w', encoding='utf-8') as f:
                    f.write(optimized_content)
                
                # 构建简化的结果 - 只返回文件路径和基本信息
                result = {
                    "unified_sections_file": unified_sections_file,
                    "optimized_content_file": optimized_md_file,
                    "processing_time": processing_time,
                    "sections_count": len(unified_sections),
                    "service_type": "final_review",
                    "message": f"已生成2个文件: {os.path.basename(unified_sections_file)}, {os.path.basename(optimized_md_file)}"
                }
                
                # 更新任务状态
                task_info.status = TaskStatus.COMPLETED
                task_info.completed_at = datetime.now()
                task_info.progress = 100.0
                task_info.message = "文档优化完成"
                task_info.result = result
                
                self.logger.info(f"✅ 任务 {task_id} 完成，处理时间: {processing_time:.2f}秒")
                
                # 清理临时文件
                try:
                    os.unlink(temp_file_path)
                    os.unlink(analysis_file_path)
                    os.unlink(optimized_file_path)
                except:
                    pass  # 忽略清理错误
                    
            except Exception as e:
                # 清理临时文件
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                raise e
                
        except Exception as e:
            # 处理失败
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = datetime.now()
            task_info.progress = 0.0
            task_info.message = "任务处理失败"
            task_info.error_message = str(e)
            
            self.logger.error(f"❌ 任务 {task_id} 失败: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[TaskInfo]: 任务信息，如果不存在则返回None
        """
        return self.tasks.get(task_id)
    
    def get_task_result(self, task_id: str) -> Optional[OptimizationResult]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[OptimizationResult]: 优化结果，如果任务未完成或不存在则返回None
        """
        task_info = self.tasks.get(task_id)
        if task_info and task_info.status == TaskStatus.COMPLETED:
            return task_info.result
        return None
    
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功删除
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            self.logger.info(f"🗑️ 删除任务: {task_id}")
            return True
        return False
    
    def list_tasks(self) -> Dict[str, TaskInfo]:
        """
        列出所有任务
        
        Returns:
            Dict[str, TaskInfo]: 任务字典
        """
        return self.tasks.copy()
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """
        清理已完成的旧任务
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        current_time = datetime.now()
        tasks_to_delete = []
        
        for task_id, task_info in self.tasks.items():
            if task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                if task_info.completed_at:
                    age_hours = (current_time - task_info.completed_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        tasks_to_delete.append(task_id)
        
        for task_id in tasks_to_delete:
            self.delete_task(task_id)
        
        if tasks_to_delete:
            self.logger.info(f"🧹 清理了 {len(tasks_to_delete)} 个过期任务")
    
    def shutdown(self):
        """关闭任务管理器"""
        self.logger.info("🔄 正在关闭任务管理器...")
        self.executor.shutdown(wait=True)
        self.logger.info("✅ 任务管理器已关闭")


# 全局任务管理器实例
task_manager = TaskManager()
