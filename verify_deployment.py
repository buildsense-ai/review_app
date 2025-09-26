#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署验证脚本
验证项目是否准备好部署到云端
"""

import os
import sys
from pathlib import Path

def check_file_exists(file_path, description):
    """检查文件是否存在"""
    if Path(file_path).exists():
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - 文件不存在")
        return False

def check_directory_exists(dir_path, description):
    """检查目录是否存在"""
    if Path(dir_path).is_dir():
        print(f"✅ {description}: {dir_path}")
        return True
    else:
        print(f"❌ {description}: {dir_path} - 目录不存在")
        return False

def main():
    """主验证函数"""
    print("🔍 开始部署验证...")
    print("=" * 50)
    
    all_checks_passed = True
    
    # 检查核心文件
    core_files = [
        (".gitignore", "Git忽略文件"),
        ("README.md", "项目说明文档"),
        ("router/main.py", "主应用程序"),
        ("router/requirements.txt", "依赖文件"),
        ("router/config.py", "配置文件"),
        ("router/.env.example", "环境配置示例"),
    ]
    
    print("\n📁 检查核心文件:")
    for file_path, description in core_files:
        if not check_file_exists(file_path, description):
            all_checks_passed = False
    
    # 检查路由文件
    router_files = [
        ("router/routers/final_review_router.py", "文档优化路由"),
        ("router/routers/thesis_agent_router.py", "论点检查路由"),
        ("router/routers/web_agent_router.py", "论据评估路由"),
    ]
    
    print("\n🔀 检查路由文件:")
    for file_path, description in router_files:
        if not check_file_exists(file_path, description):
            all_checks_passed = False
    
    # 检查服务目录
    service_dirs = [
        ("final_review_agent_app", "文档优化服务"),
        ("thesis_agent_app", "论点检查服务"),
        ("web_agent_app", "论据评估服务"),
    ]
    
    print("\n📂 检查服务目录:")
    for dir_path, description in service_dirs:
        if not check_directory_exists(dir_path, description):
            all_checks_passed = False
    
    # 检查Python导入
    print("\n🐍 检查Python导入:")
    try:
        sys.path.append('router')
        from main import app
        print("✅ 主应用导入成功")
    except Exception as e:
        print(f"❌ 主应用导入失败: {e}")
        all_checks_passed = False
    
    # 检查环境配置
    print("\n⚙️ 检查环境配置:")
    try:
        from dotenv import load_dotenv
        load_dotenv('router/.env')
        
        api_key = os.getenv('OPENROUTER_API_KEY')
        model = os.getenv('OPENROUTER_MODEL')
        
        if api_key and api_key != 'your_api_key_here':
            print(f"✅ API密钥已配置")
            print(f"✅ 使用模型: {model}")
        else:
            print("⚠️  API密钥未配置或使用默认值")
            print("   请在云端部署时配置 .env 文件")
            
    except Exception as e:
        print(f"⚠️  环境配置检查失败: {e}")
        print("   请确保在云端部署时正确配置环境变量")
    
    # 最终结果
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("🎉 所有检查通过！项目已准备好部署到云端")
        print("\n📋 部署步骤:")
        print("1. 克隆仓库: git clone https://github.com/buildsense-ai/review_agent.git")
        print("2. 进入目录: cd review_agent")
        print("3. 配置环境: cd router && cp .env.example .env && nano .env")
        print("4. 安装依赖: pip install -r requirements.txt")
        print("5. 启动服务: nohup python3 main.py > ../logs/app.log 2>&1 &")
        print("6. 验证部署: curl http://localhost:8000/health")
    else:
        print("❌ 部分检查失败，请修复后再部署")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
