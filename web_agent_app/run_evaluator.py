#!/usr/bin/env python3
"""
文档论据支持度评估器运行脚本
使用新的三步骤流程：检测论断 → websearch → 按章节生成
"""

import sys
import os
from whole_document_pipeline import WholeDocumentPipeline

def main():
    """主函数"""
    
    # 默认配置
    default_document = "final_markdown_merged_document_20250904_162736.md"
    default_max_claims = 15
    use_section_processing = True  # 默认使用新的章节并行处理
    
    # 解析命令行参数
    if len(sys.argv) == 1:
        # 无参数，使用默认配置
        document_path = default_document
        max_claims = default_max_claims
        print("📋 使用默认配置:")
        print(f"   - 文档: {document_path}")
        print(f"   - 最大论断数: {max_claims}")
        print(f"   - 处理模式: {'章节并行处理' if use_section_processing else '整体文档处理'}")
    elif len(sys.argv) == 2:
        # 只提供文档路径
        document_path = sys.argv[1]
        max_claims = default_max_claims
    elif len(sys.argv) == 3:
        # 提供文档路径和max_claims
        document_path = sys.argv[1]
        max_claims = int(sys.argv[2])
    else:
        # 提供文档路径、max_claims和处理模式
        document_path = sys.argv[1]
        max_claims = int(sys.argv[2])
        use_section_processing = sys.argv[3].lower() in ['true', '1', 'section', 'parallel']
    
    print("\n💡 使用方法:")
    print("   python run_evaluator.py                                           # 使用默认文档和参数")
    print("   python run_evaluator.py <document_path>                           # 指定文档，使用默认论断数")
    print("   python run_evaluator.py <document_path> <max_claims>              # 自定义论断数")
    print("   python run_evaluator.py <document_path> <max_claims> <mode>       # 完全自定义 (mode: true/false)")
    
    # 检查文档是否存在
    if not os.path.exists(document_path):
        print(f"❌ 文档不存在: {document_path}")
        sys.exit(1)
    
    print("\n🚀 启动新的三步骤文档论据支持度评估器")
    print(f"📄 目标文档: {document_path}")
    print(f"📊 最大论断数量: {max_claims}")
    print(f"🔄 处理模式: {'章节并行处理 (推荐)' if use_section_processing else '整体文档处理'}")
    print("-" * 60)
    
    try:
        # 初始化流水线
        pipeline = WholeDocumentPipeline()
        
        # 运行新的三步骤评估流程
        print("🔍 步骤1: 检测缺乏证据支撑的论断...")
        print("🌐 步骤2: WebSearch搜索相关证据...")
        print("📝 步骤3: 按章节并行生成修改文档...")
        print()
        
        result = pipeline.process_whole_document(
            document_path=document_path,
            max_claims=max_claims,
            max_search_results=10,
            use_section_based_processing=use_section_processing
        )
        
        # 输出结果摘要
        if result['status'] == 'success':
            print("\n🎉 新的三步骤评估完成！")
            print(f"📊 处理统计:")
            stats = result.get('statistics', {})
            
            if use_section_processing:
                # 章节并行处理模式的统计
                print(f"   - 处理章节: {stats.get('total_sections', 0)} 个")
                print(f"   - 成功章节: {stats.get('successful_sections', 0)} 个")
                print(f"   - 检测论断: {stats.get('total_claims_detected', 0)} 个")
                print(f"   - 搜索证据: {stats.get('total_evidence_sources', 0)} 条")
                print(f"   - 处理模式: 章节并行处理 (max_workers=5)")
            else:
                # 整体文档处理模式的统计
                print(f"   - 检测论断: {stats.get('total_claims_detected', 0)} 个")
                print(f"   - 搜索证据: {stats.get('total_evidence_sources', 0)} 条")
                print(f"   - 处理模式: 整体文档处理")
            
            print(f"   - 处理时间: {result.get('processing_time', 0):.1f} 秒")
            
            print(f"\n📁 输出文件:")
            files = result.get('output_files', {})
            for file_type, file_path in files.items():
                print(f"   - {file_type}: {file_path}")
            
            if use_section_processing:
                print(f"\n✨ 新功能亮点:")
                print(f"   - 🔍 AI精确检测缺乏证据的论断")
                print(f"   - 🌐 并行WebSearch搜索证据")
                print(f"   - 📝 按章节并行生成修改 (5个工作线程)")
                print(f"   - 📋 JSON合并器追踪所有修改")
                print(f"   - 🎯 直接告诉AI在哪里修改什么")
            
        else:
            print(f"\n❌ 评估失败: {result.get('error', '未知错误')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 运行时错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

