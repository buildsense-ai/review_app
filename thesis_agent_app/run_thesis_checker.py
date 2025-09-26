"""
论点一致性检查主运行脚本

提供完整的论点一致性检查流程：
1. 提取核心论点
2. 检查各章节与核心论点的一致性
3. 修正不一致的章节
4. 生成修正后的文档
"""

import json
import logging
import sys
import os
from typing import Optional, List
from datetime import datetime

# 导入相关模块
from thesis_extractor import ThesisExtractor, ThesisStatement
from thesis_consistency_checker import ThesisConsistencyChecker, ConsistencyAnalysis
from document_regenerator import ThesisDocumentRegenerator
from config import config


def setup_logging():
    """设置日志配置"""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.log_file, encoding=config.output_encoding)
        ]
    )


class ThesisConsistencyPipeline:
    """论点一致性检查流水线 - 简化为3步流程"""
    
    def __init__(self):
        """初始化流水线"""
        self.extractor = ThesisExtractor()
        self.checker = ThesisConsistencyChecker()
        self.regenerator = ThesisDocumentRegenerator()
        self.logger = logging.getLogger(__name__)
    
    def run_full_pipeline(self, document_file: str, document_title: Optional[str] = None, 
                         output_dir: str = "./thesis_outputs", 
                         auto_correct: bool = True) -> dict:
        """
        运行简化的论点一致性检查流水线（3步流程）
        
        Args:
            document_file: 文档文件路径
            document_title: 文档标题（可选）
            output_dir: 输出目录
            auto_correct: 是否自动修正问题（默认True）
            
        Returns:
            dict: 流水线执行结果
        """
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 如果没有提供标题，使用文件名
            if document_title is None:
                document_title = os.path.basename(document_file)
            
            self.logger.info(f"🚀 开始论点一致性检查流水线: {document_title}")
            
            # 第一步：加载文档内容
            document_content = self._load_document_content(document_file)
            if not document_content:
                return {'error': '无法加载文档内容'}
            
            # 第二步：提取核心论点
            self.logger.info("📋 第一步：提取核心论点")
            thesis_statement = self.extractor.extract_thesis_from_document(document_content, document_title)
            
            if not thesis_statement.main_thesis:
                return {'error': '无法提取有效的核心论点'}
            
            # 不保存论点提取结果和报告（简化输出）
            
            self.logger.info(f"✅ 核心论点提取完成: {thesis_statement.main_thesis[:100]}...")
            
            # 第三步：检查论点一致性
            self.logger.info("🔍 第二步：检查论点一致性")
            consistency_analysis = self.checker.check_consistency(document_content, thesis_statement, document_title)
            
            # 保存一致性分析结果（使用内置时间戳生成）
            consistency_file = self.checker.save_consistency_analysis(
                consistency_analysis, thesis_statement, document_title,
                output_dir  # 只传递目录，让方法自己生成带时间戳的文件名
            )
            
            # 不生成一致性报告（简化输出）
            
            self.logger.info(f"✅ 一致性检查完成，发现 {consistency_analysis.total_issues_found} 个问题")
            
            # 第三步：修正问题章节并生成完整文档（如果需要且启用自动修正）
            complete_document_results = None
            
            if consistency_analysis.total_issues_found > 0 and auto_correct:
                self.logger.info("🔧 第三步：修正问题章节并生成完整文档")
                
                complete_document_results = self.regenerator.regenerate_complete_document(
                    analysis_file=consistency_file,
                    document_file=document_file,
                    output_dir=output_dir
                )
                
                if 'error' not in complete_document_results and 'message' not in complete_document_results:
                    self.logger.info(f"✅ 完整文档生成完成，修正了 {complete_document_results.get('sections_count', 0)} 个章节")
                else:
                    self.logger.warning(f"⚠️ 完整文档生成结果: {complete_document_results}")
            elif consistency_analysis.total_issues_found == 0:
                self.logger.info("✅ 文档论点一致性良好，无需修正")
            else:
                self.logger.info("ℹ️ 发现问题但未启用自动修正，请手动处理")
            
            # 不生成流水线摘要报告（简化输出）
            
            # 返回结果
            result = {
                'status': 'success',
                'document_title': document_title,
                'thesis_statement': thesis_statement,
                'consistency_analysis': consistency_analysis,
                'complete_document_results': complete_document_results,
                'output_files': {
                    'consistency_analysis': consistency_file
                }
            }
            
            # 添加完整文档输出文件信息
            if complete_document_results and 'saved_files' in complete_document_results:
                result['output_files'].update(complete_document_results['saved_files'])
            
            self.logger.info("🎉 论点一致性检查流水线执行完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 流水线执行失败: {e}")
            return {'error': f'流水线执行失败: {str(e)}'}
    
    def _load_document_content(self, document_file: str) -> str:
        """
        加载文档内容
        
        Args:
            document_file: 文档文件路径
            
        Returns:
            str: 文档内容
        """
        try:
            if document_file.endswith('.json'):
                # 处理JSON文档，提取generated_content
                with open(document_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                content_parts = []
                report_guide = json_data.get('report_guide', [])
                
                for part in report_guide:
                    sections = part.get('sections', [])
                    
                    for section in sections:
                        subtitle = section.get('subtitle', '')
                        generated_content = section.get('generated_content', '')
                        if subtitle and generated_content:
                            content_parts.append(f"## {subtitle}\n\n{generated_content}")
                
                content = "\n\n".join(content_parts)
                self.logger.info(f"成功加载JSON文档，提取了{len(content_parts)}个章节")
                return content
            else:
                # 处理Markdown文档
                with open(document_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.logger.info(f"成功加载Markdown文档")
                return content
        except Exception as e:
            self.logger.error(f"加载文档失败: {e}")
            return ""
    
    def _generate_pipeline_summary(self, document_title: str, thesis_statement: ThesisStatement, 
                                 consistency_analysis: ConsistencyAnalysis, 
                                 correction_results: Optional[dict]) -> str:
        """
        生成流水线摘要报告
        
        Args:
            document_title: 文档标题
            thesis_statement: 核心论点结构
            consistency_analysis: 一致性分析结果
            correction_results: 修正结果（可选）
            
        Returns:
            str: 摘要报告内容
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report_lines = [
            f"# 论点一致性检查流水线摘要报告",
            f"",
            f"**文档标题**: {document_title}",
            f"**执行时间**: {timestamp}",
            f"",
            f"## 🎯 核心论点提取结果",
            f"**主要论点**: {thesis_statement.main_thesis}",
            f"",
            f"**支撑论据**:",
        ]
        
        for i, arg in enumerate(thesis_statement.supporting_arguments, 1):
            report_lines.append(f"{i}. {arg}")
        
        report_lines.extend([
            f"",
            f"**关键概念**: {', '.join(thesis_statement.key_concepts)}",
            f"",
            f"## 🔍 一致性检查结果",
            f"**整体一致性评分**: {consistency_analysis.overall_consistency_score:.2f}/1.00",
            f"**发现问题总数**: {consistency_analysis.total_issues_found}",
            f""
        ])
        
        if consistency_analysis.total_issues_found == 0:
            report_lines.append("✅ **优秀**: 所有章节都与核心论点保持良好一致性")
        else:
            report_lines.append("⚠️ **发现问题**: 以下章节存在一致性问题")
            for issue in consistency_analysis.consistency_issues:
                report_lines.append(f"- {issue.section_title} ({issue.issue_type})")
        
        report_lines.append("")
        
        # 修正结果
        if correction_results:
            if 'error' in correction_results:
                report_lines.extend([
                    f"## ❌ 章节修正结果",
                    f"修正过程中发生错误: {correction_results['error']}",
                    f""
                ])
            elif 'message' in correction_results:
                report_lines.extend([
                    f"## ℹ️ 章节修正结果",
                    f"{correction_results['message']}",
                    f""
                ])
            else:
                report_lines.extend([
                    f"## 🔧 章节修正结果",
                    f"**修正章节数**: {len(correction_results)}",
                    f"**修正章节列表**:",
                ])
                
                for section_title, result in correction_results.items():
                    original_issue = result.get('original_issue', {})
                    report_lines.append(f"- {section_title} (原问题: {original_issue.get('issue_type', '')})")
                
                report_lines.append("")
        else:
            if consistency_analysis.total_issues_found > 0:
                report_lines.extend([
                    f"## ℹ️ 章节修正结果",
                    f"未执行自动修正，请手动处理发现的一致性问题",
                    f""
                ])
        
        # 建议
        report_lines.extend([
            f"## 💡 改进建议",
        ])
        
        for suggestion in consistency_analysis.improvement_suggestions:
            report_lines.append(f"- {suggestion}")
        
        report_lines.extend([
            f"",
            f"## 📁 输出文件",
            f"- 核心论点提取结果: `thesis_statement_{document_title}.json`",
            f"- 核心论点报告: `thesis_report_{document_title}.md`",
            f"- 一致性分析结果: `consistency_analysis_{document_title}.json`",
            f"- 一致性检查报告: `consistency_report_{document_title}.md`",
        ])
        
        if correction_results and 'error' not in correction_results and 'message' not in correction_results:
            report_lines.extend([
                f"- 修正后章节内容: `corrected_sections_*.json`",
                f"- 修正后章节报告: `corrected_sections_*.md`",
            ])
        
        report_lines.extend([
            f"",
            f"---",
            f"*本报告由Gauz论点一致性Agent自动生成*"
        ])
        
        return "\n".join(report_lines)


def analyze_document_from_file(file_path: str, document_title: Optional[str] = None, 
                             output_dir: str = "./thesis_outputs",
                             auto_correct: bool = True):
    """
    从文件读取文档内容并进行完整的论点一致性检查
    
    Args:
        file_path: 文档文件路径
        document_title: 文档标题（可选，默认使用文件名）
        output_dir: 输出目录
        auto_correct: 是否自动修正问题（默认True）
        
    Returns:
        分析结果
    """
    try:
        # 如果没有提供标题，使用文件名
        if document_title is None:
            document_title = os.path.basename(file_path)
        
        # 创建流水线并执行
        pipeline = ThesisConsistencyPipeline()
        result = pipeline.run_full_pipeline(
            document_file=file_path,
            document_title=document_title,
            output_dir=output_dir,
            auto_correct=auto_correct
        )
        
        return result
        
    except FileNotFoundError:
        print(f"❌ 文件未找到: {file_path}")
        return None
    except Exception as e:
        print(f"❌ 分析过程中发生错误: {e}")
        return None


def main():
    """主函数 - 命令行接口"""
    setup_logging()
    
    # 默认配置
    default_file_path = "final_markdown_merged_document_20250828_160506.md"
    default_output_dir = "./test_results"
    
    # 如果没有提供参数，使用默认配置
    if len(sys.argv) < 2:
        print("🚀 使用默认配置运行论点一致性检查")
        print(f"📄 默认文档: {default_file_path}")
        print(f"📁 默认输出目录: {default_output_dir}")
        print("")
        print("如需自定义配置，使用方法:")
        print("  python run_thesis_checker.py <文档文件路径> [选项]")
        print("")
        print("选项:")
        print("  --title <标题>          指定文档标题")
        print("  --output <目录>         指定输出目录")
        print("  --no-auto-correct      不自动修正问题，只进行检查")
        print("")
        
        # 使用默认配置
        file_path = default_file_path
        document_title = "用户手册文档"
        output_dir = default_output_dir
        auto_correct = True
    else:
        # 解析命令行参数
        file_path = sys.argv[1]
        document_title = None
        output_dir = default_output_dir  # 默认使用 test_results
        auto_correct = True
    
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--title' and i + 1 < len(sys.argv):
                document_title = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--output' and i + 1 < len(sys.argv):
                output_dir = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--no-auto-correct':
                auto_correct = False
                i += 1
            else:
                print(f"未知选项: {sys.argv[i]}")
                return
    
    print(f"🔍 开始论点一致性检查: {file_path}")
    if document_title:
        print(f"📋 文档标题: {document_title}")
    print(f"📁 输出目录: {output_dir}")
    if not auto_correct:
        print("ℹ️ 仅检查模式，不自动修正")
    
    # 执行分析
    result = analyze_document_from_file(
        file_path=file_path,
        document_title=document_title,
        output_dir=output_dir,
        auto_correct=auto_correct
    )
    
    if result is None:
        print("❌ 论点一致性检查失败")
        return
    
    if 'error' in result:
        print(f"❌ 错误: {result['error']}")
        return
    
    # 显示结果摘要
    print(f"\n📊 论点一致性检查完成:")
    print(f"   核心论点: {result['thesis_statement'].main_thesis[:100]}...")
    print(f"   一致性评分: {result['consistency_analysis'].overall_consistency_score:.2f}")
    print(f"   发现问题: {result['consistency_analysis'].total_issues_found} 个")
    
    if result.get('complete_document_results'):
        complete_results = result['complete_document_results']
        if 'error' in complete_results:
            print(f"   完整文档生成: 失败 - {complete_results['error']}")
        elif 'message' in complete_results:
            print(f"   完整文档生成: {complete_results['message']}")
        else:
            print(f"   完整文档生成: 成功，修正了 {complete_results.get('sections_count', 0)} 个章节")
            if 'saved_files' in complete_results:
                print(f"   完整修正后文档: {complete_results['saved_files'].get('complete_document', '未生成')}")
    
    print(f"\n📁 输出文件已保存到: {output_dir}")
    print(f"   一致性分析: {result['output_files']['consistency_analysis']}")
    if result.get('complete_document_results') and 'saved_files' in result['complete_document_results']:
        complete_doc = result['complete_document_results']['saved_files'].get('complete_document')
        if complete_doc:
            print(f"   修正后文档: {complete_doc}")


if __name__ == "__main__":
    main()
