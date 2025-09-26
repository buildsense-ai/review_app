#!/usr/bin/env python3
"""
论据支持度评估系统 FastAPI 服务器启动脚本
"""

import os
import sys
import uvicorn
import argparse
from pathlib import Path

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import fastapi
        import openai
        import requests
        print("✅ 所有依赖已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def check_config():
    """检查配置文件"""
    config_items = []
    
    # 检查.env文件
    env_file = Path(".env")
    if env_file.exists():
        config_items.append("✅ .env文件存在")
    else:
        config_items.append("⚠️ .env文件不存在，将使用默认配置")
    
    # 检查config.py
    config_file = Path("config.py")
    if config_file.exists():
        config_items.append("✅ config.py文件存在")
    else:
        config_items.append("❌ config.py文件不存在")
        return False
    
    for item in config_items:
        print(item)
    
    return True

def create_output_dir():
    """创建输出目录"""
    output_dir = Path("test_results")
    output_dir.mkdir(exist_ok=True)
    print(f"✅ 输出目录已创建: {output_dir.absolute()}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="启动论据支持度评估系统API服务器")
    parser.add_argument("--host", default="0.0.0.0", help="服务器主机地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8001, help="服务器端口 (默认: 8001)")
    parser.add_argument("--reload", action="store_true", help="启用自动重载 (开发模式)")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数 (生产模式)")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"], help="日志级别")
    
    args = parser.parse_args()
    
    print("🚀 论据支持度评估系统 FastAPI 服务器")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查配置
    if not check_config():
        sys.exit(1)
    
    # 创建输出目录
    create_output_dir()
    
    print("\n📋 服务器配置:")
    print(f"   主机地址: {args.host}")
    print(f"   端口: {args.port}")
    print(f"   重载模式: {'开启' if args.reload else '关闭'}")
    print(f"   工作进程: {args.workers}")
    print(f"   日志级别: {args.log_level}")
    
    print(f"\n🌐 服务器将在以下地址启动:")
    print(f"   本地访问: http://localhost:{args.port}")
    print(f"   网络访问: http://{args.host}:{args.port}")
    print(f"   API文档: http://localhost:{args.port}/docs")
    print(f"   ReDoc文档: http://localhost:{args.port}/redoc")
    
    print("\n⚡ 启动服务器...")
    
    try:
        if args.reload:
            # 开发模式
            uvicorn.run(
                "app:app",
                host=args.host,
                port=args.port,
                reload=True,
                log_level=args.log_level
            )
        else:
            # 生产模式
            uvicorn.run(
                "app:app",
                host=args.host,
                port=args.port,
                workers=args.workers,
                log_level=args.log_level
            )
    except KeyboardInterrupt:
        print("\n⚠️ 服务器已停止")
    except Exception as e:
        print(f"\n❌ 服务器启动失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
