#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档内容更新工具 - 适配论据支持度评估系统
提供多种文档处理和更新方式
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from whole_document_pipeline import WholeDocumentPipeline

def update_document_with_evidence_analysis(document_path: str, 
                                         output_dir: str = "enhanced_results",
                                         processing_mode: str = "parallel") -> Dict[str, str]:
    """
    使用证据分析更新文档内容
    
    Args:
        document_path: 输入文档路径
        output_dir: 输出目录
        processing_mode: 处理模式 ("parallel" 或 "sequential")
        
    Returns:
        Dict[str, str]: 输出文件路径
    """
    print("=== 文档证据分析更新工具 ===")
    print(f"输入文档: {document_path}")
    print(f"输出目录: {output_dir}")
    print(f"处理模式: {processing_mode}")
    print()
    
    # 使用新的流水线处理
    pipeline = WholeDocumentPipeline()
    
    if processing_mode == "parallel":
        # 使用章节并行处理
        result = pipeline.process_whole_document(
            document_path=document_path,
            use_section_based_processing=True
        )
    else:
        # 使用整体文档处理
        result = pipeline.process_whole_document(
            document_path=document_path,
            use_section_based_processing=False
        )
    
    if result.get('status') == 'success':
        return result.get('output_files', {})
    else:
        print(f"❌ 处理失败: {result.get('error', '未知错误')}")
        return {}

def process_document_sequential(document_path: str, output_dir: str) -> Dict[str, str]:
    """
    顺序处理整个文档（原有方式）
    
    Args:
        document_path: 输入文档路径
        output_dir: 输出目录
        
    Returns:
        Dict[str, str]: 输出文件路径
    """
    print("🔄 使用顺序处理模式（整体文档）...")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        from whole_document_pipeline import WholeDocumentPipeline
        
        # 创建流水线
        pipeline = WholeDocumentPipeline()
        
        # 处理文档
        result = pipeline.process_whole_document(
            document_path=document_path,
            max_claims=20,  # 整体文档可以处理更多论断
            max_search_results=10
        )
        
        if result.get('status') == 'success':
            output_files = result.get('output_files', {})
            
            # 复制文件到指定输出目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(document_path))[0]
            
            result_paths = {}
            
            if 'enhanced_document' in output_files:
                src_path = output_files['enhanced_document']
                dst_path = os.path.join(output_dir, f"enhanced_{base_name}_{timestamp}.md")
                if os.path.exists(src_path):
                    import shutil
                    shutil.copy2(src_path, dst_path)
                    result_paths['enhanced_document'] = dst_path
            
            if 'evidence_analysis' in output_files:
                src_path = output_files['evidence_analysis']
                dst_path = os.path.join(output_dir, f"evidence_analysis_{base_name}_{timestamp}.json")
                if os.path.exists(src_path):
                    import shutil
                    shutil.copy2(src_path, dst_path)
                    result_paths['evidence_analysis'] = dst_path
            
            print(f"✅ 顺序处理完成")
            return result_paths
        else:
            print(f"❌ 处理失败: {result.get('error', '未知错误')}")
            return {}
    
    except Exception as e:
        print(f"❌ 顺序处理时出错: {str(e)}")
        return {}

