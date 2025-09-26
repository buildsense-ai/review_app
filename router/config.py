#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一AI服务路由系统配置文件
整合三个服务的配置需求
"""

import os
from typing import Optional, List
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class UnifiedConfig:
    """统一配置管理类"""
    
    def __init__(self):
        """初始化配置"""
        self._load_env_variables()
    
    def _load_env_variables(self):
        """加载环境变量"""
        # 尝试从各个服务目录加载.env文件
        current_dir = Path(__file__).parent
        parent_dir = current_dir.parent
        
        env_files = [
            current_dir / '.env',
            parent_dir / 'final_review_agent_app' / '.env',
            parent_dir / 'thesis_agent_app' / '.env',
            parent_dir / 'web_agent_app' / '.env'
        ]
        
        for env_file in env_files:
            if env_file.exists():
                load_dotenv(env_file)
                print(f"✅ 加载配置文件: {env_file}")
    
    # ==================== OpenRouter API 配置 ====================
    
    @property
    def openrouter_api_key(self) -> str:
        """OpenRouter API密钥"""
        return os.getenv('OPENROUTER_API_KEY', '')
    
    @property
    def openrouter_base_url(self) -> str:
        """OpenRouter API基础URL"""
        return os.getenv('OPENROUTER_BASE_URL')
    
    @property
    def openrouter_model(self) -> str:
        """OpenRouter模型名称"""
        return os.getenv('OPENROUTER_MODEL')
    
    @property
    def openrouter_http_referer(self) -> str:
        """OpenRouter HTTP Referer"""
        return os.getenv('OPENROUTER_HTTP_REFERER', '')
    
    @property
    def openrouter_x_title(self) -> str:
        """OpenRouter X-Title"""
        return os.getenv('OPENROUTER_X_TITLE', '')
    
    # ==================== 模型参数配置 ====================
    
    @property
    def temperature(self) -> float:
        """模型温度参数"""
        return float(os.getenv('TEMPERATURE', '0.3'))
    
    @property
    def max_tokens(self) -> int:
        """最大token数"""
        return int(os.getenv('MAX_TOKENS', '4000'))
    
    @property
    def thesis_extraction_temperature(self) -> float:
        """论点提取温度参数"""
        return float(os.getenv('THESIS_EXTRACTION_TEMPERATURE', '0.1'))
    
    @property
    def consistency_check_temperature(self) -> float:
        """一致性检查温度参数"""
        return float(os.getenv('CONSISTENCY_CHECK_TEMPERATURE', '0.1'))
    
    @property
    def content_correction_temperature(self) -> float:
        """内容修正温度参数"""
        return float(os.getenv('CONTENT_CORRECTION_TEMPERATURE', '0.2'))
    
    # ==================== Web搜索配置 ====================
    
    @property
    def custom_search_api_url(self) -> str:
        """自定义搜索API URL"""
        return os.getenv("CUSTOM_SEARCH_API_URL", "http://43.139.19.144:8005/search")
    
    @property
    def custom_search_engines(self) -> List[str]:
        """搜索引擎列表"""
        return ["serp"]  # 只使用serp搜索引擎
    
    @property
    def custom_search_timeout(self) -> int:
        """搜索超时时间"""
        return int(os.getenv("CUSTOM_SEARCH_TIMEOUT", "30"))
    
    # ==================== 系统配置 ====================
    
    @property
    def max_content_length(self) -> int:
        """最大内容长度"""
        return int(os.getenv("MAX_CONTENT_LENGTH", "8000"))
    
    @property
    def max_retries(self) -> int:
        """最大重试次数"""
        return int(os.getenv("MAX_RETRIES", "3"))
    
    @property
    def request_timeout(self) -> int:
        """请求超时时间"""
        return int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    @property
    def api_timeout(self) -> int:
        """API超时时间"""
        return int(os.getenv('API_TIMEOUT', '60'))
    
    @property
    def api_retry_count(self) -> int:
        """API重试次数"""
        return int(os.getenv('API_RETRY_COUNT', '3'))
    
    # ==================== 并行处理配置 ====================
    
    @property
    def max_workers(self) -> int:
        """最大工作线程数"""
        return int(os.getenv("MAX_WORKERS", "5"))
    
    @property
    def enable_parallel_processing(self) -> bool:
        """是否启用并行处理"""
        return os.getenv('ENABLE_PARALLEL_PROCESSING', 'true').lower() == 'true'
    
    @property
    def enable_parallel_search(self) -> bool:
        """是否启用并行搜索"""
        return os.getenv("ENABLE_PARALLEL_SEARCH", "true").lower() == "true"
    
    @property
    def enable_parallel_enhancement(self) -> bool:
        """是否启用并行增强"""
        return os.getenv("ENABLE_PARALLEL_ENHANCEMENT", "true").lower() == "true"
    
    @property
    def enable_parallel_analysis(self) -> bool:
        """是否启用并行分析"""
        return os.getenv("ENABLE_PARALLEL_ANALYSIS", "true").lower() == "true"
    
    # ==================== 输出配置 ====================
    
    @property
    def default_output_dir(self) -> str:
        """默认输出目录"""
        return os.getenv('DEFAULT_OUTPUT_DIR', './test_results')
    
    @property
    def output_encoding(self) -> str:
        """输出编码"""
        return os.getenv('OUTPUT_ENCODING', 'utf-8')
    
    @property
    def timestamp_format(self) -> str:
        """时间戳格式"""
        return os.getenv('TIMESTAMP_FORMAT', '%Y%m%d_%H%M%S')
    
    @property
    def save_intermediate_results(self) -> bool:
        """是否保存中间结果"""
        return os.getenv("SAVE_INTERMEDIATE_RESULTS", "true").lower() == "true"
    
    @property
    def generate_markdown_output(self) -> bool:
        """是否生成Markdown输出"""
        return os.getenv("GENERATE_MARKDOWN_OUTPUT", "true").lower() == "true"
    
    # ==================== 日志配置 ====================
    
    @property
    def log_level(self) -> str:
        """日志级别"""
        return os.getenv('LOG_LEVEL', 'INFO')
    
    @property
    def log_file(self) -> str:
        """日志文件"""
        return os.getenv('LOG_FILE', 'unified_api.log')
    
    @property
    def enable_color_logs(self) -> bool:
        """是否启用彩色日志"""
        return os.getenv("ENABLE_COLOR_LOGS", "true").lower() == "true"
    
    @property
    def enable_http_logs(self) -> bool:
        """是否启用HTTP日志"""
        return os.getenv("ENABLE_HTTP_LOGS", "true").lower() == "true"
    
    # ==================== 处理配置 ====================
    
    @property
    def default_auto_correct(self) -> bool:
        """默认是否自动修正"""
        return os.getenv('DEFAULT_AUTO_CORRECT', 'true').lower() == 'true'
    
    @property
    def min_evidence_credibility(self) -> float:
        """最小证据可信度"""
        return float(os.getenv("MIN_EVIDENCE_CREDIBILITY", "0.5"))
    
    @property
    def min_evidence_relevance(self) -> float:
        """最小证据相关性"""
        return float(os.getenv("MIN_EVIDENCE_RELEVANCE", "0.4"))
    
    @property
    def max_evidence_per_claim(self) -> int:
        """每个论断的最大证据数"""
        return int(os.getenv("MAX_EVIDENCE_PER_CLAIM", "10"))
    
    @property
    def enhancement_confidence_threshold(self) -> float:
        """增强置信度阈值"""
        return float(os.getenv("ENHANCEMENT_CONFIDENCE_THRESHOLD", "0.6"))
    
    @property
    def preserve_original_structure(self) -> bool:
        """是否保持原始结构"""
        return os.getenv("PRESERVE_ORIGINAL_STRUCTURE", "true").lower() == "true"
    
    @property
    def add_citation_links(self) -> bool:
        """是否添加引用链接"""
        return os.getenv("ADD_CITATION_LINKS", "true").lower() == "true"
    
    # ==================== 验证和工具方法 ====================
    
    def validate_config(self) -> List[str]:
        """验证配置"""
        errors = []
        
        if not self.openrouter_api_key:
            errors.append("OPENROUTER_API_KEY 未设置")
        
        if self.max_workers <= 0:
            errors.append("MAX_WORKERS 必须大于0")
        
        if self.temperature < 0 or self.temperature > 2:
            errors.append("TEMPERATURE 必须在0-2之间")
        
        if self.max_tokens <= 0:
            errors.append("MAX_TOKENS 必须大于0")
        
        return errors
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("📋 统一AI服务路由系统配置:")
        print(f"   OpenRouter模型: {self.openrouter_model}")
        print(f"   API密钥: {'已设置' if self.openrouter_api_key else '未设置'}")
        print(f"   输出目录: {self.default_output_dir}")
        print(f"   最大工作线程: {self.max_workers}")
        print(f"   并行处理: {self.enable_parallel_processing}")
        print(f"   自动修正: {self.default_auto_correct}")
        print(f"   日志级别: {self.log_level}")
        
        errors = self.validate_config()
        if errors:
            print("⚠️ 配置问题:")
            for error in errors:
                print(f"   - {error}")
        else:
            print("✅ 配置验证通过")
    
    def get_service_config(self, service_name: str) -> dict:
        """获取特定服务的配置"""
        base_config = {
            "openrouter_api_key": self.openrouter_api_key,
            "openrouter_base_url": self.openrouter_base_url,
            "openrouter_model": self.openrouter_model,
            "max_tokens": self.max_tokens,
            "max_workers": self.max_workers,
            "output_dir": self.default_output_dir,
            "log_level": self.log_level
        }
        
        if service_name == "final_review":
            return {
                **base_config,
                "temperature": self.temperature,
                "enable_parallel": self.enable_parallel_processing
            }
        elif service_name == "thesis_agent":
            return {
                **base_config,
                "thesis_extraction_temperature": self.thesis_extraction_temperature,
                "consistency_check_temperature": self.consistency_check_temperature,
                "content_correction_temperature": self.content_correction_temperature,
                "auto_correct": self.default_auto_correct
            }
        elif service_name == "web_agent":
            return {
                **base_config,
                "temperature": self.temperature,
                "search_api_url": self.custom_search_api_url,
                "search_timeout": self.custom_search_timeout,
                "max_evidence_per_claim": self.max_evidence_per_claim,
                "enable_parallel_search": self.enable_parallel_search
            }
        else:
            return base_config

# 全局配置实例
config = UnifiedConfig()

def get_config() -> UnifiedConfig:
    """获取配置实例"""
    return config

if __name__ == "__main__":
    # 测试配置加载
    config = get_config()
    config.print_config_summary()
