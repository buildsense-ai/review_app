"""
论文核心论点提取器 - 使用OpenRouter API分析文档并提取核心论点

负责从文档中提取核心论点（Thesis Statement），为后续的一致性检查提供基础。
"""

import json
import logging
import re
import time
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dataclasses import dataclass, field
from config import config


@dataclass
class ThesisStatement:
    """核心论点数据结构"""
    main_thesis: str = ""
    supporting_arguments: List[str] = field(default_factory=list)
    key_concepts: List[str] = field(default_factory=list)


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
    
    def extraction_start(self, title: str): 
        self.logger.info(self._colorize(f"\n🎯 开始核心论点提取: {title}", 'PURPLE'))
    
    def extraction_complete(self, title: str): 
        self.logger.info(self._colorize(f"✅ 论点提取完成: {title}", 'WHITE'))
    
    def thesis_found(self, thesis: str): 
        self.logger.info(self._colorize(f"🎯 核心论点: {thesis[:100]}...", 'GREEN'))
    
    def api_call(self, content: str): 
        self.logger.info(self._colorize(f"🤖 API调用: {content}", 'GREEN'))
    
    def api_response(self, content: str): 
        self.logger.info(self._colorize(f"📡 API响应: {content}", 'CYAN'))


class ThesisExtractor:
    """论文核心论点提取器"""
    
    def __init__(self, api_key: str = None):
        """
        初始化论点提取器
        
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
        
        # 论点提取提示词模板
        self.thesis_extraction_prompt = """
# 角色
你是一名专业的学术论文分析师和逻辑专家，擅长从复杂的学术文档中提取核心论点和论证结构。

# 任务
你的核心任务是深度分析我提供的文档内容，提取出文档的核心论点（Thesis Statement）以及相关的论证要素。

# 分析范围
只分析"正文"段落，严格忽略以下所有非正文内容：
1) 任何"### 相关图片资料"标题及其后的图片描述/图片来源/图片Markdown（直到下一个二级标题`## `或文末）。
2) 任意 Markdown 图片语法行：包含 `![` 或 `](http` 的行。
3) 含有"图片描述:"或"图片来源:"开头的行。
4) 任何"### 相关表格资料"标题及其后的表格内容，或任意以 `|` 开头的 Markdown 表格行。
5) 代码块、引用块、脚注等非正文元素。

# 提取要求
请从文档中提取以下要素：

1. **核心论点 (main_thesis)**: 文档的中心观点或主要论述，通常是作者要证明或阐述的核心观点。
2. **支撑论据 (supporting_arguments)**: 支持核心论点的主要论据或分论点。
3. **关键概念 (key_concepts)**: 文档中反复出现的重要概念、术语或理论。

# 输出要求（仅JSON）
你的最终输出必须是一个结构化的 JSON 对象，格式如下：

{
  "main_thesis": "文档的核心论点，用一句话概括",
  "supporting_arguments": [
    "支撑论据1",
    "支撑论据2",
    "支撑论据3"
  ],
  "key_concepts": [
    "关键概念1",
    "关键概念2",
    "关键概念3"
  ]
}

# 工作流程
1) 通读全文，理解文档的整体结构和主要内容。
2) 识别文档的核心观点和主要论述。
3) 提取支撑核心论点的主要论据。
4) 识别关键概念和术语。
5) 严格按照JSON格式返回结果，不要包含任何其他文字说明。

待分析文档：
$document_content

