# Table Agent 模块架构说明

## 背景与目标
- 目标：识别文档中适合用表格呈现的内容，并将相关片段优化为结构化的 Markdown 表格，提升可读性与对比性。
- 范围：仅覆盖 `table_agent_app` 模块的分析与修改流程，不展开底层实现细节。

## 总体架构
- 核心角色：
  - `TableAgent`：流程协调器，串联“分析 → 解析 → 修改 → 输出”。
  - `TableAnalyzer`：机会识别器，调用模型判断哪些章节适合表格化，并产出建议。
  - `TableModifier`：修改器，基于建议并行生成表格化内容，确保输出干净可用。
  - 共享组件：`DocumentParser`（统一的 Markdown 章节解析，支持 H1/H2/H3）。
- 外部依赖：
  - 模型服务：通过 `OpenRouter`（`openai` 客户端，`base_url=https://openrouter.ai/api/v1`）。
  - 环境变量：`OPENROUTER_API_KEY`（必需）、`OPENROUTER_MODEL` 或 `DEFAULT_MODEL`（可选）。
- 产出结构：统一的 `unified_sections`（按 H1 组织，内含各章节的原文、建议、优化后文本、状态等）。

## 核心流程
1. 输入：接收完整的 Markdown 文档（`markdown_content`）以及文档标题（可选）。
2. 表格机会分析：`TableAnalyzer.analyze_table_opportunities` 调用模型，返回 `table_opportunities` 列表（含 `section_title` 与建议）。
3. 章节解析：`DocumentParser.parse_sections` 将文档切分为按 H1/H2/H3 组织的结构，供后续定位与替换。
4. 并行优化：`TableModifier.apply_modifications` 使用线程池对目标章节并行生成表格化版本，并清理模型响应中的多余标记。
5. 统一输出：`TableAgent.build_unified_output` 将修改结果合并为 `unified_sections`，按 H1 标题归档，便于后续落地与展示。
6. 返回结果：返回 `unified_sections`（JSON 字典）。

> 流程示意：
> 输入 Markdown → 机会分析（Analyzer）→ 章节解析（DocumentParser）→ 并行优化（Modifier）→ 构建统一输出（TableAgent）→ 返回 `unified_sections`

## 优化内容与效果
- 优化类型：将“数字清单、对比项、团队配置、时间安排、风险清单、指标与预算”等适合结构化表达的段落转为表格。
- 转换策略：从序号/段落中抽取关键字段并表头化（如“项目/对象、数量/面积、用途/职责、备注”），保留原章节顺序与层级；对于 H2/H3 合并的章节，按 `二级标题 > 三级标题` 组织。
- 清理规则：
  - 移除围栏与代码块标记（如 ```markdown / ```），避免污染正文；
  - 去除重复标题行，避免“标题 + 标题”重复；
  - 统一数值与单位的基本格式（如“25,000 平方米”），减少歧义；
  - 保留图片与已检索表格标记，不擅自删除附件引用。
- 输出结构：每个被优化的章节会包含 `original_content`（原文片段）、`suggestion`（优化说明）、`regenerated_content`（表格化后文本）、`status=table_optimized`，方便路由服务与前端消费。
- 质量保障：并行处理失败的章节会回退到原文；模型响应做格式清理与容错，确保落地后可读。
- 业务成效：提升跨章节的可读性与横向对比能力，适合评审与汇报；产出 `unified_sections` 与扁平化结果便于系统对接。

### 典型场景
- “主要建设内容、设备清单、人员分工、项目里程碑、风险与应对、费用与预算、指标对比”等段落均可表格化呈现。

### 示例（简化）
原文（节选）：
```
## 六、主要建设内容
1. 综合教学楼：建筑面积 25,000 平方米，用于公共课程教学。
2. 实训大楼：建筑面积 18,000 平方米，配备实训室和实验室。
```
优化后（节选）：
```
## 六、主要建设内容
| 项目         | 数量/面积       | 用途/说明           |
|--------------|-----------------|---------------------|
| 综合教学楼   | 25,000 平方米   | 公共课程教学        |
| 实训大楼     | 18,000 平方米   | 实训室与实验室配置  |
```

