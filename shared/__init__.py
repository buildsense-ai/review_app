#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享模块
统一的工具函数、类和异常定义
"""

from .exceptions import (
    SharedException,
    LLMCallError,
    DocumentAnalysisError,
    DocumentProcessingError
)
from .task_manager import TaskManager, TaskStatus
from .document_parser import DocumentParser
from .json_merger import JSONDocumentMerger, SimpleMarkdownConverter, update_json_sections_inplace
from .api_client_factory import APIClientFactory

__all__ = [
    # Exceptions
    'SharedException',
    'LLMCallError',
    'DocumentAnalysisError',
    'DocumentProcessingError',
    # Task Management
    'TaskManager',
    'TaskStatus',
    # Document Processing
    'DocumentParser',
    'JSONDocumentMerger',
    'SimpleMarkdownConverter',
    'update_json_sections_inplace',
    # API Clients
    'APIClientFactory',
]
