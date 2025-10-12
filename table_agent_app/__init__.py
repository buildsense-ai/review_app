#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Table Agent - 文档表格优化分析和应用
"""

__version__ = "1.0.0"
__author__ = "Gauz Document Agent Team"

from .table_analyzer import TableAnalyzer
from .table_modifier import TableModifier
from .run_table_agent import TableAgent

__all__ = [
    "TableAnalyzer",
    "TableModifier",
    "TableAgent"
]

