# 文档质量优化系统

基于OpenRouter API的智能文档质量分析和优化系统，采用全新的两步式工作流程。

## 🔄 新工作流程

### 步骤1：全局分析
- **输入**：完整的Markdown文档
- **输出**：包含修改指令和表格优化机会的JSON分析结果
- **功能**：
  - 识别文档中的冗余内容和质量问题
  - 分析适合用表格呈现的结构化内容

### 步骤2：文档修改  
- **输入**：原始Markdown文档 + 分析结果JSON
- **输出**：优化后的Markdown文档
- **功能**：
  - 基于分析结果智能修改原文档
  - 将适合的内容转换为Markdown表格格式
  - 使用 **【表格优化】** 标记突出显示优化的表格

## 🚀 快速开始

### 1. 环境配置

复制配置模板并填入API密钥：
```bash
cp env_template.txt .env
# 编辑 .env 文件，设置 OPENROUTER_API_KEY
```

### 2. 完整优化流程（推荐）

```bash
python run_document_optimizer.py your_document.md
```

这将自动执行两个步骤并生成：
- 分析结果JSON文件
- 优化后的Markdown文档
- 详细的修改报告

### 3. 分步执行

如果需要分别执行两个步骤：

**步骤1：全局分析**
```bash
python run_document_optimizer.py --step1 your_document.md
```

**步骤2：文档修改**
```bash
python run_document_optimizer.py --step2 your_document.md analysis_result.json
```

## 📁 项目结构

```
final_review_agent_app/
├── document_reviewer.py      # 文档质量分析器
├── document_modifier.py      # 文档修改器
├── run_document_optimizer.py # 主程序（新工作流程）
├── run_reviewer.py          # 单独的分析工具
├── check_prompt.py          # 提示词检查工具
├── env_template.txt         # 配置模板
└── README.md               # 本文件
```

## 🔧 核心组件

### DocumentReviewer
- 负责文档质量分析
- 使用OpenRouter API进行智能分析
- 输出结构化的修改指令

### DocumentModifier  
- 负责基于分析结果修改文档
- 使用LLM进行章节内容重写
- 保持文档结构不变

### DocumentOptimizer
- 整合分析和修改功能
- 提供完整的优化流程
- 支持分步执行和完整执行

## 📊 输出文件

### 分析结果 (JSON)
```json
{
  "document_title": "文档标题",
  "analysis_timestamp": "2024-01-01 12:00:00",
  "issues_found": 3,
  "modification_instructions": [
    {
      "section_title": "章节标题",
      "modification_type": "content_optimization",
      "instruction": "具体的修改建议",
      "priority": "medium"
    }
  ],
  "table_opportunities": [
    {
      "section_title": "人员配置",
      "table_opportunity": "将人员配置信息转换为表格格式",
      "content_type": "personnel_allocation",
      "priority": "high"
    }
  ],
  "analysis_summary": "分析摘要"
}
```

### 修改报告 (JSON)
```json
{
  "original_document": "原文档路径",
  "analysis_file": "分析文件路径", 
  "optimized_document": "优化文档路径",
  "modification_timestamp": "2024-01-01 12:00:00",
  "sections_modified": 3,
  "tables_optimized": 2,
  "modifications_applied": [...],
  "table_optimizations_applied": [...],
  "overall_improvement": "改进摘要"
}
```

## ⚙️ 配置选项

在 `.env` 文件中可配置：

```env
# API配置
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DEFAULT_MODEL=deepseek/deepseek-chat-v3-0324

# 处理配置
API_TEMPERATURE=0.1
API_MAX_TOKENS=8000
API_TIMEOUT=60

# 输出配置
DEFAULT_OUTPUT_DIR=./test_results
LOG_LEVEL=INFO
```

## 🔍 使用示例

### 示例1：完整优化
```bash
python run_document_optimizer.py report.md
```

输出：
```
🚀 开始完整文档优化流程: report.md
🔍 步骤1：开始全局分析文档 - report.md
🔍 开始分析表格优化机会...
📊 表格机会分析完成，发现 2 个优化机会
✅ 步骤1完成 - 分析结果已保存: ./analysis_results/analysis_report_md_20240101_120000.json
📊 分析摘要: 发现 3 个问题，2 个表格优化机会
🔧 步骤2：开始修改文档
📊 表格优化完成: 人员配置
📊 表格优化完成: 技术规格
📊 表格优化完成，优化了 2 个表格
✅ 步骤2完成 - 优化文档已保存: ./optimized_results/optimized_report_md_20240101_120001.md
📝 修改摘要: 修改了 3 个章节，优化了 2 个表格
🎉 完整优化流程完成！
```

### 示例2：仅分析
```bash
python run_reviewer.py document.md
```

### 示例3：快速测试（推荐）
```bash
# 使用内置测试文档快速测试
python test_workflow.py

# 或者直接运行优化器（会提示使用默认文档）
python run_document_optimizer.py
```

### 示例4：检查配置
```bash
python check_prompt.py
```

## 📊 表格优化功能

系统会自动识别适合用表格呈现的内容，如：

### 优化前：
```
（2）职能部门人员：
综合管理部：
行政专员：2人。负责日常行政事务、文档管理。
财务专员：2人。负责预算、核算及财务报表。
人力资源专员：1人。负责人事招聘、培训及绩效管理。
```

### 优化后：
```markdown
（2）职能部门人员：

**【表格优化】**
| 部门 | 职位 | 人数 | 职责描述 |
|------|------|------|----------|
| 综合管理部 | 行政专员 | 2人 | 负责日常行政事务、文档管理 |
| 综合管理部 | 财务专员 | 2人 | 负责预算、核算及财务报表 |
| 综合管理部 | 人力资源专员 | 1人 | 负责人事招聘、培训及绩效管理 |
```

系统支持的表格类型：
- 人员配置信息
- 组织架构信息  
- 规格参数对比
- 分类列表信息
- 其他结构化数据

## 🚨 注意事项

1. **API密钥**：必须在 `.env` 文件中设置有效的 `OPENROUTER_API_KEY`
2. **文档格式**：目前支持Markdown格式文档
3. **网络连接**：需要稳定的网络连接访问OpenRouter API
4. **文件编码**：建议使用UTF-8编码的文档文件
5. **表格标记**：优化后的表格会用 **【表格优化】** 标记突出显示

## 🔄 从旧版本迁移

如果你之前使用的是包含 `json_merger.py` 和 `update_json_content.py` 的版本：

1. 这些文件已被删除，功能已整合到新的工作流程中
2. 使用 `run_document_optimizer.py` 替代之前的多步骤流程
3. 新流程更简单、更高效，直接处理Markdown文档

## 📝 日志

系统会生成以下日志文件：
- `document_optimization.log` - 完整优化流程日志
- `document_quality_analysis.log` - 质量分析日志

## 🤝 支持

如有问题，请检查：
1. API密钥是否正确配置
2. 网络连接是否正常
3. 文档格式是否为UTF-8编码的Markdown
4. 查看日志文件获取详细错误信息
