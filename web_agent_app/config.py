"""
论据支持度评估系统配置文件
"""

import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 加载统一路由系统的 .env 文件
try:
    from pathlib import Path
    router_env = Path(__file__).parent.parent / "router" / ".env"
    if router_env.exists():
        load_dotenv(router_env)
except Exception:
    pass

# OpenRouter API 配置
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 模型配置
MODEL_NAME = os.getenv("MODEL_NAME") or os.getenv("OPENROUTER_MODEL")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))

# Web搜索API配置
CUSTOM_SEARCH_API_URL = os.getenv("CUSTOM_SEARCH_API_URL", "http://43.139.19.144:8005/search")
CUSTOM_SEARCH_ENGINES = ["serp"]  # 只使用serp搜索引擎
CUSTOM_SEARCH_TIMEOUT = int(os.getenv("CUSTOM_SEARCH_TIMEOUT", "30"))

# 系统配置
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "8000"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# 并行处理配置
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
ENABLE_PARALLEL_SEARCH = os.getenv("ENABLE_PARALLEL_SEARCH", "true").lower() == "true"
ENABLE_PARALLEL_ENHANCEMENT = os.getenv("ENABLE_PARALLEL_ENHANCEMENT", "true").lower() == "true"
ENABLE_PARALLEL_ANALYSIS = os.getenv("ENABLE_PARALLEL_ANALYSIS", "true").lower() == "true"

# 输出配置
OUTPUT_ENCODING = "utf-8"
SAVE_INTERMEDIATE_RESULTS = os.getenv("SAVE_INTERMEDIATE_RESULTS", "true").lower() == "true"
GENERATE_MARKDOWN_OUTPUT = os.getenv("GENERATE_MARKDOWN_OUTPUT", "true").lower() == "true"

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENABLE_COLOR_LOGS = os.getenv("ENABLE_COLOR_LOGS", "true").lower() == "true"
ENABLE_HTTP_LOGS = os.getenv("ENABLE_HTTP_LOGS", "true").lower() == "true"

# 证据评估配置
MIN_EVIDENCE_CREDIBILITY = float(os.getenv("MIN_EVIDENCE_CREDIBILITY", "0.5"))
MIN_EVIDENCE_RELEVANCE = float(os.getenv("MIN_EVIDENCE_RELEVANCE", "0.4"))
MAX_EVIDENCE_PER_CLAIM = int(os.getenv("MAX_EVIDENCE_PER_CLAIM", "10"))

# 内容增强配置
ENHANCEMENT_CONFIDENCE_THRESHOLD = float(os.getenv("ENHANCEMENT_CONFIDENCE_THRESHOLD", "0.6"))
PRESERVE_ORIGINAL_STRUCTURE = os.getenv("PRESERVE_ORIGINAL_STRUCTURE", "true").lower() == "true"
ADD_CITATION_LINKS = os.getenv("ADD_CITATION_LINKS", "true").lower() == "true"
