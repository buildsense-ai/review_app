"""
文档质量评估器 - 使用OpenRouter API进行冗余度分析

负责对生成的文档进行深度质量评估，识别不必要的冗余内容，
并提供优化建议。
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dataclasses import dataclass, field


@dataclass
class RedundancyAnalysis:
    """冗余分析结果数据结构"""
    total_unnecessary_redundancy_types: int = 0
    unnecessary_redundancies_analysis: List[Dict[str, Any]] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)


class ColoredLogger:
    """彩色日志记录器"""
    COLORS = {
        'RESET': '\033[0m', 'BLUE': '\033[94m', 'GREEN': '\033[92m', 
        'YELLOW': '\033[93m', 'RED': '\033[91m', 'PURPLE': '\033[95m', 
        'CYAN': '\033[96m', 'WHITE': '\033[97m',
    }
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _colorize(self, text: str, color: str) -> str:
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['RESET']}"
    
    def info(self, message: str): 
        self.logger.info(message)
    
    def error(self, message: str): 
        self.logger.error(message)
    
    def warning(self, message: str): 
        self.logger.warning(message)
    
    def debug(self, message: str): 
        self.logger.debug(message)
    
    def analysis_start(self, title: str): 
        self.logger.info(self._colorize(f"\n🔍 开始文档质量分析: {title}", 'PURPLE'))
    
    def analysis_complete(self, title: str): 
        self.logger.info(self._colorize(f"✅ 文档'{title}'质量分析完成", 'WHITE'))
    
    def redundancy_found(self, count: int): 
        self.logger.info(self._colorize(f"⚠️ 发现 {count} 类不必要的冗余内容", 'YELLOW'))
    
    def api_call(self, content: str): 
        self.logger.info(self._colorize(f"🤖 API调用: {content}", 'GREEN'))
    
    def api_response(self, content: str): 
        self.logger.info(self._colorize(f"📡 API响应: {content}", 'CYAN'))


class DocumentReviewer:
    """文档质量评估器"""
    
    def __init__(self, api_key: str = None):
        """
        初始化文档评估器
        
        Args:
            api_key: OpenRouter API密钥
        """
        # 如果没有提供API key，从环境变量获取
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.colored_logger = ColoredLogger(__name__)
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        
        # 冗余分析提示词模板
        self.redundancy_analysis_prompt = """
# 角色
你是一名专业的文档分析师和高级编辑，擅长识别文本中的逻辑结构、信息层级和冗余内容。

# 任务
你的核心任务是深度分析我提供的文档正文，严格按照以下标准，识别所有不必要的冗余表达，并针对每一个问题点提出具体的修改建议。

# 评估范围限制（重要）
只评估"正文"段落，严格忽略以下所有非正文内容：
1) 任何"### 相关图片资料"标题及其后的图片描述/图片来源/图片Markdown（直到下一个二级标题`## `或文末）。
2) 任意 Markdown 图片语法行：包含 `![` 或 `](http` 的行。
3) 含有"图片描述:"或"图片来源:"开头的行。
4) 任何"### 相关表格资料"标题及其后的表格内容，或任意以 `|` 开头的 Markdown 表格行。
5) 代码块、引用块、脚注等非正文元素。

务必不要基于上述内容做出判断、引用或提出修改建议。你的关注点仅限各小节的正文叙述性文本（即二级标题`## {subtitle}`下的段落文字）。

# 核心标准与定义
在执行任务时，你必须严格区分"必要的重复"和"不必要的冗余"。

不必要的冗余（需要识别）：
定义：在不同章节或同一章节中，对同一具体事实、细节或描述进行重复性陈述，包括：
- 相同或高度相似的句子、段落在多个章节中出现
- 同一章节内反复表达相同含义的内容
- 过度使用相同的修饰词、短语或表述方式
特征：导致文档冗长，降低阅读效率和专业性。

