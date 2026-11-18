# 给 Codex 的执行指令：中文角色扮演课程大作业（2026-11-18）

你是本课程作业的本地执行工程师。原则：快速、可复现、控制支出，
严格以仓库题目和 CharacterEval 官方实现为准，不进行新模型训练。
目前由 ChatGPT 创建了一套未实测过真实供应商 API 的初始脚手架，
在本机充分审查和测试后才能运行收费实验。

## 仓库与优先级
仓库：YiBoZhangCS/-，分支 codex/charactereval-course-20261118。
先 git fetch 并切换到该分支。不要改动 main，不要 force push。
先读仓库根目录 README.md、角色扮演大作业.pdf、报告模板.docx，
以及 基于大模型的角色扮演/ 下三个文件和 roleplay/ 下的脚本与文档。
PDF、DOCX 不可凭 README 猜测；请本地提取/渲染核查每一页和报告格式。
若各来源矛盾，以老师最新的作业正式要求为准，列出差异，不要擅自决定提交。

## 目标交付
A. 可校验完整 571 个 ID 的 roleplay/runs/final_v1/submission.json；
B. 对应可复现的 API 推理脚本、参数、失败处理与成本记录；
C. 依照报告模板完成的 DOCX（若老师要求则补 PDF），包含真实实验结果、
论文/开源引用、方法、消融、错误分析、成本统计；
D. 提交前整体验收报告（校验通过、Git commit、价格、OJ 得分/是否已提交）。

## P0：审查并加固脚本（严禁大批量调用）
阅读 roleplay/generate.py、validate_submission.py、test_pipeline.py。
重点检查：
- JSON 数组读取，571 个原始 id，不改变角色、完整 context；
- 本次作业画像对象直接 JSON 序列化而非 Python 形式；
- Chat Completions / Responses endpoint 参数兼容性；
- 断点续跑时同 run-id 的模型、prompt、参数、种子完全一致；
- 响应必须是角色下一句，不要输出说话人标识或多行；
- 429/5xx/timeout 有限次数重试，错误不以空答案掩盖；
- 危险日志绝不包含 API Key、Bearer 头；
- 每次/全局美元总预算，务必限制全部 API 实验 <=100 USD；
- 本地真实代理的计费标准可能与官方标价不同。
先执行 python -m pip install -r roleplay/requirements.txt 以及
python -m unittest discover -s roleplay -p 'test_*.py' -v。
必要时添加测试、修 BUG。当前尚未完成这一步，不要声称已通过。

## P1：验证 API 和价格（安全）
用户在 ~/.bashrc 中通过 export ainet_key 设置 API Key。
读取环境变量即可，禁止 echo/print key；禁止写入 Git 或日志。
截图的 API 地址是 http://ainet-hub.com，不能直接向 HTTP 发送密钥。
请从 AINet Hub 的账号控制台或帮助文档确认真正的 HTTPS API base URL；
无法核实时停止收费请求并明确报告。无需为模型对比修改 Codex 自身供应商：
generate.py 的 --model 直接决定调用哪个模型。
明确列出可用模型的真实 API ID、输入/输出 USD per 1M tokens、
支持的接口模式和可能的中转附加费用。优先核验：
glm-5.3-flash、qwen3.8-max、gpt-6-astra-medium、
DeepSeek-V4.1-Flash-HS 或其供应商实际 ID。
模型菜单中的展示名称不能直接保证真实 API ID 可用。
只做 1~3 条真实 smoke 测试，检查 response、usage、耗时、价格。
遇到 API 400 不无限重试；先定位 URL、模型名和参数。

## P2：低预算模型与提示词对比
先用 roleplay/generate.py --limit 40 --seed 20261118 --strategy structured
对三个性价比合适的模型分别生成同一批样本。
保留 response 原文和耗时、token、价格；记录失败案例。
对优胜模型再用 baseline / structured 做同样 40 条消融。
不要直接假定 GPT 6 比中文专用模型强；比较真实中文角色表现。
条件允许且值得时，可以复用官方 CharacterRM：
https://github.com/morecry/CharacterEval
官方已有 transform_format.py / run_char_rm.py / compute_score.py。
奖励模型 morecry/BaichuanCharRM 权重约 26.5 GB，单张 L40 46GB
可能具备运行条件，但需核实依赖/远端磁盘/下载网络和许可。
这不是硬性前置条件；若下载/适配太费时，可用人工定性判读和
少量 OJ 反馈替代。没有真实打分就不得编造数字。

外部独立复现（2026-11-01）：SociaBench 在其不同测试集规模和流程下，
GLM 5.3 Flash 在角色一致性指标领先 GPT-6 Astra；
这是模型选择的线索，而非课堂 OJ 的可直接引用成绩。
链接：https://sociabench.com/b/charactereval

## P3：完成正式 571 条
选成本与质量平衡最佳的模型及 prompt；生成完整 571 条；
所有 id 一一对应，单行，无空答，JSON 体积合规。
运行 python roleplay/validate_submission.py PATH_TO_submission.json。
输出 model_output 的长度直方图、异常列表、输入输出 token 总计，
实际供应商计费截图/可核实金额及各轮实验汇总。
不要向 OJ 上传伪造的填充答案。不自动使用提交配额；
到最终确认时提醒用户登录 https://ir.illm.ac.cn/task/9#nav-profile
提交文件并回传 Success/Details/Leaderboard 指标（或获得用户明确授权后操作）。
README 说明单次评分至少十分钟；注意截止日、日提交限制和剩余次数。

## P4：报告
先读取老师的 报告模板.docx 与 角色扮演大作业.pdf；以其要求完成
正式排版。以 roleplay/REPORT_SKELETON.md 为工作稿，不直接提交工作稿。
论文研究基础至少包含：
Tu et al., CharacterEval, ACL 2024,
Ruangtanusak et al., Talk Less, Call Right, 2025,
Peng & Shang, Codifying Character Logic in Role-Playing, NeurIPS 2025。
方法必须清楚说明角色条件构造、对话情境判断、提示词场景契约、
输出约束、接口调用、对照/消融、token/费率审计与失败处理。
只有真实数据才进结果表；OJ Average 是12项等权均值；
说明它不同于原论文四维报告和其他平台的榜单。
提供有意义的 2~3 个真实 ID 案例（注意适量引用原文）。
DOCX 用模板中的样式编写，导出 PDF 并目检分页、字体、表格和图片。

## P5：版本管理与交付
将脚本、报告、可公开的实验配置/汇总推送到本分支。
不要提交密钥、含凭证的原始 HTTP 请求、庞大模型权重。
不要修改测试集原样。提交建议写明模型和提示词真实版本。
最后返回：具体 git commit SHA、创建/修改文件列表、
实际每一阶段完成了什么、哪些没完成、API 费用及剩余预算、
test 运行记录、submission 校验结果、OJ 是否提交、报告路径。
不要仅说“已完成”，必须提供可核验依据。
