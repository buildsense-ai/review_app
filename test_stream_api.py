#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 SSE 流式端点
测试流程：
1. 连接到流式端点
2. 实时接收 SSE 事件
3. 打印进度信息和最终结果
"""

import requests
import json
import sys

# API配置
BASE_URL = "http://localhost:8010"
REDUNDANCY_STREAM_API = f"{BASE_URL}/api/redundancy-agent/v1/pipeline-stream"
TABLE_STREAM_API = f"{BASE_URL}/api/table-agent/v1/pipeline-stream"

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


def parse_sse_line(line: str) -> tuple:
    """
    解析 SSE 行
    
    Returns:
        (event_type, data_dict) 或 (None, None)
    """
    line = line.strip()
    if not line:
        return None, None
    
    if line.startswith('event:'):
        event_type = line[6:].strip()
        return ('event', event_type)
    elif line.startswith('data:'):
        data_json = line[5:].strip()
        try:
            data = json.loads(data_json)
            return ('data', data)
        except json.JSONDecodeError:
            return ('data', data_json)
    
    return None, None


def test_redundancy_stream():
    """测试冗余优化的流式端点"""
    print("=" * 80)
    print("测试冗余优化流式端点")
    print("=" * 80)
    
    payload = {
        "document_content": TEST_DOCUMENT,
        "document_title": "测试文档",
        "filename": "test.md"
    }
    
    print(f"\n发送请求到: {REDUNDANCY_STREAM_API}")
    print(f"文档长度: {len(TEST_DOCUMENT)} 字符\n")
    
    try:
        response = requests.post(
            REDUNDANCY_STREAM_API,
            json=payload,
            stream=True,
            headers={'Accept': 'text/event-stream'},
            timeout=300
        )
        
        if response.status_code != 200:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(response.text)
            return
        
        print("✅ 连接成功，开始接收 SSE 事件...\n")
        print("-" * 80)
        
        current_event = None
        result_data = None
        
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            parse_type, parse_value = parse_sse_line(line)
            
            if parse_type == 'event':
                current_event = parse_value
            elif parse_type == 'data' and isinstance(parse_value, dict):
                event_type = current_event or 'unknown'
                
                if event_type == 'progress':
                    status = parse_value.get('status', '')
                    message = parse_value.get('message', '')
                    progress = parse_value.get('progress', 0)
                    print(f"[{progress:3d}%] {status:12s} | {message}")
                
                elif event_type == 'result':
                    result_data = parse_value
                    chapters = result_data.get('chapters', [])
                    summary = result_data.get('summary', '')
                    print(f"\n✅ 收到最终结果:")
                    print(f"   {summary}")
                    print(f"   包含 {len(chapters)} 个优化章节")
                
                elif event_type == 'end':
                    print(f"\n🎉 处理完成!")
                    break
                
                elif event_type == 'error':
                    error = parse_value.get('error', '')
                    print(f"\n❌ 错误: {error}")
                    break
        
        print("-" * 80)
        
        if result_data and result_data.get('chapters'):
            print("\n详细结果预览（前2个章节）:")
            for i, chapter in enumerate(result_data['chapters'][:2], 1):
                print(f"\n章节 {i}:")
                print(f"  原文长度: {len(chapter.get('original_text', ''))} 字符")
                print(f"  修改后长度: {len(chapter.get('edit_text', ''))} 字符")
                print(f"  修改建议: {chapter.get('comment', '')[:100]}...")
        
        print("\n" + "=" * 80)
        print("冗余优化测试完成")
        print("=" * 80)
        
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保服务器正在运行")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


def test_table_stream():
    """测试表格优化的流式端点"""
    print("\n\n")
    print("=" * 80)
    print("测试表格优化流式端点")
    print("=" * 80)
    
    # 使用包含适合表格化的内容的文档
    table_document = """
# 项目建设内容

## 主要建设内容

1. 综合教学楼：建筑面积 25,000 平方米，用于公共课程教学。
2. 实训大楼：建筑面积 18,000 平方米，配备实训室和实验室。
3. 学生宿舍楼：建筑面积 30,000 平方米，可容纳 3,000 名学生。
4. 食堂：建筑面积 5,000 平方米，提供 6,000 个就餐座位。

## 项目团队配置

为确保项目顺利实施，我们组建了一支专业的团队。团队将设立1名项目经理，全面负责项目规划、进度跟踪和资源协调。技术方面，将配备2名高级工程师，负责核心架构设计和开发工作。此外，还需要1名UI/UX设计师来负责产品界面和用户体验设计，以及1名测试工程师保障软件质量。
"""
    
    payload = {
        "document_content": table_document,
        "document_title": "测试文档 - 表格优化",
        "filename": "test_table.md"
    }
    
    print(f"\n发送请求到: {TABLE_STREAM_API}")
    print(f"文档长度: {len(table_document)} 字符\n")
    
    try:
        response = requests.post(
            TABLE_STREAM_API,
            json=payload,
            stream=True,
            headers={'Accept': 'text/event-stream'},
            timeout=300
        )
        
        if response.status_code != 200:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(response.text)
            return
        
        print("✅ 连接成功，开始接收 SSE 事件...\n")
        print("-" * 80)
        
        current_event = None
        result_data = None
        
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            parse_type, parse_value = parse_sse_line(line)
            
            if parse_type == 'event':
                current_event = parse_value
            elif parse_type == 'data' and isinstance(parse_value, dict):
                event_type = current_event or 'unknown'
                
                if event_type == 'progress':
                    status = parse_value.get('status', '')
                    message = parse_value.get('message', '')
                    progress = parse_value.get('progress', 0)
                    print(f"[{progress:3d}%] {status:12s} | {message}")
                
                elif event_type == 'result':
                    result_data = parse_value
                    chapters = result_data.get('chapters', [])
                    summary = result_data.get('summary', '')
                    print(f"\n✅ 收到最终结果:")
                    print(f"   {summary}")
                    print(f"   包含 {len(chapters)} 个优化章节")
                
                elif event_type == 'end':
                    print(f"\n🎉 处理完成!")
                    break
                
                elif event_type == 'error':
                    error = parse_value.get('error', '')
                    print(f"\n❌ 错误: {error}")
                    break
        
        print("-" * 80)
        
        if result_data and result_data.get('chapters'):
            print("\n详细结果预览（前2个章节）:")
            for i, chapter in enumerate(result_data['chapters'][:2], 1):
                print(f"\n章节 {i}:")
                print(f"  原文长度: {len(chapter.get('original_text', ''))} 字符")
                print(f"  修改后长度: {len(chapter.get('edit_text', ''))} 字符")
                print(f"  修改建议: {chapter.get('comment', '')[:100]}...")
                
                # 显示表格化的内容预览
                edit_text = chapter.get('edit_text', '')
                if '|' in edit_text:
                    print(f"\n  包含表格!")
        
        print("\n" + "=" * 80)
        print("表格优化测试完成")
        print("=" * 80)
        
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保服务器正在运行")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        if test_type == "redundancy":
            test_redundancy_stream()
        elif test_type == "table":
            test_table_stream()
        else:
            print(f"未知的测试类型: {test_type}")
            print("用法: python test_stream_api.py [redundancy|table]")
    else:
        # 默认测试冗余优化
        test_redundancy_stream()
        
        # 询问是否继续测试表格优化
        print("\n是否继续测试表格优化流式API? (y/n): ", end="")
        try:
            choice = input().strip().lower()
            if choice == 'y':
                test_table_stream()
        except KeyboardInterrupt:
            print("\n\n测试已取消")

