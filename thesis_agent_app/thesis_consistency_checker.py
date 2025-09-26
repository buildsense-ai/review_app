"""
论点一致性检查器 - 检查文档各章节与核心论点的一致性

负责逐一检查每个章节、每个段落的分论点是否服务于、或至少不违背核心论点。
"""

import json
import logging
import re
import time
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
from dataclasses import dataclass, field
from thesis_extractor import ThesisStatement, ColoredLogger
from config import config


@dataclass
class ConsistencyIssue:
    """一致性问题数据结构"""
    section_title: str = ""
    issue_type: str = ""  # "contradiction", "irrelevant", "weak_support", "unclear"
    description: str = ""
    evidence: str = ""
    suggestion: str = ""


@dataclass
class ConsistencyAnalysis:
    """一致性分析结果数据结构"""
    overall_consistency_score: float = 0.0
    total_issues_found: int = 0
    consistency_issues: List[ConsistencyIssue] = field(default_factory=list)
    well_aligned_sections: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)


class ThesisConsistencyChecker:
    """论点一致性检查器"""
    
    def __init__(self, api_key: str = None):
        """
        初始化一致性检查器
        
        Args:
            api_key: OpenRouter API密钥（可选，默认从配置文件读取）
        """
        self.api_key = api_key or config.openrouter_api_key
        self.colored_logger = ColoredLogger(__name__)
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            base_url=config.openrouter_base_url,
            api_key=self.api_key,
        )
        
        # 一致性检查提示词模板
        self.consistency_check_prompt = """
# 角色
你是一名专业的学术论文逻辑分析师和"逻辑警察"，擅长识别论文中的逻辑一致性问题，确保全文围绕核心论点展开，无自相矛盾之处。

# 任务
你的核心任务是基于已提取的核心论点，逐一检查文档中每个章节的内容是否与核心论点保持一致，识别所有可能的逻辑冲突、偏离主题或论证薄弱的地方。

# 核心论点信息
**主要论点**: $main_thesis
**支撑论据**: $supporting_arguments
**关键概念**: $key_concepts

# 评估范围限制（重要）
只评估"正文"段落，严格忽略以下所有非正文内容：
1) 任何"### 相关图片资料"标题及其后的图片描述/图片来源/图片Markdown（直到下一个二级标题`## `或文末）。
2) 任意 Markdown 图片语法行：包含 `![` 或 `](http` 的行。
3) 含有"图片描述:"或"图片来源:"开头的行。
4) 任何"### 相关表格资料"标题及其后的表格内容，或任意以 `|` 开头的 Markdown 表格行。
5) 代码块、引用块、脚注等非正文元素。

# 一致性检查标准
请检查每个章节是否存在以下问题：

1. **直接矛盾 (contradiction)**: 章节内容与核心论点或支撑论据直接冲突
2. **偏离主题 (irrelevant)**: 章节内容与核心论点无关或关联度很低
3. **论证薄弱 (weak_support)**: 章节内容试图支持核心论点但论证不充分或逻辑不清
4. **表述不清 (unclear)**: 章节内容模糊不清，无法判断其与核心论点的关系
5. **可优化 (optimization)**: 章节内容基本合理，但可以通过加强论证、优化表述、增强与核心论点的关联等方式进一步改进

# 输出要求（仅JSON）
你的最终输出必须是一个结构化的 JSON 数组，**必须包含对每个章节的分析**：

[
  {
    "section_title": "章节标题",
    "issue_type": "问题类型 (contradiction/irrelevant/weak_support/unclear/optimization)",
    "description": "问题的详细描述或优化点分析",
    "evidence": "支持该判断的具体证据（引用章节中的关键句子）",
    "suggestion": "具体的修改建议或优化方案"
  }
]

# 工作流程
1) 仔细阅读核心论点及其相关要素
2) 逐个分析每个章节的正文内容
3) 判断每个章节与核心论点的关系
4) 识别不一致、矛盾、偏离或可优化的地方
5) **对每个章节都必须提供具体的改进建议**
6) 严格按照JSON数组格式返回结果，不要包含任何其他文字说明

**严格要求：绝对不允许返回空数组。每个章节都必须有对应的分析结果和改进建议。**

待检查文档：
$document_content

请严格遵循以上要求，只返回JSON格式结果。必须对每个章节都提供分析和建议。"""

        self.colored_logger.info("✅ ThesisConsistencyChecker 初始化完成")
    
    def check_consistency(self, document_content: str, thesis_statement: ThesisStatement, 
                         document_title: str = "未命名文档") -> ConsistencyAnalysis:
        """
        检查文档与核心论点的一致性
        
        Args:
            document_content: 待检查的文档内容
            thesis_statement: 核心论点结构
            document_title: 文档标题
            
        Returns:
            ConsistencyAnalysis: 一致性分析结果
        """
        self.colored_logger.info(f"\n🔍 开始论点一致性检查: {document_title}")
        
        try:
            # 检查文档内容长度
            if len(document_content.strip()) < 200:
                self.colored_logger.warning("⚠️ 文档内容过短，可能无法进行有效的一致性检查")
                return ConsistencyAnalysis(
                    overall_consistency_score=1.0,
                    total_issues_found=0,
                    consistency_issues=[],
                    well_aligned_sections=[],
                    improvement_suggestions=["文档内容过短，建议增加更多详细信息"]
                )
            
            # 调用OpenRouter API进行一致性检查
            check_result = self._call_openrouter_api(document_content, thesis_statement)
            
            # 解析API响应
            consistency_analysis = self._parse_api_response(check_result, document_content)
            
            # 计算整体一致性评分
            consistency_score = self._calculate_consistency_score(consistency_analysis)
            consistency_analysis.overall_consistency_score = consistency_score
            
            # 生成改进建议
            improvement_suggestions = self._generate_improvement_suggestions(consistency_analysis)
            consistency_analysis.improvement_suggestions = improvement_suggestions
            
            # 记录检查结果
            self.colored_logger.info(f"🎯 一致性检查完成，发现 {consistency_analysis.total_issues_found} 个问题")
            self.colored_logger.info(f"📊 整体一致性评分: {consistency_score:.2f}")
            
            return consistency_analysis
            
        except Exception as e:
            self.colored_logger.error(f"❌ 一致性检查失败: {e}")
            return ConsistencyAnalysis(
                overall_consistency_score=0.0,
                total_issues_found=0,
                consistency_issues=[],
                well_aligned_sections=[],
                improvement_suggestions=[f"检查过程中发生错误: {str(e)}"]
            )
    
    def _call_openrouter_api(self, document_content: str, thesis_statement: ThesisStatement) -> str:
        """
        调用OpenRouter API进行一致性检查
        
        Args:
            document_content: 文档内容
            thesis_statement: 核心论点结构
            
        Returns:
            str: API响应内容
        """
        try:
            # 构建提示词，替换论点信息
            prompt = self.consistency_check_prompt.replace('$document_content', document_content)
            prompt = prompt.replace('$main_thesis', thesis_statement.main_thesis)
            prompt = prompt.replace('$supporting_arguments', ', '.join(thesis_statement.supporting_arguments))
            prompt = prompt.replace('$key_concepts', ', '.join(thesis_statement.key_concepts))
            
            self.colored_logger.info(f"📄 文档内容长度: {len(document_content)}字符")
            self.colored_logger.info(f"🎯 核心论点: {thesis_statement.main_thesis[:100]}...")
            
            # 调用API
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": config.openrouter_http_referer,
                    "X-Title": config.openrouter_x_title,
                },
                extra_body={},
                model=config.openrouter_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=config.consistency_check_temperature,
                max_tokens=config.max_tokens
            )
            
            # 检查响应结构
            if not hasattr(completion, 'choices') or not completion.choices:
                raise ValueError("API响应格式错误")
            
            if not completion.choices[0].message or not completion.choices[0].message.content:
                raise ValueError("API响应内容为空")
            
            response_content = completion.choices[0].message.content
            
            self.colored_logger.info(f"📡 API调用成功，响应长度: {len(response_content)} 字符")
            self.colored_logger.info(f"📄 API响应内容: {response_content[:500]}...")  # 显示前500个字符
            
            return response_content
            
        except Exception as e:
            self.colored_logger.error(f"❌ OpenRouter API调用失败: {e}")
            raise
    
    def _parse_api_response(self, api_response: str, document_content: str) -> ConsistencyAnalysis:
        """
        解析API响应，提取一致性问题
        
        Args:
            api_response: API响应内容
            document_content: 原始文档内容（用于提取章节信息）
            
        Returns:
            ConsistencyAnalysis: 解析后的一致性分析结果
        """
        try:
            # 清理响应内容
            cleaned_response = api_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            cleaned_response = cleaned_response.strip()
            
            # 尝试提取JSON内容
            json_match = re.search(r'\[.*\]', cleaned_response, re.DOTALL)
            if not json_match:
                self.colored_logger.warning("⚠️ API响应中未找到有效的JSON数组，假设无一致性问题")
                return ConsistencyAnalysis(
                    overall_consistency_score=1.0,
                    total_issues_found=0,
                    consistency_issues=[],
                    well_aligned_sections=self._extract_section_titles(document_content),
                    improvement_suggestions=[]
                )
            
            json_str = json_match.group(0)
            
            # 尝试解析JSON
            try:
                parsed_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.colored_logger.error(f"❌ JSON解析失败: {e}")
                return ConsistencyAnalysis()
            
            # 构建ConsistencyAnalysis对象
            consistency_issues = []
            
            if isinstance(parsed_data, list):
                for item in parsed_data:
                    if isinstance(item, dict):
                        issue = ConsistencyIssue(
                            section_title=item.get('section_title', ''),
                            issue_type=item.get('issue_type', ''),
                            description=item.get('description', ''),
                            evidence=item.get('evidence', ''),
                            suggestion=item.get('suggestion', '')
                        )
                        consistency_issues.append(issue)
            
            # 提取所有章节标题，找出没有问题的章节
            all_sections = self._extract_section_titles(document_content)
            problematic_sections = {issue.section_title for issue in consistency_issues}
            well_aligned_sections = [section for section in all_sections if section not in problematic_sections]
            
            analysis = ConsistencyAnalysis(
                total_issues_found=len(consistency_issues),
                consistency_issues=consistency_issues,
                well_aligned_sections=well_aligned_sections
            )
            
            self.colored_logger.debug(f"✅ 成功解析API响应，发现 {len(consistency_issues)} 个一致性问题")
            
            return analysis
            
        except Exception as e:
            self.colored_logger.error(f"❌ 响应解析失败: {e}")
            return ConsistencyAnalysis()
    
    def _extract_section_titles(self, document_content: str) -> List[str]:
        """
        从文档中提取所有章节标题
        
        Args:
            document_content: 文档内容
            
        Returns:
            List[str]: 章节标题列表
        """
        try:
            titles = []
            
            # 匹配一级标题
            pattern_h1 = r'^#\s+(.+)$'
            h1_matches = re.findall(pattern_h1, document_content, re.MULTILINE)
            titles.extend([match.strip() for match in h1_matches])
            
            # 匹配二级标题
            pattern_h2 = r'^##\s+(.+)$'
            h2_matches = re.findall(pattern_h2, document_content, re.MULTILINE)
            titles.extend([match.strip() for match in h2_matches])
            
            # 匹配三级标题
            pattern_h3 = r'^###\s+(.+)$'
            h3_matches = re.findall(pattern_h3, document_content, re.MULTILINE)
            titles.extend([match.strip() for match in h3_matches])
            
            return titles
        except Exception as e:
            self.colored_logger.error(f"❌ 提取章节标题失败: {e}")
            return []
    
    def _calculate_consistency_score(self, analysis: ConsistencyAnalysis) -> float:
        """
        计算整体一致性评分
        
        Args:
            analysis: 一致性分析结果
            
        Returns:
            float: 一致性评分 (0.0-1.0)
        """
        if analysis.total_issues_found == 0:
            return 1.0  # 无问题，满分
        
        # 基于问题数量和严重程度计算评分
        base_score = 1.0
        
        # 简化的扣分逻辑：每个问题扣0.1分
        total_penalty = analysis.total_issues_found * 0.1
        
        # 应用惩罚，但不低于0.0
        final_score = max(0.0, base_score - total_penalty)
        
        self.colored_logger.debug(f"📊 一致性评分计算: 基础分1.0 - 总扣分{total_penalty:.2f} = {final_score:.2f}")
        
        return final_score
    
    def _generate_improvement_suggestions(self, analysis: ConsistencyAnalysis) -> List[str]:
        """
        生成改进建议
        
        Args:
            analysis: 一致性分析结果
            
        Returns:
            List[str]: 改进建议列表
        """
        suggestions = []
        
        if analysis.total_issues_found == 0:
            suggestions.append("✅ 文档论点一致性良好，所有章节都与核心论点保持一致")
            return suggestions
        
        # 添加总体建议
        suggestions.append(f"📝 发现 {analysis.total_issues_found} 个论点一致性问题，建议进行修正")
        
        # 添加具体问题类型建议
        issue_types = {}
        for issue in analysis.consistency_issues:
            issue_type = issue.issue_type
            if issue_type not in issue_types:
                issue_types[issue_type] = 0
            issue_types[issue_type] += 1
        
        for issue_type, count in issue_types.items():
            if issue_type == "contradiction":
                suggestions.append(f"🔄 发现 {count} 个直接矛盾问题，需要重新审视相关章节的论述")
            elif issue_type == "irrelevant":
                suggestions.append(f"🎯 发现 {count} 个偏离主题问题，建议调整章节内容使其更贴近核心论点")
            elif issue_type == "weak_support":
                suggestions.append(f"💪 发现 {count} 个论证薄弱问题，需要加强论据和逻辑链条")
            elif issue_type == "unclear":
                suggestions.append(f"🔍 发现 {count} 个表述不清问题，建议明确章节与核心论点的关系")
        
        # 添加通用建议
        suggestions.extend([
            "💡 建议重新审视每个章节是否服务于核心论点",
            "💡 确保所有论据都指向同一个结论",
            "💡 消除可能的逻辑矛盾和自相矛盾"
        ])
        
        return suggestions
    
    def generate_consistency_report(self, analysis: ConsistencyAnalysis, thesis_statement: ThesisStatement, 
                                  document_title: str = "未命名文档") -> str:
        """
        生成一致性检查报告
        
        Args:
            analysis: 一致性分析结果
            thesis_statement: 核心论点结构
            document_title: 文档标题
            
        Returns:
            str: 格式化的一致性报告
        """
        report_lines = [
            f"# 论点一致性检查报告",
            f"**文档标题**: {document_title}",
            f"**检查时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## 🎯 核心论点",
            f"**主要论点**: {thesis_statement.main_thesis}",
            f"",
            f"## 📊 一致性评估结果",
            f"**整体一致性评分**: {analysis.overall_consistency_score:.2f}/1.00",
            f"**发现问题总数**: {analysis.total_issues_found}",
            f""
        ]
        
        if analysis.total_issues_found == 0:
            report_lines.extend([
                f"✅ **优秀**: 所有章节都与核心论点保持良好一致性",
                f""
            ])
        else:
            report_lines.extend([
                f"⚠️ **发现问题**: 共 {analysis.total_issues_found} 个论点一致性问题需要处理",
                f""
            ])
            
            # 详细问题列表
            for i, issue in enumerate(analysis.consistency_issues, 1):
                report_lines.extend([
                    f"### {i}. {issue.section_title}",
                    f"**问题类型**: {issue.issue_type}",
                    f"**问题描述**: {issue.description}",
                    f"**支撑证据**: {issue.evidence}",
                    f"**修改建议**: {issue.suggestion}",
                    f""
                ])
        
        # 表现良好的章节
        if analysis.well_aligned_sections:
            report_lines.extend([
                f"## ✅ 论点一致性良好的章节",
            ])
            for section in analysis.well_aligned_sections:
                report_lines.append(f"- {section}")
            report_lines.append("")
        
        # 改进建议
        report_lines.extend([
            f"## 💡 改进建议",
        ])
        
        for suggestion in analysis.improvement_suggestions:
            report_lines.append(f"- {suggestion}")
        
        report_lines.extend([
            f"",
            f"---",
            f"*本报告由Gauz论点一致性Agent自动生成*"
        ])
        
        return "\n".join(report_lines)
    
    def save_consistency_analysis(self, analysis: ConsistencyAnalysis, thesis_statement: ThesisStatement, 
                                document_title: str, output_path: str = None) -> str:
        """
        保存一致性分析结果到文件
        
        Args:
            analysis: 一致性分析结果
            thesis_statement: 核心论点结构
            document_title: 文档标题
            output_path: 输出路径（可选）
            
        Returns:
            str: 保存的文件路径
        """
        import os
        from datetime import datetime
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[^\w\s-]', '', document_title).strip()
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        
        if output_path is None:
            output_path = f"consistency_analysis_{safe_title}_{timestamp}.json"
        elif os.path.isdir(output_path):
            # 如果传入的是目录，则在目录下生成带时间戳的文件名
            filename = f"consistency_analysis_{safe_title}_{timestamp}.json"
            output_path = os.path.join(output_path, filename)
        
        # 准备保存的数据
        save_data = {
            "document_title": document_title,
            "analysis_timestamp": timestamp,
            "thesis_statement": {
                "main_thesis": thesis_statement.main_thesis,
                "supporting_arguments": thesis_statement.supporting_arguments,
                "key_concepts": thesis_statement.key_concepts
            },
            "consistency_analysis": {
                "overall_consistency_score": analysis.overall_consistency_score,
                "total_issues_found": analysis.total_issues_found,
                "consistency_issues": [
                    {
                        "section_title": issue.section_title,
                        "issue_type": issue.issue_type,
                        "description": issue.description,
                        "evidence": issue.evidence,
                        "suggestion": issue.suggestion
                    }
                    for issue in analysis.consistency_issues
                ],
                "well_aligned_sections": analysis.well_aligned_sections,
                "improvement_suggestions": analysis.improvement_suggestions
            }
        }
        
        # 保存JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        self.colored_logger.info(f"💾 一致性分析结果已保存到: {output_path}")
        
        return output_path
