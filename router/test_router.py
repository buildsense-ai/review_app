#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一AI服务路由系统测试工具
支持测试三个主要服务：文档优化、论点一致性检查、论据支持度评估
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

class RouterTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        # 使用统一的输出目录
        self.results_dir = Path(__file__).parent / "outputs" / "test_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
    def load_test_document(self, file_path: str = "testmarkdown.md") -> str:
        """加载测试文档"""
        test_file = Path(file_path)
        if not test_file.exists():
            raise FileNotFoundError(f"测试文件 {file_path} 不存在")
        
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"📄 已加载测试文档: {test_file.name}")
        print(f"📊 文档大小: {len(content)} 字符, {len(content.splitlines())} 行")
        return content
    
    def save_result(self, service_name: str, result: Dict[Any, Any], task_id: str = None) -> str:
        """保存测试结果到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if task_id:
            filename = f"{service_name}_{task_id}_{timestamp}.json"
        else:
            filename = f"{service_name}_{timestamp}.json"
        
        result_file = self.results_dir / filename
        
        # 确保目录存在
        self.results_dir.mkdir(exist_ok=True)
        
        # 确保结果是可序列化的
        try:
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"💾 结果已保存到: {result_file}")
            print(f"📊 文件大小: {result_file.stat().st_size} bytes")
            return str(result_file)
        except Exception as e:
            print(f"❌ 保存结果失败: {e}")
            # 尝试保存简化版本
            try:
                simplified_result = {
                    "task_id": result.get("task_id", "unknown"),
                    "status": result.get("status", "unknown"),
                    "timestamp": timestamp,
                    "error": f"原始结果保存失败: {str(e)}",
                    "raw_result": str(result)[:1000]  # 只保存前1000个字符
                }
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(simplified_result, f, ensure_ascii=False, indent=2)
                print(f"💾 简化结果已保存到: {result_file}")
                return str(result_file)
            except Exception as e2:
                print(f"❌ 简化结果保存也失败: {e2}")
                return ""
    
    def test_final_review_agent(self, content: str) -> Dict[Any, Any]:
        """测试文档优化服务"""
        print("\n" + "="*60)
        print("🔧 测试 Final Review Agent (文档优化服务)")
        print("="*60)
        
        # 使用异步接口
        url = f"{self.base_url}/api/final-review/optimize"
        payload = {
            "content": content,
            "filename": "testmarkdown.md",
            "options": {}
        }
        
        try:
            print("🚀 提交文档优化任务...")
            response = requests.post(url, json=payload, timeout=600)  # 10分钟
            
            if response.status_code != 200:
                error_msg = f"任务提交失败: {response.status_code} - {response.text}"
                print(f"❌ {error_msg}")
                return {"error": error_msg}
            
            task_info = response.json()
            task_id = task_info.get("task_id")
            print(f"✅ 任务已提交, Task ID: {task_id}")
            print(f"📊 任务状态: {task_info.get('status')}")
            
            # 轮询任务状态
            status_url = f"{self.base_url}/api/final-review/tasks/{task_id}/status"
            print("⏳ 等待任务完成...")
            
            max_attempts = 120  # 最多等待10分钟 (120 * 5秒 = 600秒)
            attempt = 0
            
            while attempt < max_attempts:
                time.sleep(5)  # 每5秒检查一次
                attempt += 1
                
                # 显示等待进度
                elapsed_time = attempt * 5
                print(f"⏱️  等待中... ({elapsed_time}s / {max_attempts * 5}s)")
                
                try:
                    status_response = requests.get(status_url, timeout=60)  # 1分钟
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status")
                        progress = status_data.get("progress", 0)
                        message = status_data.get("message", "")
                        
                        print(f"📊 任务状态: {current_status}, 进度: {progress}%, 消息: {message}")
                        
                        if current_status == "completed":
                            print("✅ 任务完成!")
                            
                            # 获取任务结果
                            result_url = f"{self.base_url}/api/final-review/tasks/{task_id}/result"
                            result_response = requests.get(result_url, timeout=120)  # 2分钟
                            
                            if result_response.status_code == 200:
                                result_data = result_response.json()
                                
                                # 显示结果信息
                                result = result_data.get("result", {})
                                if result:
                                    print(f"📄 {result.get('message', '处理完成')}")
                                    print(f"⏱️ 处理时间: {result.get('processing_time', 'N/A')} 秒")
                                    print(f"📝 处理章节数: {result.get('sections_count', 'N/A')}")
                                    
                                    # 显示生成的文件路径
                                    if result.get('unified_sections_file'):
                                        print(f"📋 统一章节结果: {result['unified_sections_file']}")
                                    if result.get('optimized_content_file'):
                                        print(f"📄 优化后文档: {result['optimized_content_file']}")
                                else:
                                    print("⚠️ 未获取到结果信息")
                                
                                return result_data
                            else:
                                error_msg = f"获取结果失败: {result_response.status_code}"
                                print(f"❌ {error_msg}")
                                return {"error": error_msg}
                        
                        elif current_status == "failed":
                            error_msg = status_data.get("error_message", "任务失败")
                            print(f"❌ 任务失败: {error_msg}")
                            return {"error": error_msg}
                    
                except requests.exceptions.RequestException as e:
                    print(f"⚠️ 状态查询失败: {e}")
            
            error_msg = f"任务超时，已等待 {max_attempts * 5} 秒 ({max_attempts * 5 // 60} 分钟)，请检查服务器状态或增加超时时间"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
            
        except requests.exceptions.Timeout as e:
            error_msg = f"请求超时: {e}。服务器可能需要更长时间处理，请稍后重试或联系管理员"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
    
    def test_thesis_agent(self, content: str) -> Dict[Any, Any]:
        """测试论点一致性检查服务"""
        print("\n" + "="*60)
        print("🎯 测试 Thesis Agent (论点一致性检查服务)")
        print("="*60)
        
        # 使用异步流水线接口
        url = f"{self.base_url}/api/thesis-agent/v1/pipeline-async"
        payload = {
            "document_content": content,
            "document_title": "测试文档",
            "auto_correct": True
        }
        
        try:
            print("🚀 提交论点一致性检查任务...")
            response = requests.post(url, json=payload, timeout=600)  # 10分钟
            
            if response.status_code != 200:
                error_msg = f"任务提交失败: {response.status_code} - {response.text}"
                print(f"❌ {error_msg}")
                return {"error": error_msg}
            
            task_info = response.json()
            task_id = task_info.get("task_id")
            print(f"✅ 任务已提交, Task ID: {task_id}")
            print(f"📊 任务状态: {task_info.get('status')}")
            
            # 轮询任务状态
            status_url = f"{self.base_url}/api/thesis-agent/v1/task/{task_id}"
            print("⏳ 等待任务完成...")
            
            max_attempts = 120  # 最多等待10分钟 (120 * 5秒 = 600秒)
            attempt = 0
            
            while attempt < max_attempts:
                time.sleep(5)  # 每5秒检查一次
                attempt += 1
                
                try:
                    status_response = requests.get(status_url, timeout=60)  # 1分钟
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status")
                        
                        print(f"📊 任务状态: {current_status}")
                        
                        if current_status == "completed":
                            print("✅ 任务完成!")
                            
                            # 使用新的API端点获取纯净的章节结果
                            print("📥 获取统一章节结果...")
                            result_url = f"{self.base_url}/api/thesis-agent/v1/result/{task_id}"
                            result_response = requests.get(result_url, timeout=60)
                            
                            if result_response.status_code == 200:
                                unified_sections = result_response.json()
                                
                                # 不再保存额外文件，router已经生成了文件
                                
                                # 显示章节结果摘要
                                print("\n📋 统一章节结果摘要:")
                                print("=" * 40)
                                
                                success_count = 0
                                identified_count = 0
                                corrected_count = 0
                                
                                # 处理层级结构：H1 -> H2 -> 章节数据
                                for h1_title, h2_sections in unified_sections.items():
                                    print(f"📚 {h1_title}")
                                    
                                    if isinstance(h2_sections, dict):
                                        for h2_title, section_data in h2_sections.items():
                                            if isinstance(section_data, dict) and 'status' in section_data:
                                                status = section_data.get('status', 'unknown')
                                                word_count = section_data.get('word_count', 0)
                                                suggestion = section_data.get('suggestion', '')
                                                
                                                status_icon = {
                                                    'success': '✅',
                                                    'identified': '⚠️',
                                                    'corrected': '🔧'
                                                }.get(status, '❓')
                                                
                                                print(f"  {status_icon} {h2_title}")
                                                print(f"     状态: {status}, 字数: {word_count}")
                                                if suggestion and not suggestion.startswith("✅"):
                                                    print(f"     建议: {suggestion[:80]}...")
                                                print()
                                                
                                                # 统计各状态数量
                                                if status == 'success':
                                                    success_count += 1
                                                elif status == 'identified':
                                                    identified_count += 1
                                                elif status == 'corrected':
                                                    corrected_count += 1
                                
                                print(f"📊 章节统计: 成功 {success_count}, 发现问题 {identified_count}, 已修正 {corrected_count}")
                                
                                # 不再保存额外文件，router已经生成了文件
                                
                                return unified_sections
                            else:
                                print(f"❌ 获取统一章节结果失败: {result_response.status_code}")
                                # 降级到原始结果（不保存额外文件）
                                result = status_data.get("result", {})
                                print(f"🎯 核心论点: N/A")
                                print(f"🔍 一致性问题数: N/A")
                                print(f"📝 修正章节数: N/A")
                                return status_data
                        
                        elif current_status == "failed":
                            error_msg = status_data.get("error", "任务失败")
                            print(f"❌ 任务失败: {error_msg}")
                            return {"error": error_msg}
                    
                except requests.exceptions.RequestException as e:
                    print(f"⚠️ 状态查询失败: {e}")
            
            error_msg = f"任务超时，已等待 {max_attempts * 5} 秒 ({max_attempts * 5 // 60} 分钟)，请检查服务器状态或增加超时时间"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
            
        except requests.exceptions.Timeout as e:
            error_msg = f"请求超时: {e}。服务器可能需要更长时间处理，请稍后重试或联系管理员"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
    
    def test_web_agent(self, content: str) -> Dict[Any, Any]:
        """测试论据支持度评估服务"""
        print("\n" + "="*60)
        print("🌐 测试 Web Agent (论据支持度评估服务)")
        print("="*60)
        
        # 使用新的证据增强流水线接口
        url = f"{self.base_url}/api/web-agent/v1/evidence-pipeline-async"
        payload = {
            "document_content": content,
            "document_title": "测试文档",
            "max_claims": 10,
            "max_search_results": 5
        }
        
        try:
            print("🚀 提交论据支持度评估任务...")
            response = requests.post(url, json=payload, timeout=600)  # 10分钟
            
            if response.status_code != 200:
                error_msg = f"任务提交失败: {response.status_code} - {response.text}"
                print(f"❌ {error_msg}")
                return {"error": error_msg}
            
            task_info = response.json()
            task_id = task_info.get("task_id")
            print(f"✅ 任务已提交, Task ID: {task_id}")
            print(f"📊 任务状态: {task_info.get('status')}")
            
            # 轮询任务状态
            status_url = f"{self.base_url}/api/web-agent/v1/task/{task_id}"
            print("⏳ 等待任务完成...")
            
            max_attempts = 120  # 最多等待10分钟 (120 * 5秒 = 600秒)
            attempt = 0
            
            while attempt < max_attempts:
                time.sleep(5)  # 每5秒检查一次
                attempt += 1
                
                try:
                    status_response = requests.get(status_url, timeout=60)  # 1分钟
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status")
                        
                        print(f"📊 任务状态: {current_status}")
                        
                        if current_status == "completed":
                            print("✅ 任务完成!")
                            
                            # 使用新的API端点获取纯净的论断结果
                            print("📥 获取论断分析结果...")
                            result_url = f"{self.base_url}/api/web-agent/v1/result/{task_id}"
                            result_response = requests.get(result_url, timeout=60)
                            
                            if result_response.status_code == 200:
                                unified_claims = result_response.json()
                                
                                # 不再保存额外文件，router已经生成了文件
                                
                                # 获取增强后的文档
                                print("📥 获取增强后的文档...")
                                enhanced_url = f"{self.base_url}/api/web-agent/v1/enhanced/{task_id}"
                                enhanced_response = requests.get(enhanced_url, timeout=60)
                                
                                if enhanced_response.status_code == 200:
                                    enhanced_data = enhanced_response.json()
                                    enhanced_document = enhanced_data.get("enhanced_document", "")
                                    
                                    if enhanced_document:
                                        print(f"📄 增强后的文档已获取（不再保存额外文件）")
                                
                                # 显示论断结果摘要
                                print("\n📋 论断分析结果摘要:")
                                print("=" * 40)
                                
                                total_claims = 0
                                enhanced_claims = 0
                                no_evidence_claims = 0
                                
                                for h1_title, h2_sections in unified_claims.items():
                                    print(f"📖 {h1_title}")
                                    if isinstance(h2_sections, dict):
                                        for h2_title, section_data in h2_sections.items():
                                            if isinstance(section_data, dict) and 'status' in section_data:
                                                # 新的数据结构：每个H2章节直接包含section_data
                                                status = section_data.get('status', 'unknown')
                                                suggestion = section_data.get('suggestion', '')
                                                word_count = section_data.get('word_count', 0)
                                                
                                                status_icon = {
                                                    'enhanced': '✅',
                                                    'identified': '⚠️',
                                                    'no_evidence': '❌'
                                                }.get(status, '❓')
                                                
                                                print(f"  {status_icon} {h2_title}: {status} ({word_count} 字)")
                                                if suggestion:
                                                    print(f"    建议: {suggestion}")
                                                
                                                # 统计各状态数量
                                                total_claims += 1
                                                if status == 'enhanced':
                                                    enhanced_claims += 1
                                                elif status in ['no_evidence', 'identified']:
                                                    no_evidence_claims += 1
                                            elif isinstance(section_data, dict):
                                                # 旧的数据结构：H2章节包含多个claims
                                                print(f"  📄 {h2_title}: {len(section_data)} 个论断")
                                                for claim_id, claim_data in section_data.items():
                                                    if isinstance(claim_data, dict):
                                                        status = claim_data.get('status', 'unknown')
                                                        evidence_count = len(claim_data.get('evidence_sources', []))
                                                        
                                                        status_icon = {
                                                            'enhanced': '✅',
                                                            'no_evidence': '⚠️'
                                                        }.get(status, '❓')
                                                        
                                                        print(f"    {status_icon} {claim_id}: {status}, 证据数: {evidence_count}")
                                                        
                                                        # 统计各状态数量
                                                        total_claims += 1
                                                        if status == 'enhanced':
                                                            enhanced_claims += 1
                                                        elif status == 'no_evidence':
                                                            no_evidence_claims += 1
                                
                                print(f"\n📊 论断统计: 总计 {total_claims}, 已增强 {enhanced_claims}, 无证据 {no_evidence_claims}")
                                
                                # 不再保存额外文件，router已经生成了文件
                                
                                return unified_claims
                            else:
                                print(f"❌ 获取论断分析结果失败: {result_response.status_code}")
                                # 降级到原始结果（不保存额外文件）
                                return status_data
                        
                        elif current_status == "failed":
                            error_msg = status_data.get("error", "任务失败")
                            print(f"❌ 任务失败: {error_msg}")
                            return {"error": error_msg}
                    
                except requests.exceptions.RequestException as e:
                    print(f"⚠️ 状态查询失败: {e}")
            
            error_msg = f"任务超时，已等待 {max_attempts * 5} 秒 ({max_attempts * 5 // 60} 分钟)，请检查服务器状态或增加超时时间"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
            
        except requests.exceptions.Timeout as e:
            error_msg = f"请求超时: {e}。服务器可能需要更长时间处理，请稍后重试或联系管理员"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {e}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
    
    def check_server_status(self) -> bool:
        """检查服务器状态"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)  # 健康检查10秒足够
            return response.status_code == 200
        except:
            return False

