"""
简化的论点一致性检查系统配置管理器
"""

import os
from typing import Optional, List
from pathlib import Path


class ThesisAgentConfig:
    """简化的论点一致性检查Agent配置类"""
    
    def __init__(self, env_file: Optional[str] = None):
        """初始化配置"""
        self._load_env_file(env_file)
    
    def _load_env_file(self, env_file: Optional[str] = None):
        """加载.env文件"""
        if env_file is None:
            # 尝试在当前目录查找.env文件
            current_dir = Path(__file__).parent
            env_file = str(current_dir / '.env')
        
        if env_file and os.path.exists(env_file):
            self._parse_env_file(env_file)
    
    def _parse_env_file(self, env_file: str):
        """解析.env文件"""
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if value:
                            os.environ[key] = value
        except Exception as e:
            print(f"警告：无法加载.env文件 {env_file}: {e}")
    
    # API配置
    @property
    def openrouter_api_key(self) -> str:
        return os.getenv('OPENROUTER_API_KEY')
    
    @property
    def openrouter_base_url(self) -> str:
        return os.getenv('OPENROUTER_BASE_URL')
    
    @property
    def openrouter_model(self) -> str:
        return os.getenv('OPENROUTER_MODEL')
    
    @property
    def openrouter_http_referer(self) -> str:
        return os.getenv('OPENROUTER_HTTP_REFERER', '')
    
    @property
    def openrouter_x_title(self) -> str:
        return os.getenv('OPENROUTER_X_TITLE', '')
    
    # 模型参数
    @property
    def thesis_extraction_temperature(self) -> float:
        return float(os.getenv('THESIS_EXTRACTION_TEMPERATURE', '0.1'))
    
    @property
    def consistency_check_temperature(self) -> float:
        return float(os.getenv('CONSISTENCY_CHECK_TEMPERATURE', '0.1'))
    
    @property
    def content_correction_temperature(self) -> float:
        return float(os.getenv('CONTENT_CORRECTION_TEMPERATURE', '0.2'))
    
    @property
    def max_tokens(self) -> int:
        return int(os.getenv('MAX_TOKENS', '4000'))
    
    # 输出配置
    @property
    def default_output_dir(self) -> str:
        return os.getenv('DEFAULT_OUTPUT_DIR', './test_results')
    
    @property
    def log_level(self) -> str:
        return os.getenv('LOG_LEVEL', 'INFO')
    
    @property
    def log_file(self) -> str:
        return os.getenv('LOG_FILE', 'thesis_consistency_check.log')
    
    @property
    def output_encoding(self) -> str:
        return os.getenv('OUTPUT_ENCODING', 'utf-8')
    
    @property
    def timestamp_format(self) -> str:
        return os.getenv('TIMESTAMP_FORMAT', '%Y%m%d_%H%M%S')
    
    # 处理配置
    @property
    def default_auto_correct(self) -> bool:
        return os.getenv('DEFAULT_AUTO_CORRECT', 'true').lower() == 'true'
    
    @property
    def api_timeout(self) -> int:
        return int(os.getenv('API_TIMEOUT', '60'))
    
    @property
    def api_retry_count(self) -> int:
        return int(os.getenv('API_RETRY_COUNT', '3'))
    
    # 多线程配置
    @property
    def max_workers(self) -> int:
        return int(os.getenv('MAX_WORKERS', '5'))
    
    @property
    def enable_parallel_processing(self) -> bool:
        return os.getenv('ENABLE_PARALLEL_PROCESSING', 'true').lower() == 'true'
    
    def validate_config(self) -> List[str]:
        """验证配置"""
        errors = []
        if not self.openrouter_api_key:
            errors.append("OPENROUTER_API_KEY 未设置")
        return errors
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("📋 论点一致性检查Agent配置:")
        print(f"   API模型: {self.openrouter_model}")
        print(f"   输出目录: {self.default_output_dir}")
        print(f"   自动修正: {self.default_auto_correct}")
        print(f"   最大工作线程: {self.max_workers}")
        print(f"   并行处理: {self.enable_parallel_processing}")
        
        errors = self.validate_config()
        if errors:
            print("⚠️ 配置问题:")
            for error in errors:
                print(f"   - {error}")
        else:
            print("✅ 配置验证通过")


# 全局配置实例
config = ThesisAgentConfig()


def load_config(env_file: Optional[str] = None) -> ThesisAgentConfig:
    """
    加载配置
    
    Args:
        env_file: .env文件路径
        
    Returns:
        ThesisAgentConfig: 配置实例
    """
    return ThesisAgentConfig(env_file)


if __name__ == "__main__":
    # 测试配置加载
    config = load_config()
    config.print_config_summary()