请严格遵循以上要求，只返回JSON格式结果。"""

        self.colored_logger.info("✅ ThesisExtractor 初始化完成")
    
    def extract_thesis_from_document(self, document_content: str, document_title: str = "未命名文档") -> ThesisStatement:
        """
        从文档中提取核心论点
        
        Args:
            document_content: 待分析的文档内容
            document_title: 文档标题
            
        Returns:
            ThesisStatement: 提取的论点结构
        """
        self.colored_logger.extraction_start(document_title)
        
        try:
            # 检查文档内容长度
            if len(document_content.strip()) < 200:
                self.colored_logger.warning("⚠️ 文档内容过短，可能无法进行有效的论点提取")
                return ThesisStatement(
                    main_thesis="文档内容过短，无法提取有效论点",
                    supporting_arguments=["需要更多内容进行分析"],
                    key_concepts=[]
                )
            
            # 调用OpenRouter API进行论点提取
            try:
                extraction_result = self._call_openrouter_api(document_content)
            except Exception as api_error:
                self.colored_logger.error(f"❌ API调用失败: {api_error}")
                return ThesisStatement(
                    main_thesis=f"API调用失败: {str(api_error)}",
                    supporting_arguments=[],
                    key_concepts=[]
                )
            
            # 解析API响应
            try:
                thesis_statement = self._parse_api_response(extraction_result)
            except Exception as parse_error:
                self.colored_logger.error(f"❌ 响应解析失败: {parse_error}")
                return ThesisStatement(
                    main_thesis=f"响应解析失败: {str(parse_error)}",
                    supporting_arguments=[],
                    key_concepts=[]
                )
            
            # 检查是否成功提取到论点
            if not thesis_statement.main_thesis or thesis_statement.main_thesis.startswith("提取失败") or thesis_statement.main_thesis.startswith("API调用失败") or thesis_statement.main_thesis.startswith("响应解析失败"):
                self.colored_logger.error(f"❌ 论点提取失败或为空")
                return thesis_statement
            
            # 记录提取结果
            self.colored_logger.thesis_found(thesis_statement.main_thesis)
            self.colored_logger.extraction_complete(document_title)
            
            return thesis_statement
            
        except Exception as e:
            self.colored_logger.error(f"❌ 论点提取失败（未知错误）: {e}")
            import traceback
            self.colored_logger.error(f"完整错误信息: {traceback.format_exc()}")
            return ThesisStatement(
                main_thesis=f"提取失败: {str(e)}",
                supporting_arguments=[],
                key_concepts=[]
            )
    
    def _call_openrouter_api(self, document_content: str) -> str:
        """
        调用OpenRouter API进行论点提取
        
        Args:
            document_content: 文档内容
            
        Returns:
            str: API响应内容
        """
        try:
            # 记录文档内容长度
            self.colored_logger.info(f"📄 文档内容长度: {len(document_content)}字符")
            
            # 构建提示词
            prompt = self.thesis_extraction_prompt.replace('$document_content', document_content)
            
            self.colored_logger.api_call(f"发送论点提取请求到OpenRouter API，内容长度: {len(prompt)}字符")
            
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
                temperature=config.thesis_extraction_temperature,
                max_tokens=config.max_tokens
            )
            
            # 检查响应结构
            if not hasattr(completion, 'choices') or not completion.choices:
                raise ValueError("API响应格式错误")
            
            if not completion.choices[0].message or not completion.choices[0].message.content:
                raise ValueError("API响应内容为空")
            
            response_content = completion.choices[0].message.content
            
            # 检查响应完整性
            if hasattr(completion, 'usage'):
                self.colored_logger.info(f"📊 Token使用情况: {completion.usage}")
            
            finish_reason = completion.choices[0].finish_reason if hasattr(completion.choices[0], 'finish_reason') else None
            if finish_reason == 'length':
                self.colored_logger.warning("⚠️ API响应被截断（达到max_tokens限制），建议增加max_tokens配置")
            elif finish_reason:
                self.colored_logger.debug(f"完成原因: {finish_reason}")
            
            self.colored_logger.api_response(f"API调用成功，响应长度: {len(response_content)} 字符")
            
            return response_content
            
        except Exception as e:
            self.colored_logger.error(f"❌ OpenRouter API调用失败: {e}")
            raise
    
    def _parse_api_response(self, api_response: str) -> ThesisStatement:
        """
        解析API响应，提取论点结构
        
        Args:
            api_response: API响应内容
            
        Returns:
            ThesisStatement: 解析后的论点结构
        """
        try:
            # 添加调试日志：记录原始响应的前后部分
            self.colored_logger.info(f"📝 API响应总长度: {len(api_response)} 字符")
            self.colored_logger.debug(f"📝 API响应前200字符: {api_response[:200]}")
            self.colored_logger.debug(f"📝 API响应后200字符: {api_response[-200:]}")
            
            # 清理响应内容，移除可能的markdown代码块标记
            cleaned_response = api_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            cleaned_response = cleaned_response.strip()
            
            # 改进：先尝试直接解析整个响应
            try:
                parsed_data = json.loads(cleaned_response)
                self.colored_logger.debug(f"✅ 直接解析成功")
            except json.JSONDecodeError as direct_error:
                self.colored_logger.debug(f"直接解析失败，尝试提取JSON: {direct_error}")
                
                # 如果直接解析失败，使用正则提取
                # 改用非贪婪匹配，从第一个 { 开始尝试找到完整的 JSON 对象
                json_match = None
                
                # 尝试多种正则模式
                patterns = [
                    r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}',  # 非贪婪匹配，支持一层嵌套
                    r'\{.*?\}(?=\s*$)',  # 非贪婪匹配到文档末尾
                    r'\{.*\}',  # 贪婪匹配（兜底）
                ]
                
                for i, pattern in enumerate(patterns):
                    json_match = re.search(pattern, cleaned_response, re.DOTALL)
                    if json_match:
                        self.colored_logger.debug(f"使用模式 {i+1} 匹配成功")
                        break
                
                if not json_match:
                    self.colored_logger.error(f"❌ API响应中未找到有效的JSON内容")
                    self.colored_logger.error(f"响应内容前500字符: {cleaned_response[:500]}...")
                    return ThesisStatement()
                
                json_str = json_match.group(0)
                self.colored_logger.debug(f"提取的JSON长度: {len(json_str)} 字符")
                
                # 尝试解析JSON
                try:
                    parsed_data = json.loads(json_str)
                    self.colored_logger.debug(f"✅ 正则提取后解析成功")
                except json.JSONDecodeError as e:
                    self.colored_logger.error(f"❌ JSON解析失败: {e}")
                    self.colored_logger.error(f"JSON内容前500字符: {json_str[:500]}")
                    self.colored_logger.error(f"JSON内容后500字符: {json_str[-500:]}")
                    
                    # 尝试找到JSON截断的位置
                    try:
                        # 逐步减少内容长度，尝试找到有效的JSON
                        for trim_length in [100, 500, 1000, 2000]:
                            if len(json_str) > trim_length:
                                trimmed_json = json_str[:-trim_length]
                                # 尝试补全最后的大括号
                                if trimmed_json.count('{') > trimmed_json.count('}'):
                                    trimmed_json += '}'
                                try:
                                    parsed_data = json.loads(trimmed_json)
                                    self.colored_logger.warning(f"⚠️ 通过截断修复JSON成功（截断 {trim_length} 字符）")
                                    break
                                except:
                                    continue
                        else:
                            return ThesisStatement()
                    except:
                        return ThesisStatement()
            
            # 构建ThesisStatement对象
            thesis_statement = ThesisStatement(
                main_thesis=parsed_data.get('main_thesis', ''),
                supporting_arguments=parsed_data.get('supporting_arguments', []),
                key_concepts=parsed_data.get('key_concepts', [])
            )
            
            self.colored_logger.info(f"✅ 成功解析API响应，提取论点: {thesis_statement.main_thesis[:100]}...")
            
            return thesis_statement
            
        except Exception as e:
            self.colored_logger.error(f"❌ 响应解析失败: {e}")
            import traceback
            self.colored_logger.error(f"完整错误信息: {traceback.format_exc()}")
            return ThesisStatement()
    
    def save_thesis_statement(self, thesis: ThesisStatement, document_title: str, output_path: str = None) -> str:
        """
        保存论点结构到文件
        
        Args:
            thesis: 论点结构
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
            output_path = f"thesis_statement_{safe_title}_{timestamp}.json"
        
        # 准备保存的数据
        save_data = {
            "document_title": document_title,
            "extraction_timestamp": timestamp,
            "thesis_statement": {
                "main_thesis": thesis.main_thesis,
                "supporting_arguments": thesis.supporting_arguments,
                "key_concepts": thesis.key_concepts
            }
        }
        
        # 保存JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        self.colored_logger.info(f"💾 论点结构已保存到: {output_path}")
        
        return output_path
    
    def generate_thesis_report(self, thesis: ThesisStatement, document_title: str = "未命名文档") -> str:
        """
        生成论点分析报告
        
        Args:
            thesis: 论点结构
            document_title: 文档标题
            
        Returns:
            str: 格式化的论点报告
        """
        report_lines = [
            f"# 论文核心论点分析报告",
            f"**文档标题**: {document_title}",
            f"**分析时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## 🎯 核心论点",
            f"**主要论点**: {thesis.main_thesis}",
            f"",
            f"## 📋 支撑论据",
        ]
        
        if thesis.supporting_arguments:
            for i, arg in enumerate(thesis.supporting_arguments, 1):
                report_lines.append(f"{i}. {arg}")
        else:
            report_lines.append("暂无明确的支撑论据")
        
        report_lines.extend([
            f"",
            f"## 🔑 关键概念",
        ])
        
        if thesis.key_concepts:
            for concept in thesis.key_concepts:
                report_lines.append(f"- {concept}")
        else:
            report_lines.append("暂无明确的关键概念")
        
        report_lines.extend([
            f"",
            f"---",
            f"*本报告由Gauz论点一致性Agent自动生成*"
        ])
        
        return "\n".join(report_lines)
