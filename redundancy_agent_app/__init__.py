#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redundancy Agent - 文档冗余内容分析和优化
"""

__version__ = "1.0.0"
__author__ = "Gauz Document Agent Team"

from .redundancy_analyzer import RedundancyAnalyzer
from .redundancy_modifier import RedundancyModifier
from .run_redundancy_agent import RedundancyAgent

__all__ = [
    "RedundancyAnalyzer",
    "RedundancyModifier", 
    "RedundancyAgent"
]

