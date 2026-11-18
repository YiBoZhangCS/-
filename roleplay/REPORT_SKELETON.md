# 信息检索课程大作业：基于 CharacterEval 的中文角色扮演对话生成
**实验报告工作稿；所有 [待填写] 项必须依据实际运行记录与 OJ 输出补全，不得视为最终报告。**

## 1 摘要
研究任务：给定人物画像、所属作品和多轮对话，生成下一轮符合人物身份的中文回复。
本文复用 Tu et al. (ACL 2024) CharacterEval 的数据表征和评测思路，通过 API
模型选型及结构化角色提示完成课程题目。571 条固定测试样本、77 个角色、24 部作品。
方法：以全角色画像和完整上下文作为条件，对照直接角色提示与结构化人物/场景契约；
比较 [实际模型列表]，并在给定 API 预算内选择 [最终模型]。
OJ 12 维等权 Average：[待填写]；估算 API 成本：[待填写] USD。

## 2 问题定义与数据
输入样本 x_i = (id_i, role_i, novel_i, context_i)，角色画像 P(role_i)。
模型生成 y_i = f_theta(P(role_i), context_i, role_i, novel_i; prompt)。
测试集 571 个互不重复 ID；77 个角色，覆盖 24 部作品；全部人物均能在角色画像中找到。
角色画像对应 CharacterEval 任务；与官方版本逐字一致性尚待独立核验，不以此作为已证实结论。
测试集文件名为 jsonl，但内容是 JSON 数组；指标映射为 JSON 对象。
指标映射存在 567 个 ID 键，其中 4 个 ID 没有对应评估指标，
但仍需提交全部 571 个 ID 的回答。
上下文字符数：min=6，中位数=155，P90=449，max=1237；
画像 JSON 序列化字符数（按每条测试样本统计、ensure_ascii=False、默认分隔符）：
min=175，中位数=839，P90=1722，max=2579。
以上统计已由 audit_data.py 复核，原始文件 SHA256 和指标覆盖记录见 audit/data_stats.json。

## 3 背景工作
CharacterEval: Tu et al., ACL 2024，提供中文角色扮演 benchmark、角色画像及
CharacterRM。论文整体含 4 个维度及 13 项指标；本课程采用其中 12 项主观指标，
将 12 个指标的未舍入平均成绩再等权平均作为 Average。
官方参考实现：按角色读取资料、组合上下文、生成回复、展开对应指标、
以 BaichuanCharRM 评估。复现时不重新训练模型。
参考：Ruangtanusak et al. (2025), Talk Less, Call Right。
其角色卡/场景契约和规则提示可启发本任务，但论文是在不同的
CPDC 2025 基准上测试，不能将该论文的分数拿来证明 CharacterEval 的改进。
另参考 Peng & Shang, NeurIPS 2025, Codifying Character Logic in Role-Playing；
其可执行条件式角色逻辑较复杂，若课程时间有限只借鉴结构化决策思想，不部署完整 FSM。

## 4 方法
4.1 模型输入构建：原始角色卡（JSON 格式）+ 作品名 + 目标角色名 + 完整历史对话；
以系统提示控制角色身份与输出格式。
4.2 Baseline：简单角色扮演系统提示，直接续写。
补充课件要求的画像消融：no_profile 与 baseline 保持相同系统提示、模型、解码参数和样本，
仅去掉角色画像。baseline 与 structured 的对照是提示词消融，二者都含画像，不能混淆。
4.3 Structured：场景契约包括对方意图、情绪、角色关系、角色动机、
角色语言风格、动作适配、避免虚构。中间推理不输出，仅生成台词。
4.4 后处理：检查首行，必要时移除开头的重复角色名前缀；不生成多行、
ERROR 或空字符串；保留原始数据顺序/ID。
4.5 运行防护：以源数据哈希保证输入不漂移；运行日志和 config 保存于
roleplay/runs；断点续跑。API 花费按供应商实际报价与返回 token 使用量估算。
4.6 不使用训练数据微调，不修改公开测试集，也不向模型输入评测得分信息。

## 5 实验设计
模型：
| 实验ID | 模型实际ID | Prompt | 样本数 | 估算美元 | OJ/本地指标 | 说明 |
|---|---|---|---:|---:|---|---|
| E0 | [待填写] | baseline | 40 | [待填写] | [待填写] | 对照 |
| E1 | [待填写] | structured | 40 | [待填写] | [待填写] | 提示词消融 |
| E2 | [待填写] | structured | 40 | [待填写] | [待填写] | 模型比较 |
| E3 | [待填写] | structured | 571 | [待填写] | [待填写] | 最终提交 |

注意：小样本对比并不等同于 OJ 评分。若没有本地 CharacterRM，
小样本采用预定义评价表格的人审或仅做定性误差分析，
不要凭空填写 OJ 分数。
对模型价格、上下文限制、实际 endpoint 和推理模式，应以供应商日志和
配置快照为准。记录 token 用量、延迟、输出长度、失败/重试次数。

## 6 结果与分析
6.1 OJ 实际 12 项分数：
Fluency [ ], Coherence [ ], Consistency [ ], Exposure [ ], Accuracy [ ],
Hallucination [ ], Behavior [ ], Utterance [ ], Humanlikeness [ ],
Communication_skills [ ], Diversity [ ], Empathy [ ], Average [ ]。
6.2 比较：不同模型、提示词、响应长度和风格控制的结果。
6.3 典型成功案例：[真实 ID / 原始 context 节选 / 生成回复 / 分析]。
6.4 失败案例：[真实 ID / 异常类别 / 改进建议]。
6.5 成本分析：实际总请求数、输入/输出 tokens、定价来源、
失败重试成本、API 总金额/候选方案性价比。

## 7 局限与结论
固定的 571 条课堂子集与官方论文完整评测集存在差异；CharacterRM 与人工偏好
不完全等价；模型随机性、API 代理或版本变化可能影响结果。
精简复现的价值在于可验证的端到端生成、对照、成本与错误分析，而非提出新算法。

## 参考文献
[1] Tu Q., Fan S., Tian Z., et al. CharacterEval: A Chinese Benchmark for
Role-Playing Conversational Agent Evaluation. ACL, 2024.
https://aclanthology.org/2024.acl-long.638/
[2] Ruangtanusak S., Taveekitworachai P., Pipatanakul K. Talk Less, Call Right:
Enhancing Role-Play LLM Agents with Automatic Prompt Optimization and Role Prompting, 2025.
https://arxiv.org/abs/2509.00482
[3] Peng L., Shang J. Codifying Character Logic in Role-Playing. NeurIPS, 2025.
https://papers.neurips.cc/paper_files/paper/2025/hash/15294ba2dcfb4521274f7aa1c26f4dd4-Abstract-Conference.html

最终 DOCX/PDF 交付：应以仓库根目录的 报告模板.docx 与 角色扮演大作业.pdf 为准。