def compare_processing_modes(document_path: str, output_dir: str = "comparison_results") -> Dict[str, Any]:
    """
    比较不同处理模式的效果
    
    Args:
        document_path: 输入文档路径
        output_dir: 输出目录
        
    Returns:
        Dict[str, Any]: 比较结果
    """
    print("=== 处理模式比较工具 ===")
    print(f"输入文档: {document_path}")
    print(f"输出目录: {output_dir}")
    print()
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    comparison_results = {
        'document_path': document_path,
        'comparison_timestamp': datetime.now().isoformat(),
        'modes': {}
    }
    
    # 并行模式
    print("🚀 测试并行章节处理模式...")
    parallel_start = time.time()
    try:
        pipeline = WholeDocumentPipeline()
        parallel_result = pipeline.process_whole_document(
            document_path=document_path,
            use_section_based_processing=True
        )
        parallel_time = time.time() - parallel_start
        parallel_results = parallel_result.get('output_files', {})
        
        comparison_results['modes']['parallel'] = {
            'status': 'success',
            'processing_time': parallel_time,
            'output_files': parallel_results,
            'advantages': [
                "避免token长度限制",
                "并行处理速度快",
                "每章节独立分析"
            ]
        }
        print(f"✅ 并行模式完成，耗时: {parallel_time:.2f}秒")
    except Exception as e:
        comparison_results['modes']['parallel'] = {
            'status': 'failed',
            'error': str(e)
        }
        print(f"❌ 并行模式失败: {str(e)}")
    
    # 顺序模式
    print("\n📝 测试顺序整体处理模式...")
    sequential_start = time.time()
    try:
        sequential_results = process_document_sequential(
            document_path,
            os.path.join(output_dir, "sequential_mode")
        )
        sequential_time = time.time() - sequential_start
        
        comparison_results['modes']['sequential'] = {
            'status': 'success',
            'processing_time': sequential_time,
            'output_files': sequential_results,
            'advantages': [
                "保持文档整体连贯性",
                "全局上下文理解",
                "统一的处理标准"
            ]
        }
        print(f"✅ 顺序模式完成，耗时: {sequential_time:.2f}秒")
    except Exception as e:
        comparison_results['modes']['sequential'] = {
            'status': 'failed',
            'error': str(e)
        }
        print(f"❌ 顺序模式失败: {str(e)}")
    
    # 生成比较报告
    report_path = os.path.join(output_dir, f"comparison_report_{int(time.time())}.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(comparison_results, f, ensure_ascii=False, indent=2)
    
    # 生成可读报告
    readable_report_path = os.path.join(output_dir, f"comparison_report_{int(time.time())}.md")
    generate_readable_comparison_report(comparison_results, readable_report_path)
    
    print(f"\n📊 比较完成！")
    print(f"✅ 详细报告: {report_path}")
    print(f"✅ 可读报告: {readable_report_path}")
    
    return comparison_results

def generate_readable_comparison_report(comparison_data: Dict[str, Any], output_path: str):
    """生成可读的比较报告"""
    
    report_content = f"""# 文档处理模式比较报告

**文档**: {comparison_data['document_path']}
**比较时间**: {comparison_data['comparison_timestamp']}

## 处理模式对比

"""
    
    modes = comparison_data.get('modes', {})
    
    if 'parallel' in modes:
        parallel = modes['parallel']
        status_icon = "✅" if parallel['status'] == 'success' else "❌"
        report_content += f"""### {status_icon} 并行章节处理模式

**状态**: {parallel['status']}
"""
        if parallel['status'] == 'success':
            report_content += f"""**处理时间**: {parallel['processing_time']:.2f}秒
**输出文件**: {len(parallel.get('output_files', {}))} 个

**优势**:
"""
            for advantage in parallel.get('advantages', []):
                report_content += f"- {advantage}\n"
        else:
            report_content += f"**错误**: {parallel.get('error', '未知错误')}\n"
        
        report_content += "\n"
    
    if 'sequential' in modes:
        sequential = modes['sequential']
        status_icon = "✅" if sequential['status'] == 'success' else "❌"
        report_content += f"""### {status_icon} 顺序整体处理模式

**状态**: {sequential['status']}
"""
        if sequential['status'] == 'success':
            report_content += f"""**处理时间**: {sequential['processing_time']:.2f}秒
**输出文件**: {len(sequential.get('output_files', {}))} 个

**优势**:
"""
            for advantage in sequential.get('advantages', []):
                report_content += f"- {advantage}\n"
        else:
            report_content += f"**错误**: {sequential.get('error', '未知错误')}\n"
        
        report_content += "\n"
    
    # 性能比较
    if 'parallel' in modes and 'sequential' in modes:
        parallel_time = modes['parallel'].get('processing_time', 0)
        sequential_time = modes['sequential'].get('processing_time', 0)
        
        if parallel_time > 0 and sequential_time > 0:
            speedup = sequential_time / parallel_time
            report_content += f"""## 性能分析

- **并行模式耗时**: {parallel_time:.2f}秒
- **顺序模式耗时**: {sequential_time:.2f}秒
- **速度提升**: {speedup:.2f}x

"""
    
    report_content += """## 推荐使用场景

### 并行章节处理模式
- 适用于长文档（>10000字符）
- 需要快速处理的场景
- 章节相对独立的文档
- 对处理速度有要求的情况

### 顺序整体处理模式
- 适用于短文档（<5000字符）
- 需要保持全局连贯性的文档
- 章节间关联性强的内容
- 对处理质量要求极高的情况

## 总结

两种模式各有优势，建议根据具体需求选择：
- 长文档或时间敏感 → 选择并行模式
- 短文档或质量优先 → 选择顺序模式
"""
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"✅ 可读报告已生成: {output_path}")
    except Exception as e:
        print(f"❌ 生成可读报告失败: {str(e)}")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python update_json_content.py <文档路径> [模式] [输出目录]")
        print()
        print("模式选项:")
        print("  parallel   - 并行章节处理（默认）")
        print("  sequential - 顺序整体处理")
        print("  compare    - 比较两种模式")
        print()
        print("示例:")
        print("  python update_json_content.py document.md parallel enhanced_results")
        print("  python update_json_content.py document.md compare comparison_results")
        return 1
    
    document_path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "parallel"
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "enhanced_results"
    
    if not os.path.exists(document_path):
        print(f"❌ 文档文件不存在: {document_path}")
        return 1
    
    try:
        if mode == "compare":
            # 比较模式
            comparison_results = compare_processing_modes(document_path, output_dir)
            if comparison_results:
                print("🎉 比较完成！")
                return 0
            else:
                print("❌ 比较失败！")
                return 1
        else:
            # 单一模式处理
            result_paths = update_document_with_evidence_analysis(
                document_path, output_dir, mode
            )
            
            if result_paths:
                print("🎉 文档更新成功完成！")
                for file_type, path in result_paths.items():
                    print(f"  {file_type}: {path}")
                return 0
            else:
                print("❌ 文档更新失败！")
                return 1
    
    except Exception as e:
        print(f"❌ 执行过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())