必要的重复（可以保留）：
定义：为强化核心论点、服务于不同章节的论证逻辑而进行的策略性重复。
特征：每次重复都有明确的功能性目的，如承上启下、强调重点等。

**重要提示**：当你发现任何形式的重复内容时，都应该提出优化建议。宁可多识别一些潜在问题，也不要遗漏明显的冗余。

# 输出要求（仅JSON）
你的最终输出必须是一个结构化的 JSON 数组。根据冗余情况的不同，使用以下两种格式：

**情况1：同章节内部冗余**
```json
[
  {
    "subtitle": "章节标题",
    "suggestion": "针对该章节内部冗余的具体修改建议，如合并重复段落、删除冗余表述等。"
  }
]
```

**情况2：不同章节间冗余**
```json
[
  {
    "subtitles": ["章节标题1", "章节标题2", "章节标题3"],
    "suggestion": "明确指出在「章节标题1」中保留哪些具体信息（详细描述保留的内容），在「章节标题2」中删除哪些重复信息（详细描述要删除的内容），在「章节标题3」中如何调整（如有）。确保重要信息不会在所有章节中都被删除，必须有一个章节保留完整信息。"
  }
]
```

**关键要求：**
- subtitle/subtitles: 必须精准引用文档中存在问题的章节完整标题（如："三、项目必要性分析"）
- suggestion: 必须详细说明具体的修改操作，包括：
  - 对于跨章节冗余：明确指出哪个章节保留什么内容，哪个章节删除什么内容
  - 对于章节内冗余：具体说明如何合并或删除重复内容
  - 确保重要信息得到保留，避免过度删减

# 工作流程
1) 先从原文中"逻辑上忽略"所有被【评估范围限制】列出的内容，仅保留正文段落用于分析。
2) 以章节（subtitle）为单位，查找正文中的重复信息点或写作不佳之处。
3) 依据【核心标准与定义】判断是否为不必要的冗余。
4) 根据冗余类型（同章节内 vs 跨章节），选择合适的输出格式。
5) 提供详细、可操作的修改建议，确保信息保留的合理性。
6) 严格按照【输出要求】的JSON数组格式返回，仅返回JSON，不要包含任何其他文字说明。

# 示例分析

## 示例 1：跨章节冗余（不同章节间重复）

**原始文本**
```
## 一、项目介绍

本项目符合国家中长期教育发展规划，符合省级教育事业"十四五"规划，符合清远市教育发展战略。通过本项目的建设，将进一步完善清新区职业教育体系，提升职业教育整体办学水平，促进教育公平和社会和谐发展。

## 五、项目必要性分析

本项目符合国家中长期教育发展规划，符合省级教育事业"十四五"规划，符合清远市教育发展战略，符合清远市教育事业发展总体要求，对促进职业教育发展具有重要意义。
```

**期望输出**
```json
[
  {
    "subtitles": ["一、项目介绍", "五、项目必要性分析"],
    "suggestion": "在「五、项目必要性分析」中保留完整的政策符合性表述（国家中长期教育发展规划、省级教育事业"十四五"规划、清远市教育发展战略、清远市教育事业发展总体要求），并补充对促进职业教育发展重要意义的论述。在「一、项目介绍」中删除重复的政策符合性表述，保留项目建设对清新区职业教育体系完善、办学水平提升、教育公平促进等方面的具体作用描述。"
  }
]
```

## 示例 2：同章节内冗余

**原始文本**
```
## 三、技术方案

本项目采用先进的云计算技术。云计算技术能够提供强大的计算能力。我们选择的云计算平台具有高可靠性。云计算技术的优势在于弹性扩展和成本控制。通过云计算技术，我们可以实现资源的动态分配。
```

**期望输出**
```json
[
  {
    "subtitle": "三、技术方案",
    "suggestion": "合并关于云计算技术的重复表述，整合为：本项目采用先进的云计算技术，该技术具有强大计算能力、高可靠性、弹性扩展和成本控制等优势，能够实现资源的动态分配。"
  }
]
```

