#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一的任务状态管理器
用于所有router中的后台任务状态跟踪
"""

import time
from typing import Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel


class TaskStatus(BaseModel):
    """任务状态响应模型"""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: float  # 0.0 - 1.0
    message: str
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class TaskManager:
    """统一的任务管理器"""
    
    def __init__(self):
        """初始化任务管理器"""
        self.storage: Dict[str, Dict[str, Any]] = {}
    
    def create_task(self, task_id: str) -> None:
        """
        创建新任务
        
        Args:
            task_id: 任务ID
        """
        self.storage[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'progress': 0.0,
            'message': '任务已创建',
            'result': None,
            'error': None,
            'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'end_time': None
        }
    
    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 进度 (0.0-1.0)
            message: 状态消息
            result: 任务结果
            error: 错误信息
        """
        if task_id not in self.storage:
            self.create_task(task_id)
        
        task = self.storage[task_id]
        
        if status is not None:
            task['status'] = status
        if progress is not None:
            task['progress'] = progress
        if message is not None:
            task['message'] = message
        if result is not None:
            task['result'] = result
        if error is not None:
            task['error'] = error
        
        # 如果任务完成或失败，记录结束时间
        if status in ['completed', 'failed']:
            task['end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态字典，如果不存在返回None
        """
        return self.storage.get(task_id)
    
    def get_task_status(self, task_id: str) -> TaskStatus:
        """
        获取任务状态（返回Pydantic模型）
        
        Args:
            task_id: 任务ID
            
        Returns:
            TaskStatus对象
        """
        task = self.get_task(task_id)
        if task is None:
            return TaskStatus(
                task_id=task_id,
                status="not_found",
                progress=0.0,
                message="任务不存在"
            )
        return TaskStatus(**task)
    
    def task_exists(self, task_id: str) -> bool:
        """
        检查任务是否存在
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 任务是否存在
        """
        return task_id in self.storage
    
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功删除
        """
        if task_id in self.storage:
            del self.storage[task_id]
            return True
        return False
    
    def clear_old_tasks(self, max_age_seconds: int = 3600) -> int:
        """
        清理过期任务
        
        Args:
            max_age_seconds: 任务最大保留时间（秒）
            
        Returns:
            int: 删除的任务数量
        """
        current_time = time.time()
        to_delete = []
        
        for task_id, task in self.storage.items():
            # 检查任务是否已完成或失败
            if task['status'] in ['completed', 'failed'] and task.get('end_time'):
                try:
                    end_time = datetime.strptime(task['end_time'], "%Y-%m-%d %H:%M:%S")
                    age = (datetime.now() - end_time).total_seconds()
                    if age > max_age_seconds:
                        to_delete.append(task_id)
                except (ValueError, TypeError):
                    # 如果时间格式不正确，跳过
                    pass
        
        # 删除过期任务
        for task_id in to_delete:
            del self.storage[task_id]
        
        return len(to_delete)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有任务
        
        Returns:
            Dict[str, Dict]: 所有任务字典
        """
        return self.storage.copy()
    
    def get_running_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有运行中的任务
        
        Returns:
            Dict[str, Dict]: 运行中的任务字典
        """
        return {
            task_id: task
            for task_id, task in self.storage.items()
            if task['status'] in ['pending', 'processing']
        }