### 边界与不处理
- 纯叙事性段落、不具备可结构化字段的内容不做强制表格化；
- 无法可靠抽取字段或语义噪声较高的段落保持原样；
- 不随意改动事实与数值，仅做排版与呈现优化。

## 模块职责与边界
- `TableAgent`
  - 负责日志、异常兜底，以及整体步骤编排。
  - 当未发现优化机会时，直接返回空结果，避免无效计算。
- `TableAnalyzer`
  - 负责提示词构建与 API 调用，响应解析为机会列表。
  - 对短文本（长度不足）进行预警，避免无效分析。
- `TableModifier`
  - 并行处理多个章节，提升吞吐（默认 `max_workers=5`）。
  - 对模型返回的内容做清理（去除代码块标记、重复标题行等）。
  - 失败时返回原始内容，确保稳健（不因少量失败影响整体）。
- `DocumentParser`
  - 统一解析标题与章节结构，输出 `{h1: {section_key: content}}` 的嵌套字典。
  - 支持 H2 与 H3 合并为 `section_key`（如 `二级标题 > 三级标题`）。

## 输入与输出
- 输入参数：
  - `markdown_content`（字符串，必填）
  - `document_title`（字符串，可选）
- 输出数据：
  - `unified_sections`（字典）：按 H1 组织章节结果。
  - 每个章节包含：`original_content`、`suggestion`、`regenerated_content`、`word_count`、`status`。
- 简例（结构示意）：
  - `{"项目概述": {"主要建设内容": {"original_content": "...", "suggestion": "...", "regenerated_content": "...", "status": "table_optimized"}}}`

## 日志与异常处理
- 日志级别：默认 `INFO`；关键步骤打点（分析、解析、并行优化、输出构建）。
- 异常策略：
  - 分析失败：抛出异常并记录错误。
  - 修改失败：单章回退到原文，不影响其它章节。
  - 响应解析：对非严格 JSON 响应做清理与容错（如剥离围栏标记）。

## 并发与性能
- 并行优化：线程池处理多个章节，提升整体效率。
- 速率限制：受模型服务速率与配额限制，建议合理设置 `max_workers` 与模型参数。
- 清理与后处理：减少无效字符与重复标题，提升最终文档一致性。

## 配置与依赖
- 环境变量：
  - `OPENROUTER_API_KEY`（必需）：模型访问凭证。
  - `OPENROUTER_MODEL` / `DEFAULT_MODEL`（可选）：指定模型。
- 主要依赖：`openai`、`concurrent.futures`、`logging`。

## 与路由服务的集成（可选说明）
- 路由位置：`router/routers/table_agent_router.py`
- 关键端点：
  - `POST /v1/pipeline-async`：提交异步处理，返回 `task_id`。
  - `GET /v1/task/{task_id}`：查询任务状态。
  - `GET /v1/result/{task_id}`：获取 `unified_sections` 原始结构。
  - `GET /v1/result-flat/{task_id}`：获取前端友好格式（扁平化章节数组）。
- 输出文件存储：`router/outputs/table_agent/`（自动生成带时间戳的 JSON 文件）。

## 运行与验证
- 本地快速验证：在项目根目录设置环境变量后运行：
  - `python e:\gaosi\review_app\table_agent_app\run_table_agent.py`
- 服务化集成：启动路由服务（FastAPI）后，通过上述端点进行调用与结果获取。

## 可扩展性建议
- 机会识别：扩展提示词以覆盖更多结构化片段（如参数表、指标对比等）。
- 并发策略：根据模型速率与主机资源调整线程池与队列策略。
- 输出格式：根据业务需要扩展 `unified_sections` 字段或增加扁平化转换层。
- 解析能力：在 `DocumentParser` 中支持更多标题级别或自定义权重解析。

## 注意事项
- 文档需包含明确的 H2/H3 标题以便准确定位章节。
- 对模型响应进行清理是必要步骤，避免将围栏或重复标题带入最终结果。
- 当文档内容过短时可能产生空结果，这属于预期行为。