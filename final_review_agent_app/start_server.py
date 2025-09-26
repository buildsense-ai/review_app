#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI服务启动脚本
"""

import os
import sys
import uvicorn
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """启动FastAPI服务"""
    
    # 检查环境变量
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("⚠️  警告: 未设置OPENROUTER_API_KEY环境变量")
        print("   请在.env文件中设置API密钥，或通过环境变量设置")
        print("   示例: export OPENROUTER_API_KEY=your_api_key_here")
        print()
    
    # 确保必要的目录存在
    os.makedirs("./temp_results", exist_ok=True)
    os.makedirs("./test_results", exist_ok=True)
    
    print("🚀 启动文档优化API服务...")
    print("📖 API文档: http://localhost:8000/docs")
    print("🔍 ReDoc文档: http://localhost:8000/redoc")
    print("❤️  健康检查: http://localhost:8000/health")
    print()
    
    # 启动服务
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()
