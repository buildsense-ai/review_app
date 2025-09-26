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

from models import TaskStatus, OptimizationResult, SectionResult
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
                                 modifications_applied: list, table_optimizations_applied: list) -> Dict[str, SectionResult]:
        """生成统一格式的章节结果"""
        unified_sections = {}
        
        # 解析原始内容的章节
        original_sections = self._parse_sections(original_content)
        # 解析优化后内容的章节
        optimized_sections = self._parse_sections(optimized_content)
        
        # 为每个章节生成结果
        for section_title, original_section_content in original_sections.items():
            optimized_section_content = optimized_sections.get(section_title, original_section_content)
            
            # 查找该章节的修改建议
            suggestion = ""
            for mod in modifications_applied:
                if mod.get('subtitle') == section_title or mod.get('section_title') == section_title:
                    suggestion = mod.get('suggestion', mod.get('instruction', ''))
                    break
            
            # 查找表格优化建议
            for table_opt in table_optimizations_applied:
                if table_opt.get('section_title') == section_title:
                    if suggestion:
                        suggestion += "; " + table_opt.get('table_opportunity', '')
                    else:
                        suggestion = table_opt.get('table_opportunity', '')
                    break
            
            if not suggestion:
                suggestion = "无需修改"
            
            # 计算字数
            word_count = len(optimized_section_content.replace(' ', '').replace('\n', ''))
            
            unified_sections[section_title] = SectionResult(
                section_title=section_title,
                original_content=original_section_content,
                suggestion=suggestion,
                regenerated_content=optimized_section_content,
                word_count=word_count,
                status="success"
            )
        
        return unified_sections
    
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
                
                result_paths = self.optimizer.regenerate_and_merge_document(
                    evaluation_file=analysis_file_path,
                    document_file=temp_file_path,
                    output_dir="./test_results",
                    auto_merge=False
                )
                optimized_file_path = result_paths.get('regenerated_sections')
                
                # 读取优化结果
                with open(optimized_file_path, 'r', encoding='utf-8') as f:
                    optimized_content = f.read()
                
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
                
                # 构建结果
                result = OptimizationResult(
                    original_content=task_info.content,
                    optimized_content=optimized_content,
                    analysis_summary=analysis_data.get('analysis_summary', '优化完成'),
                    sections_modified=len(analysis_data.get('modification_instructions', [])),
                    tables_optimized=len(analysis_data.get('table_opportunities', [])),
                    modifications_applied=analysis_data.get('modification_instructions', []),
                    table_optimizations_applied=analysis_data.get('table_opportunities', []),
                    processing_time=processing_time,
                    unified_sections=unified_sections
                )
                
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
