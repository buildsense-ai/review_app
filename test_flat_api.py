#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试扁平化API端点
测试流程：
1. 提交异步任务 (pipeline-async)
2. 轮询任务状态
3. 获取扁平化结果 (result-flat)
"""

import requests
import time
import json

# API配置
BASE_URL = "http://localhost:8010"
REDUNDANCY_API = f"{BASE_URL}/api/redundancy-agent"
TABLE_API = f"{BASE_URL}/api/table-agent"

# 测试文档内容
TEST_DOCUMENT = """
# 项目概述

## 一、项目名称

本项目正式名称为：生活方式对睡眠模式影响的量化分析与干预策略研究。

本项目旨在深入探讨个体生活方式与睡眠模式之间的内在联系，通过量化分析方法揭示其影响机制。研究核心要素聚焦于"生活方式"与"睡眠模式"。

本研究强调科学性和严谨性，同时突出其在实际应用层面的价值。通过对生活方式如何具体影响睡眠模式进行量化研究。

## 二、研究背景

当前社会中，睡眠问题日益严重。许多人面临睡眠质量下降的困扰。睡眠质量的下降影响了人们的生活质量。

随着生活节奏加快，人们的生活方式发生了巨大变化。生活方式的改变对睡眠产生了深远影响。因此，研究生活方式与睡眠的关系具有重要意义。

## 三、研究目标

本研究的主要目标是探讨生活方式对睡眠的影响。我们希望通过量化分析，揭示两者之间的关系。

具体而言，研究将分析饮食、运动、作息等生活方式因素。这些因素如何影响睡眠质量是本研究的核心问题。

