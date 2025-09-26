#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一AI服务路由系统启动脚本
"""

import os
import sys
import uvicorn
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import get_config

def main():
    """主函数"""
    # 加载配置
    config = get_config()
    
    # 打印配置摘要
    print("🚀 启动统一AI服务路由系统")
    config.print_config_summary()
    
    # 确保必要的目录存在
    os.makedirs(config.default_output_dir, exist_ok=True)
    os.makedirs("./temp_files", exist_ok=True)
    
    # 启动服务器
    print("\n🌐 启动Web服务器...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=config.log_level.lower(),
        access_log=True
    )

if __name__ == "__main__":
    main()
