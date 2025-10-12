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
    
    # 确保必要的目录存在（统一输出到router/outputs和router/temp_files）
    router_dir = Path(__file__).parent
    outputs_dir = router_dir / "outputs"
    temp_dir = router_dir / "temp_files"
    
    # 创建各服务的输出目录
    os.makedirs(outputs_dir / "final_review", exist_ok=True)
    os.makedirs(outputs_dir / "thesis", exist_ok=True)
    os.makedirs(outputs_dir / "web_evidence", exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    print(f"✅ 输出目录: {outputs_dir}")
    print(f"✅ 临时目录: {temp_dir}")
    
    # 启动服务器
    print("\n🌐 启动Web服务器...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8010,
        reload=True,
        log_level=config.log_level.lower(),
        access_log=True
    )

if __name__ == "__main__":
    main()