待分析文档（完整原文，评估时请按上述范围只取正文）：
$document_content

**分析要求**：
1. 仔细阅读每个章节的正文内容
2. 积极寻找重复的表述、相似的句子结构、重复的概念描述
3. 特别关注项目名称、地点、目标、意义等容易重复的内容
4. 如果发现任何形式的重复，都要提出优化建议
5. 如果确实没有发现任何冗余，返回空数组 []

请严格遵循以上要求，只返回JSON格式结果。禁止输出与图片/表格/媒体相关的建议或内容。"""

        # 表格机会分析提示词模板
        self.table_opportunity_analysis_prompt = """
# 角色
你是一名专业的文档格式优化专家，擅长识别文档中适合用表格呈现的内容。

# 任务
分析文档中是否存在适合用Markdown表格格式呈现的数字、数据等内容，特别关注以下类型：
1. 项目建设内容和规模相关数据
2. 项目建筑数据性指标
3. 人员配置情况相关数据


# 输出要求
返回JSON数组，每个对象包含：
- section_title: 章节标题
- table_opportunity: 表格优化建议

如果没有发现适合表格化的内容，返回空数组 []。

# 示例分析

## 示例 1：表格优化（文字类）

**原始文本**
```
## 六、主要建设内容

1. 综合教学楼：建筑面积 25,000 平方米，用于公共课程教学。
2. 实训大楼：建筑面积 18,000 平方米，配备实训室和实验室。
3. 学生宿舍楼：建筑面积 30,000 平方米，可容纳 3,000 名学生。
4. 食堂：建筑面积 5,000 平方米，提供 6,000 个就餐座位。
```

**期望输出**
```json
[
  {
    "section_title": "六、主要建设内容",
    "table_opportunity": "可将分项建设内容转为表格，清晰对比建筑面积与功能"
  }
]
```

待分析文档：
$document_content