通过本研究，我们期望为改善睡眠质量提供科学依据。这些依据将有助于制定有效的干预策略。
"""

def test_redundancy_flat_api():
    """测试冗余优化的扁平化API"""
    print("=" * 60)
    print("测试冗余优化扁平化API")
    print("=" * 60)
    
    # 1. 提交异步任务
    print("\n[步骤 1] 提交异步任务...")
    payload = {
        "document_content": TEST_DOCUMENT,
        "document_title": "测试文档",
        "filename": "test.md"
    }
    
    response = requests.post(f"{REDUNDANCY_API}/v1/pipeline-async", json=payload)
    if response.status_code != 200:
        print(f"❌ 提交任务失败: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    task_id = result.get("task_id")
    print(f"✅ 任务已提交，task_id: {task_id}")
    
    # 2. 轮询任务状态
    print("\n[步骤 2] 轮询任务状态...")
    max_attempts = 60
    attempt = 0
    
    while attempt < max_attempts:
        time.sleep(2)
        attempt += 1
        
        response = requests.get(f"{REDUNDANCY_API}/v1/task/{task_id}")
        if response.status_code != 200:
            print(f"❌ 查询任务状态失败: {response.status_code}")
            return
        
        task_status = response.json()
        status = task_status.get("status")
        progress = task_status.get("progress", 0)
        message = task_status.get("message", "")
        
        print(f"  [{attempt}] 状态: {status}, 进度: {progress:.1f}%, 消息: {message}")
        
        if status == "completed":
            print("✅ 任务完成")
            break
        elif status == "failed":
            error = task_status.get("error", "未知错误")
            print(f"❌ 任务失败: {error}")
            return
    else:
        print("❌ 任务超时")
        return
    
    # 3. 获取嵌套结构结果（原有API）
    print("\n[步骤 3] 获取嵌套结构结果...")
    response = requests.get(f"{REDUNDANCY_API}/v1/result/{task_id}")
    if response.status_code != 200:
        print(f"❌ 获取嵌套结果失败: {response.status_code}")
        print(response.text)
        return
    
    nested_result = response.json()
    print(f"✅ 嵌套结构结果获取成功")
    print(f"  结构: {list(nested_result.keys())}")
    
    # 统计有多少modified的章节
    modified_count = 0
    for part_name, sections in nested_result.items():
        for section_name, content in sections.items():
            if isinstance(content, dict) and content.get("status") == "modified":
                modified_count += 1
    print(f"  包含 {modified_count} 个已修改的章节")
    
    # 4. 获取扁平化结果（新API）
    print("\n[步骤 4] 获取扁平化结果...")
    response = requests.get(f"{REDUNDANCY_API}/v1/result-flat/{task_id}")
    if response.status_code != 200:
        print(f"❌ 获取扁平化结果失败: {response.status_code}")
        print(response.text)
        return
    
    flat_result = response.json()
    print(f"✅ 扁平化结果获取成功")
    
    # 验证扁平化结果结构
    if "chapters" not in flat_result:
        print(f"❌ 扁平化结果格式错误: 缺少 'chapters' 字段")
        return
    
    chapters = flat_result["chapters"]
    print(f"  包含 {len(chapters)} 个章节")
    
    # 显示前2个章节的详细信息
    for i, chapter in enumerate(chapters[:2], 1):
        print(f"\n  章节 {i}:")
        print(f"    - original_text 长度: {len(chapter.get('original_text', ''))} 字符")
        print(f"    - edit_text 长度: {len(chapter.get('edit_text', ''))} 字符")
        print(f"    - comment 长度: {len(chapter.get('comment', ''))} 字符")
        if chapter.get('comment'):
            print(f"    - comment 内容: {chapter['comment'][:100]}...")
    
    # 打印完整的扁平化结果（JSON字符串）
    print("\n" + "=" * 60)
    print("完整的扁平化结果输出：")
    print("=" * 60)
    print(json.dumps(flat_result, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

def test_table_flat_api():
    """测试表格优化的扁平化API"""
    print("=" * 60)
    print("测试表格优化扁平化API")
    print("=" * 60)
    
    # 1. 提交异步任务
    print("\n[步骤 1] 提交异步任务...")
    payload = {
        "document_content": TEST_DOCUMENT,
        "document_title": "测试文档",
        "filename": "test.md"
    }
    
    response = requests.post(f"{TABLE_API}/v1/pipeline-async", json=payload)
    if response.status_code != 200:
        print(f"❌ 提交任务失败: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    task_id = result.get("task_id")
    print(f"✅ 任务已提交，task_id: {task_id}")
    
    # 2. 轮询任务状态
    print("\n[步骤 2] 轮询任务状态...")
    max_attempts = 60
    attempt = 0
    
    while attempt < max_attempts:
        time.sleep(2)
        attempt += 1
        
        response = requests.get(f"{TABLE_API}/v1/task/{task_id}")
        if response.status_code != 200:
            print(f"❌ 查询任务状态失败: {response.status_code}")
            return
        
        task_status = response.json()
        status = task_status.get("status")
        progress = task_status.get("progress", 0)
        message = task_status.get("message", "")
        
        print(f"  [{attempt}] 状态: {status}, 进度: {progress:.1f}%, 消息: {message}")
        
        if status == "completed":
            print("✅ 任务完成")
            break
        elif status == "failed":
            error = task_status.get("error", "未知错误")
            print(f"❌ 任务失败: {error}")
            return
    else:
        print("❌ 任务超时")
        return
    
    # 3. 获取扁平化结果
    print("\n[步骤 3] 获取扁平化结果...")
    response = requests.get(f"{TABLE_API}/v1/result-flat/{task_id}")
    if response.status_code != 200:
        print(f"❌ 获取扁平化结果失败: {response.status_code}")
        print(response.text)
        return
    
    flat_result = response.json()
    print(f"✅ 扁平化结果获取成功")
    
    if "chapters" in flat_result:
        chapters = flat_result["chapters"]
        print(f"  包含 {len(chapters)} 个优化的章节")
        
        # 打印完整的扁平化结果（JSON字符串）
        print("\n" + "=" * 60)
        print("完整的扁平化结果输出：")
        print("=" * 60)
        print(json.dumps(flat_result, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        if test_type == "redundancy":
            test_redundancy_flat_api()
        elif test_type == "table":
            test_table_flat_api()
        else:
            print(f"未知的测试类型: {test_type}")
            print("用法: python test_flat_api.py [redundancy|table]")
    else:
        # 默认测试冗余优化
        test_redundancy_flat_api()
        
        # 询问是否继续测试表格优化
        print("\n是否继续测试表格优化API? (y/n): ", end="")
        choice = input().strip().lower()
        if choice == 'y':
            print("\n")
            test_table_flat_api()