def main():
    """主函数"""
    print("🧪 统一AI服务路由系统测试工具")
    print("="*60)
    
    tester = RouterTester()
    
    # 检查服务器状态
    if not tester.check_server_status():
        print("❌ 服务器未运行或无法连接")
        print("请先启动服务器: python start_server.py 或 uvicorn main:app --host 0.0.0.0 --port 8000")
        return
    
    print("✅ 服务器连接正常")
    
    # 加载测试文档
    try:
        content = tester.load_test_document("testmarkdown.md")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return
    
    # 显示菜单
    while True:
        print("\n" + "="*60)
        print("📋 请选择要测试的服务:")
        print("1️⃣  Final Review Agent (文档优化服务)")
        print("2️⃣  Thesis Agent (论点一致性检查服务)")
        print("3️⃣  Web Agent (论据支持度评估服务)")
        print("4️⃣  测试所有服务")
        print("0️⃣  退出")
        print("="*60)
        
        choice = input("请输入选择 (0-4): ").strip()
        
        if choice == "0":
            print("👋 再见!")
            break
        elif choice == "1":
            result = tester.test_final_review_agent(content)
            if "error" not in result:
                print("🎉 Final Review Agent 测试完成!")
        elif choice == "2":
            result = tester.test_thesis_agent(content)
            if "error" not in result:
                print("🎉 Thesis Agent 测试完成!")
        elif choice == "3":
            result = tester.test_web_agent(content)
            if "error" not in result:
                print("🎉 Web Agent 测试完成!")
        elif choice == "4":
            print("🚀 开始测试所有服务...")
            
            # 测试所有服务
            services = [
                ("Final Review Agent", tester.test_final_review_agent),
                ("Thesis Agent", tester.test_thesis_agent),
                ("Web Agent", tester.test_web_agent)
            ]
            
            results = {}
            for service_name, test_func in services:
                print(f"\n🔄 正在测试 {service_name}...")
                result = test_func(content)
                results[service_name] = result
                
                if "error" not in result:
                    print(f"✅ {service_name} 测试完成!")
                else:
                    print(f"❌ {service_name} 测试失败: {result['error']}")
            
            # 保存综合测试结果
            summary_file = tester.save_result("all_services_summary", results)
            print(f"\n🎉 所有服务测试完成! 综合结果已保存到: {summary_file}")
            
        else:
            print("❌ 无效选择，请重新输入")
    
    print(f"\n📁 所有测试结果保存在: {tester.results_dir}")

if __name__ == "__main__":
    main()
