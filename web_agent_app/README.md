# 论据支持度评估系统

一个基于AI的智能文档分析系统，专门用于验证学术文档中论点的事实支撑，并通过Web搜索增强内容的专业性和可信度。

## 🎯 系统功能

### 核心特性
- **整体文档处理**: 一次性处理整个文档，无需分章节处理
- **客观性论断识别**: 自动识别文档中需要事实、数据或引用支撑的论断
- **智能证据搜索**: 调用Web搜索API在权威信源中查找相关证据
- **支持度评估**: 评估证据对论断的支持程度和可信度
- **内容智能增强**: 根据评估结果进行验证、修正或补充

### 三种处理模式
1. **Verify（验证）**: 对已有证据支撑的论断进行准确性验证
2. **Modify（修正）**: 修正与证据矛盾或表述不准确的论断
3. **Supplement（补充）**: 为缺乏证据支撑的论断补充相关证据

## 🏗️ 系统架构

```
📄 整个文档输入 → 🎯 整体论断识别 → 🔍 批量证据搜索 → ⚖️ 整体分析增强 → 📄 三种输出文档
```

### 核心组件

1. **WholeDocumentPipeline（整体文档流水线）** 🆕
   - 一次性处理整个文档内容
   - 整体论断检测和关键词生成
   - 批量证据搜索和分析
   - 生成三种输出文档

2. **WebSearchAgent（Web搜索代理）**
   - 集成自定义搜索API（支持Google、Bing、DuckDuckGo）
   - 权威信源评分系统
   - 智能相关性评估

3. **智能AI分析** 🆕
   - 使用单个AI调用完成整体文档分析
   - 直接生成增强内容和证据标注
   - 提高处理效率和一致性

## 🚀 快速开始

### 1. 环境配置

```bash
# 安装依赖
pip install openai requests

# 配置API密钥
# 编辑 config.py 文件，添加你的 OpenRouter API 密钥
OPENROUTER_API_KEY = "your_api_key_here"

# 自定义搜索API已预配置
# API地址: http://43.139.19.144:8005/search
# 支持搜索引擎: Google, Bing, DuckDuckGo
```

### 1.1. 测试搜索API

```bash
# 测试搜索API连接
python test_search_api.py
```

### 2. 基本使用

```bash
# 使用默认文档和参数（最简单）
python run_evaluator.py

# 指定文档，使用默认论断数量（25个）
python run_evaluator.py document.md

# 完全自定义文档和论断数量
python run_evaluator.py document.md 20

# 分析JSON格式文档
python run_evaluator.py document.json 30
```

### 3. 编程接口

```python
from whole_document_pipeline import WholeDocumentPipeline

# 初始化流水线
pipeline = WholeDocumentPipeline()

# 运行完整评估
result = pipeline.process_whole_document(
    document_path="your_document.md",
    max_claims=20,
    max_search_results=10
)

# 查看结果
print(f"检测到 {result['statistics']['total_claims_detected']} 个论断")
print(f"处理时间: {result['processing_time']:.1f} 秒")
```

## 📊 输出结果

系统会在 `test_results` 目录下生成**三个核心文件**：

### 输出文件
1. **`evidence_analysis_[timestamp].json`** - 论据支持度评估分析
   - 包含整体证据评分、问题摘要、改进建议
   - 详细的论断分析和支持度评估
   
2. **`ai_enhanced_document_[timestamp].md`** - AI增强文档（带斜体标记）
   - 基于证据评估结果增强的完整文档
   - 用斜体标记修改和补充的内容
   - 可直接使用的最终文档

## 🔧 配置选项

### API配置
```python
# config.py
OPENROUTER_API_KEY = "your_key"                    # OpenRouter API密钥

# 自定义搜索API
CUSTOM_SEARCH_API_URL = "http://43.139.19.144:8005/search"
CUSTOM_SEARCH_ENGINES = ["google", "bing", "duckduckgo"]
CUSTOM_SEARCH_TIMEOUT = 30
```

### 系统参数
```python
MAX_CONTENT_LENGTH = 8000                # 单次处理最大内容长度
MIN_EVIDENCE_CREDIBILITY = 0.5           # 最低证据可信度阈值
MIN_EVIDENCE_RELEVANCE = 0.4             # 最低证据相关性阈值
ENHANCEMENT_CONFIDENCE_THRESHOLD = 0.6   # 内容增强置信度阈值
```

## 📈 评估指标

### 论断支持度等级
- **well_supported**: 有充分证据支撑
- **partially_supported**: 有部分证据支撑
- **poorly_supported**: 证据支撑不足
- **contradicted**: 与证据矛盾

### 证据评估维度
- **支持程度**: strong_support, moderate_support, weak_support, neutral, contradicts
- **可信度评分**: 0.0-1.0，基于信源权威性
- **相关性评分**: 0.0-1.0，基于内容匹配度

## 🌟 使用场景

### 学术写作
- 论文事实核查
- 引用完整性检验
- 论证强度评估

### 内容创作
- 文章可信度提升
- 权威证据补充
- 表述准确性优化

### 研究分析
- 文献综述增强
- 数据支撑验证
- 观点客观性评估

## 🛠️ 技术特点

### AI驱动的智能分析
- 使用Claude-3.5-Sonnet等先进模型
- 精确的论断识别和分类
- 智能的证据评估和内容生成

### 权威信源集成
- 通过自定义API获取多源搜索结果
- 学术期刊和数据库优先
- 政府和国际组织信源
- 多维度权威性评分

### 灵活的处理模式
- 支持JSON和Markdown格式
- 可配置的处理参数
- 完整的错误处理机制

## 📝 示例输出

### 命令行输出
```
📊 论据支持度评估完成
============================================================
✅ 检测论断: 15 个
🔍 搜索证据: 45 条
🔧 生成修改: 8 个
📈 整体证据评分: 0.78
⚠️ 发现问题: 3 个

📁 输出文件:
   论据支持度分析: ./evidence_evaluation_output/evidence_analysis_20240101_120000.json
   修正后文档: ./evidence_evaluation_output/evidence_enhanced_document_20240101_120000.md
```

### 分析文件结构 (evidence_analysis_*.json)
```json
{
  "overall_evidence_score": 0.78,
  "total_claims_analyzed": 15,
  "total_issues_found": 3,
  "evidence_issues": [
    {
      "claim_text": "某个需要修正的论断",
      "support_level": "poorly_supported",
      "action_needed": "supplement"
    }
  ],
  "improvement_suggestions": [
    "发现 1 个证据支撑不足的论断",
    "建议补充更多权威来源的证据支撑"
  ]
}
```

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进系统！

### 开发环境设置
```bash
git clone [repository]
cd web_agent
pip install -r requirements.txt
```

### 测试
```bash
python -m pytest tests/
```

## 📄 许可证

MIT License

## 🙋‍♂️ 支持

如有问题或建议，请提交Issue或联系开发团队。

---

**论据支持度评估系统** - 让你的文档更专业、更可信、更有说服力！
