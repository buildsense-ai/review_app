#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一的API客户端工厂
用于创建和管理OpenAI/OpenRouter客户端
"""

import os
from openai import OpenAI
from typing import Optional


class APIClientFactory:
    """API客户端工厂"""
    
    @staticmethod
    def create_openrouter_client(
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 300
    ) -> OpenAI:
        """
        创建OpenRouter客户端
        
        Args:
            api_key: API密钥（如果不提供，从环境变量获取）
            base_url: API基础URL（如果不提供，使用默认值）
            timeout: 请求超时时间（秒）
            
        Returns:
            OpenAI: 配置好的OpenAI客户端
            
        Raises:
            ValueError: 如果API密钥未提供且环境变量中也没有
        """
        if api_key is None:
            api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not api_key:
            raise ValueError("OpenRouter API密钥未设置。请设置环境变量 OPENROUTER_API_KEY")
        
        if base_url is None:
            base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        
        return OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout
        )
    
    @staticmethod
    def create_openai_client(
        api_key: Optional[str] = None,
        timeout: int = 300
    ) -> OpenAI:
        """
        创建标准OpenAI客户端
        
        Args:
            api_key: API密钥（如果不提供，从环境变量获取）
            timeout: 请求超时时间（秒）
            
        Returns:
            OpenAI: 配置好的OpenAI客户端
            
        Raises:
            ValueError: 如果API密钥未提供且环境变量中也没有
        """
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError("OpenAI API密钥未设置。请设置环境变量 OPENAI_API_KEY")
        
        return OpenAI(
            api_key=api_key,
            timeout=timeout
        )
    
    @staticmethod
    def get_model_name(model_type: str = "default") -> str:
        """
        获取模型名称
        
        Args:
            model_type: 模型类型 (default, fast, powerful, etc.)
            
        Returns:
            str: 模型名称
        """
        models = {
            "default": os.getenv("DEFAULT_MODEL", "anthropic/claude-3.5-sonnet"),
            "fast": os.getenv("FAST_MODEL", "anthropic/claude-3-haiku"),
            "powerful": os.getenv("POWERFUL_MODEL", "anthropic/claude-3-opus"),
            "gpt4": os.getenv("GPT4_MODEL", "openai/gpt-4-turbo"),
        }
        
        return models.get(model_type, models["default"])