请严格按照JSON格式返回结果。"""

        self.colored_logger.info("✅ DocumentReviewer 初始化完成")
    
    def analyze_document_global(self, document_content: str, document_title: str = "未命名文档") -> Dict[str, Any]:
        """
        全局文档质量分析，返回完整的分析结果用于后续修改
        
        Args:
            document_content: 待分析的文档内容
            document_title: 文档标题
            
        Returns:
            Dict[str, Any]: 包含全局分析结果的字典
        """
        self.colored_logger.analysis_start(document_title)
        
        try:
            # 检查文档内容长度
            if len(document_content.strip()) < 100:
                self.colored_logger.warning("⚠️ 文档内容过短，可能无法进行有效分析")
                return {
                    "document_title": document_title,
                    "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "issues_found": 0,
                    "modification_instructions": [],
                    "analysis_summary": "文档内容过短，无需修改"
                }
            
            # 调用OpenRouter API进行冗余分析
            analysis_result = self._call_openrouter_api(document_content)
            
            # 解析API响应为全局分析格式
            global_result = self._parse_api_response_global(analysis_result, document_title)
            
            # 执行表格机会分析
            table_opportunities = self._analyze_table_opportunities(document_content)
            global_result['table_opportunities'] = table_opportunities
            
            modification_count = len(global_result.get('modification_instructions', []))
            table_count = len(table_opportunities)
            
            self.colored_logger.info(f"✅ 全局分析完成，发现 {modification_count} 个需要修改的地方，{table_count} 个表格优化机会")
            
            return global_result
            
        except Exception as e:
            self.colored_logger.error(f"❌ 文档质量分析失败: {e}")
            return {
                "document_title": document_title,
                "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "issues_found": 0,
                "modification_instructions": [],
                "table_opportunities": [],
                "analysis_summary": "分析过程中出现错误，跳过分析",
                "error": str(e)
            }
    
    def _parse_api_response_global(self, api_response: str, document_title: str) -> Dict[str, Any]:
        """
        解析API响应为全局分析格式
        
        Args:
            api_response: API响应内容
            document_title: 文档标题
            
        Returns:
            Dict[str, Any]: 全局分析结果
        """
        from datetime import datetime
        
        try:
            # 清理响应内容，移除可能的markdown代码块标记
            cleaned_response = api_response.strip()
            
            # 移除开头的代码块标记
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:].strip()
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:].strip()
            
            # 移除结尾的代码块标记
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3].strip()
            
            # 再次清理
            cleaned_response = cleaned_response.strip()
            
            # 尝试提取JSON内容
            json_match = re.search(r'[\[\{].*[\]\}]', cleaned_response, re.DOTALL)
            if not json_match:
                self.colored_logger.error(f"❌ API响应中未找到有效的JSON内容")
                return self._create_empty_global_result(document_title, "API响应格式错误")
            
            json_str = json_match.group(0)
            
            # 尝试解析JSON
            try:
                parsed_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.colored_logger.error(f"❌ JSON解析失败: {e}")
                self.colored_logger.error(f"❌ 问题JSON内容: {json_str[:500]}...")
                # 返回一个默认的空结果，而不是包含错误信息
                return {
                    "document_title": document_title,
                    "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "issues_found": 0,
                    "modification_instructions": [],
                    "analysis_summary": "AI分析响应格式错误，跳过分析",
                    "table_opportunities": []
                }
            
            # 构建全局分析结果
            modification_instructions = []
            
            if isinstance(parsed_data, list):
                for item in parsed_data:
                    # 处理单章节冗余（subtitle字段）
                    subtitle = item.get('subtitle', '')
                    # 处理多章节冗余（subtitles字段）
                    subtitles = item.get('subtitles', [])
                    suggestion = item.get('suggestion', '')
                    
                    if subtitle and suggestion:
                        # 单章节冗余
                        modification_instructions.append({
                            "subtitle": subtitle,
                            "suggestion": suggestion
                        })
                    elif subtitles and suggestion:
                        # 多章节冗余
                        modification_instructions.append({
                            "subtitles": subtitles,
                            "suggestion": suggestion
                        })
            
            issues_count = len(modification_instructions)
            
            return {
                "document_title": document_title,
                "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "issues_found": issues_count,
                "modification_instructions": modification_instructions,
                "analysis_summary": f"发现 {issues_count} 个需要优化的章节" if issues_count > 0 else "文档质量良好，无需修改"
            }
            
        except Exception as e:
            self.colored_logger.error(f"❌ 全局响应解析失败: {e}")
            return {
                "document_title": document_title,
                "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "issues_found": 0,
                "modification_instructions": [],
                "table_opportunities": [],
                "analysis_summary": "响应解析失败，跳过分析"
            }
    
    def _analyze_table_opportunities(self, document_content: str) -> List[Dict[str, Any]]:
        """
        分析文档中的表格优化机会
        
        Args:
            document_content: 文档内容
            
        Returns:
            List[Dict[str, Any]]: 表格优化机会列表
        """
        try:
            self.colored_logger.info("🔍 开始分析表格优化机会...")
            
            # 构建提示词
            prompt = self.table_opportunity_analysis_prompt.replace('$document_content', document_content)
            
            # 调用API
            # 从环境变量获取模型名称
            model_name = os.getenv('OPENROUTER_MODEL') or os.getenv('DEFAULT_MODEL') or "deepseek/deepseek-chat-v3-0324"
            
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://gauz-document-agent.com",
                    "X-Title": "GauzDocumentAgent",
                },
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            response_content = completion.choices[0].message.content.strip()
            
            # 解析响应
            table_opportunities = self._parse_table_opportunities_response(response_content)
            
            self.colored_logger.info(f"📊 表格机会分析完成，发现 {len(table_opportunities)} 个优化机会")
            
            return table_opportunities
            
        except Exception as e:
            self.colored_logger.error(f"❌ 表格机会分析失败: {e}")
            return []
    
    def _parse_table_opportunities_response(self, api_response: str) -> List[Dict[str, Any]]:
        """
        解析表格机会分析的API响应
        
        Args:
            api_response: API响应内容
            
        Returns:
            List[Dict[str, Any]]: 解析后的表格机会列表
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
            json_match = re.search(r'[\[\{].*[\]\}]', cleaned_response, re.DOTALL)
            if not json_match:
                self.colored_logger.warning("⚠️ 表格机会分析响应中未找到有效的JSON内容")
                return []
            
            json_str = json_match.group(0)
            
            # 解析JSON
            try:
                parsed_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.colored_logger.error(f"❌ 表格机会分析JSON解析失败: {e}")
                return []
            
            # 处理解析结果
            table_opportunities = []
            if isinstance(parsed_data, list):
                for item in parsed_data:
                    if isinstance(item, dict):
                        table_opportunities.append({
                            "section_title": item.get('section_title', ''),
                            "table_opportunity": item.get('table_opportunity', ''),
                            "content_type": item.get('content_type', 'general'),
                            "priority": item.get('priority', 'medium')
                        })
            
            return table_opportunities
            
        except Exception as e:
            self.colored_logger.error(f"❌ 表格机会分析响应解析失败: {e}")
            return []
    
    def _create_empty_global_result(self, document_title: str, error_message: str) -> Dict[str, Any]:
        """创建空的全局分析结果"""
        from datetime import datetime
        
        return {
            "document_title": document_title,
            "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "issues_found": 0,
            "modification_instructions": [],
            "analysis_summary": error_message,
            "error": error_message
        }
    
    def analyze_document_quality(self, document_content: str, document_title: str = "未命名文档") -> RedundancyAnalysis:
        """
        分析文档质量，识别冗余内容
        
        Args:
            document_content: 待分析的文档内容
            document_title: 文档标题
            
        Returns:
            RedundancyAnalysis: 冗余分析结果
        """
        self.colored_logger.analysis_start(document_title)
        
        try:
            # 检查文档内容长度
            if len(document_content.strip()) < 100:
                self.colored_logger.warning("⚠️ 文档内容过短，可能无法进行有效分析")
                return RedundancyAnalysis(
                    total_unnecessary_redundancy_types=0,
                    unnecessary_redundancies_analysis=[],
                    improvement_suggestions=["文档内容过短，建议增加更多详细信息"]
                )
            
            # 调用OpenRouter API进行冗余分析
            analysis_result = self._call_openrouter_api(document_content)
            
            # 解析API响应
            redundancy_analysis = self._parse_api_response(analysis_result)
            
            # 生成改进建议
            improvement_suggestions = self._generate_improvement_suggestions(redundancy_analysis)
            redundancy_analysis.improvement_suggestions = improvement_suggestions
            
            # 记录分析结果
            self.colored_logger.redundancy_found(redundancy_analysis.total_unnecessary_redundancy_types)
            self.colored_logger.info(f"✅ 文档'{document_title}'质量分析完成")
            
            return redundancy_analysis
            
        except Exception as e:
            self.colored_logger.error(f"❌ 文档质量分析失败: {e}")
            return RedundancyAnalysis(
                total_unnecessary_redundancy_types=0,
                unnecessary_redundancies_analysis=[],
                improvement_suggestions=[f"分析过程中发生错误: {str(e)}"]
            )
    
    def _call_openrouter_api(self, document_content: str) -> str:
        """
        调用OpenRouter API进行冗余分析
        
        Args:
            document_content: 文档内容
            
        Returns:
            str: API响应内容
        """
        try:
            # 记录文档内容长度
            self.colored_logger.info(f"📄 文档内容长度: {len(document_content)}字符")
            
            # 构建提示词 - 使用字符串模板避免格式化问题
            prompt = self.redundancy_analysis_prompt.replace('$document_content', document_content)
            
            self.colored_logger.api_call(f"发送冗余分析请求到OpenRouter API，内容长度: {len(prompt)}字符")
            
            # 调用API
            # 从环境变量获取模型名称
            model_name = os.getenv('OPENROUTER_MODEL') or os.getenv('DEFAULT_MODEL') or "deepseek/deepseek-chat-v3-0324"
            
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://gauz-document-agent.com",
                    "X-Title": "GauzDocumentAgent",
                },
                extra_body={},
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # 低温度确保输出一致性
                max_tokens=4000   # 足够长的输出
            )
            
            # 调试：打印响应对象信息
            self.colored_logger.debug(f"📊 API响应对象类型: {type(completion)}")
            self.colored_logger.debug(f"📊 API响应对象属性: {hasattr(completion, 'choices')}")
            
            # 详细检查响应结构
            if not hasattr(completion, 'choices'):
                self.colored_logger.error(f"❌ API响应对象没有choices属性")
                self.colored_logger.error(f"❌ 响应对象: {completion}")
                raise ValueError("API响应对象没有choices属性")
                
            if not completion.choices:
                self.colored_logger.error(f"❌ API响应中choices为空")
                self.colored_logger.error(f"❌ 完整响应: {completion}")
                raise ValueError("API响应中choices为空")
            
            if not completion.choices[0].message:
                self.colored_logger.error(f"❌ API响应中没有message")
                raise ValueError("API响应中没有message")
            
            response_content = completion.choices[0].message.content
            if response_content is None:
                self.colored_logger.error(f"❌ API响应中message.content为空")
                raise ValueError("API响应中message.content为空")
            
            self.colored_logger.api_response(f"API调用成功，响应长度: {len(response_content)} 字符")
            
            # 调试：显示完整响应内容（用于调试）
            self.colored_logger.info(f"🔍 完整API响应内容: {response_content}")
            
            # 调试：显示响应的前500个字符
            self.colored_logger.debug(f"API响应预览: {response_content[:500]}...")
            
            # 检查响应是否为空
            if not response_content or response_content.strip() == "":
                raise ValueError("API返回了空响应")
            
            return response_content
            
        except Exception as e:
            self.colored_logger.error(f"❌ OpenRouter API调用失败: {e}")
            # 添加更详细的错误信息
            if "rate limit" in str(e).lower():
                self.colored_logger.error("可能是API速率限制，请稍后重试")
            elif "timeout" in str(e).lower():
                self.colored_logger.error("API调用超时，请检查网络连接")
            elif "authentication" in str(e).lower():
                self.colored_logger.error("API密钥认证失败，请检查密钥配置")
            else:
                self.colored_logger.error(f"未知错误类型: {type(e).__name__}")
            raise
    
    def _parse_api_response(self, api_response: str) -> RedundancyAnalysis:
        """
        解析API响应，提取冗余分析结果
        
        Args:
            api_response: API响应内容
            
        Returns:
            RedundancyAnalysis: 解析后的分析结果
        """
        try:
            # 清理响应内容，移除可能的markdown代码块标记
            cleaned_response = api_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            cleaned_response = cleaned_response.strip()
            
            # 尝试提取JSON内容 - 支持数组和对象格式
            json_match = re.search(r'[\[\{].*[\]\}]', cleaned_response, re.DOTALL)
            if not json_match:
                self.colored_logger.error(f"❌ API响应中未找到有效的JSON内容，响应内容: {cleaned_response[:200]}...")
                return RedundancyAnalysis()
            
            json_str = json_match.group(0)
            
            # 尝试解析JSON
            try:
                parsed_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.colored_logger.error(f"❌ JSON解析失败: {e}")
                self.colored_logger.error(f"❌ 问题JSON内容: {json_str[:200]}...")
                return RedundancyAnalysis()
            
            # 构建RedundancyAnalysis对象
            # 处理API返回的数组格式（按照prompt要求）
            processed_analysis = []
            
            if isinstance(parsed_data, list):
                # API返回的是数组格式，每个元素包含subtitle和suggestion
                for item in parsed_data:
                    subtitle = item.get('subtitle', item.get('subtitle', '未知位置'))
                    suggestion = item.get('suggestion', '建议优化')
                    
                    # 从subtitle中提取章节主题
                    theme = subtitle
                    if subtitle.startswith('## '):
                        theme = subtitle[3:]  # 去掉"## "前缀
                    
                    processed_item = {
                        "redundant_theme": theme,
                        "count": 1,  # 每个章节算作一个冗余点
                        "subtitles": [subtitle],
                        "evidence": [suggestion],
                        "suggestion": suggestion
                    }
                    processed_analysis.append(processed_item)
                
                analysis = RedundancyAnalysis(
                    total_unnecessary_redundancy_types=len(parsed_data),
                    unnecessary_redundancies_analysis=processed_analysis
                )
            else:
                # 兼容旧的对象格式
                raw_analysis = parsed_data.get('unnecessary_redundancies_analysis', [])
                
                for item in raw_analysis:
                    processed_item = {
                        "redundant_theme": item.get('redundant_theme', item.get('redundant_text', '未知主题')),
                        "count": item.get('count', 0),
                        "subtitles": item.get('subtitles', [f"位置{i+1}" for i in range(item.get('count', 0))]),
                        "evidence": item.get('evidence', [item.get('redundant_text', '')] * item.get('count', 0)),
                        "suggestion": item.get('suggestion', f"建议删除重复的'{item.get('redundant_text', '')}'内容")
                    }
                    processed_analysis.append(processed_item)
                
                analysis = RedundancyAnalysis(
                    total_unnecessary_redundancy_types=parsed_data.get('total_unnecessary_redundancy_types', 0),
                    unnecessary_redundancies_analysis=processed_analysis
                )
            
            self.colored_logger.debug(f"✅ 成功解析API响应，发现 {analysis.total_unnecessary_redundancy_types} 类冗余")
            
            return analysis
            
        except Exception as e:
            self.colored_logger.error(f"❌ 响应解析失败: {e}")
            self.colored_logger.error(f"❌ 原始响应内容: {api_response[:300]}...")
            return RedundancyAnalysis()
    
    
    def _generate_improvement_suggestions(self, analysis: RedundancyAnalysis) -> List[str]:
        """
        基于冗余分析结果生成改进建议
        
        Args:
            analysis: 冗余分析结果
            
        Returns:
            List[str]: 改进建议列表
        """
        suggestions = []
        
        if analysis.total_unnecessary_redundancy_types == 0:
            suggestions.append("✅ 文档质量优秀，未发现不必要的冗余内容")
            return suggestions
        
        # 添加总体建议
        suggestions.append(f"📝 发现 {analysis.total_unnecessary_redundancy_types} 类不必要的冗余内容，建议进行优化")
        
        # 添加具体建议
        for redundancy in analysis.unnecessary_redundancies_analysis:
            theme = redundancy.get('redundant_theme', '未知主题')
            count = redundancy.get('count', 0)
            suggestion = redundancy.get('suggestion', '建议删除重复内容')
            
            suggestions.append(f"🔍 {theme}: 出现{count}次 - {suggestion}")
        
        # 添加通用建议
        suggestions.extend([
            "💡 建议使用概括性语言替代重复的具体描述",
            "💡 考虑将重复信息整合到专门的章节中",
            "💡 使用引用和交叉引用来避免重复"
        ])
        
        return suggestions
    
    def generate_quality_report(self, analysis: RedundancyAnalysis, document_title: str = "未命名文档") -> str:
        """
        生成质量评估报告
        
        Args:
            analysis: 冗余分析结果
            document_title: 文档标题
            
        Returns:
            str: 格式化的质量报告
        """
        report_lines = [
            f"# 文档质量评估报告",
            f"**文档标题**: {document_title}",
            f"**评估时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## 🔍 冗余分析结果",
            f"**冗余类型总数**: {analysis.total_unnecessary_redundancy_types}",
            f""
        ]
        
        if analysis.total_unnecessary_redundancy_types == 0:
            report_lines.extend([
                f"✅ **优秀**: 未发现不必要的冗余内容",
                f""
            ])
        else:
            report_lines.extend([
                f"⚠️ **发现冗余**: 共 {analysis.total_unnecessary_redundancy_types} 类不必要的冗余内容",
                f""
            ])
            
            for i, redundancy in enumerate(analysis.unnecessary_redundancies_analysis, 1):
                theme = redundancy.get('redundant_theme', '未知主题')
                count = redundancy.get('count', 0)
                subtitles = redundancy.get('subtitles', [])
                evidence = redundancy.get('evidence', [])
                suggestion = redundancy.get('suggestion', '建议优化')
                
                report_lines.extend([
                    f"### {i}. {theme}",
                    f"**出现次数**: {count}",
                    f"**出现位置**:",
                ])
                
                for subtitle in subtitles:
                    report_lines.append(f"- {subtitle}")
                
                report_lines.extend([
                    f"**冗余证据**:",
                ])
                
                for j, evidence_text in enumerate(evidence, 1):
                    # 截断过长的证据文本
                    truncated_evidence = evidence_text[:200] + "..." if len(evidence_text) > 200 else evidence_text
                    report_lines.append(f"{j}. {truncated_evidence}")
                
                report_lines.extend([
                    f"**优化建议**: {suggestion}",
                    f""
                ])
        
        # 添加改进建议
        report_lines.extend([
            f"## 💡 改进建议",
        ])
        
        for suggestion in analysis.improvement_suggestions:
            report_lines.append(f"- {suggestion}")
        
        report_lines.extend([
            f"",
            f"---",
            f"*本报告由Gauz文档Agent自动生成*"
        ])
        
        return "\n".join(report_lines)
    
    def save_analysis_result(self, analysis: RedundancyAnalysis, document_title: str, output_path: str = None) -> str:
        """
        保存分析结果到文件
        
        Args:
            analysis: 冗余分析结果
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
            output_path = f"quality_analysis_{safe_title}_{timestamp}.json"
        
        # 准备保存的数据
        save_data = {
            "document_title": document_title,
            "analysis_timestamp": timestamp,
            "total_unnecessary_redundancy_types": analysis.total_unnecessary_redundancy_types,
            "unnecessary_redundancies_analysis": analysis.unnecessary_redundancies_analysis,
            "improvement_suggestions": analysis.improvement_suggestions
        }
        
        # 保存JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        self.colored_logger.info(f"💾 分析结果已保存到: {output_path}")
        
        return output_path
    
    def save_simple_analysis_result(self, quality_issues: List[Dict[str, str]], document_title: str, output_dir: str = ".") -> str:
        """
        保存简化分析结果到文件
        
        Args:
            quality_issues: 简化分析结果列表
            document_title: 文档标题
            output_dir: 输出目录
            
        Returns:
            str: 保存的文件路径
        """
        import os
        from datetime import datetime
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[^\w\s-]', '', document_title).strip()
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        
        output_path = os.path.join(output_dir, f"quality_analysis_{safe_title}_{timestamp}.json")
        
        # 准备保存的数据
        save_data = {
            "document_title": document_title,
            "analysis_timestamp": timestamp,
            "issues_found": len(quality_issues),
            "quality_issues": quality_issues,
            "analysis_type": "simple_format"
        }
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        self.colored_logger.info(f"💾 简化分析结果已保存到: {output_path}")
        
        return output_path