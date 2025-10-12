#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一异常定义 - 用于替代fallback机制
"""


class AgentBaseException(Exception):
    """所有Agent异常的基类"""
    pass


class LLMCallError(AgentBaseException):
    """LLM API调用失败"""
    pass


class DocumentAnalysisError(AgentBaseException):
    """文档分析失败"""
    pass


class DocumentParseError(AgentBaseException):
    """文档解析失败"""
    pass


class EvidenceSearchError(AgentBaseException):
    """证据搜索失败"""
    pass


class SectionGenerationError(AgentBaseException):
    """章节生成失败"""
    pass


class ThesisExtractionError(AgentBaseException):
    """论点提取失败"""
    pass


class ConsistencyCheckError(AgentBaseException):
    """一致性检查失败"""
    pass


class DocumentProcessingError(AgentBaseException):
    """文档处理失败"""
    pass


# 兼容性别名
SharedException = AgentBaseException

