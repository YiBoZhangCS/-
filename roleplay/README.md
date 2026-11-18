# CharacterEval 课程作业：运行说明（2026-11-18）

本目录实现 571 条中文角色扮演续写和 OJ 文件校验。原始数据保持在 ../基于大模型的角色扮演/。
最后上传：roleplay/runs/<run-id>/submission.json；不得上传 preview.partial.json。

## 环境

Python 3.10+。运行：python -m pip install -r roleplay/requirements.txt

API Key 已在用户的 ~/.bashrc 中定义为 ainet_key，可在当前 shell 加载并检查是否存在：

    source ~/.bashrc
    test -n "$ainet_key" && echo "API key loaded"

绝不可把 Key 放进 Git / 报告 / 运行日志。默认使用服务商确认过的 HTTPS API 地址。
本次用户另外明确授权了指定域名 HTTP，详见下方记录与显式开关；不要自动扩大到其他域名。
截图中的 http://ainet-hub.com 不是可以直接安全使用的 API base URL。
请从服务商控制台确定模型 ID、HTTPS base URL、Chat Completions 或 Responses 支持状况、
以及具体输入/输出价格（USD per million tokens）。

    export AINET_BASE_URL="https://YOUR_VERIFIED_PROVIDER_API_ENDPOINT/v1"

## 先做 smoke / dry run

### 2026-11-18 安全修复与当前状态

离线验收：`python roleplay/verify_offline.py`；全量数据审计：
`python roleplay/audit_data.py`。真实命令输出及版本保存在 `audit/`。
数据包含 571 个唯一 ID、77 个角色、24 部作品，指标展开后有 1005 个评分项；
6367、952、4584、4879 缺少指标映射，但不得漏交。

用户已在本次聊天明确授权使用 HTTP。仅对此域名允许显式的
`--base-url http://ainet-hub.com/v1 --allow-insecure-http`；默认仍拒绝 HTTP。
HTTP 会暴露传输中的密钥，且无法验证服务端身份；本实现不跟随重定向。
已通过 `/v1/models` 确认服务商目录中的候选 ID，`/v1/usage` 账单单位为 USD；
三种模型已完成真实 Chat Completions 测试；没有核实真实费率表。只读复核命令（先在本地加载环境变量）：
`python roleplay/provider_metadata.py --allow-insecure-http`。
不要把展示名、官方价格或其他客户端的历史账单当作本次的真实费率。

SQLite `runs/budget.sqlite3` 是跨实验的费用账本，必须与运行目录一起保留。
每次请求和重试都先持久预留；超时、429、5xx 等未知账单不自动退款。
收到 usage 后才结算，空答/截断答也先记录 token 和费用；缺少 usage 时停止。
`attempts.jsonl` 保存原始文本，`errors.jsonl` 仅保存错误类别、状态码、样本及费用记录 ID。
API 返回 usage 计算出的金额仍是估算，不能替代服务商最终账单，也不能覆盖未披露的附加费。
正式调用前应核实缓存、推理 token、倍率和最低收费，并留出预算余量。

`--billing-mode provider` 可不传费率，每次调用前持久预留美元额度，请求后核对供应商 actual_cost。
`--workers 4` 或 `8` 使用小批次并发，批次计费真实、单条均分为估算；不同模型组可并行，同模型组不可同时运行。
`--fallback-model glm-5.3-flash` 只处理服务商显式拒绝的正常素材，不改写原始上下文；真实模型写入逐条记录。
正式运行使用 `--warm-start final_v1 --run-id final_v2` 明示复用原先成功的 48 条，避免重复收费；
原有 run-id 的配置不作篡改，已接收响应和失败账单均保留。

采样 `--seed` 仅用于固定对照的样本集合，不代表模型生成具有确定性。
同 run-id 锁定 API 地址、完整提示词、源数据、画像、脚本哈希及参数；配置改变须用新 run-id。
同 run-id 进程互斥；串行模式 HTTP 400 不重试，429/5xx/连接失败最多尝试三次；并行批次遇到未知错误保存后停止，不无限重试。

已有 `baseline` 和 `structured` 都使用画像，比较的是提示词策略。
课件第 5 页还要求“不含画像/含画像”对照，因此新增 `no_profile`，
与 `baseline` 使用完全相同的系统提示，仅移除画像内容。
最终应在相同 40 条样本上分别做 `no_profile` vs `baseline` 和
`baseline` vs `structured`，清楚区分两种消融，不能混称。

三模型各 40 条和两项 GPT 消融各 40 条已完成，数据在 `results/`；完整 571 条正在生成。
没有进行 OJ 提交，也没有把定性判断当作 CharacterRM 分数。详见 `audit/STATUS.md`。

以下 MODEL、PRICE 是待替换参数，不表示已核实的服务商价格：

    python roleplay/generate.py \
      --model glm-5.3-flash --run-id glm_smoke \
      --limit 3 --strategy structured \
      --price-in VERIFIED_USD_PER_M_INPUT --price-out VERIFIED_USD_PER_M_OUTPUT \
      --budget 1 --dry-run

确认请求方式和估算后，去掉 --dry-run 才会真实请求。先测试 3 条，再独立运行
40 条模型对照。建议同 seed 的三组：glm-5.3-flash、qwen3.8-max、gpt-6-astra-medium，
均使用 structured；胜者再对比 baseline 与 structured。具体模型 ID 需由代理验证。

脚本默认 Chat Completions 模式，可使用 --api-mode responses 切换 Responses。
有些推理模型要求 --token-param max_completion_tokens 或 --reasoning-effort medium。
这些参数并非所有兼容 API 都支持；遇到 HTTP 400 应检查参数而不是无限重试。

限额示例：每组测试 --budget 5，正式 571 条 --budget 40。
这是本次脚本运行限额，不是定价；总预算请以服务商计费记录为准，留有裕量。

## 正式生成

    python roleplay/generate.py \
      --model YOUR_WINNER_ID --run-id final_v1 \
      --limit 571 --strategy structured \
      --price-in VERIFIED_INPUT_PRICE --price-out VERIFIED_OUTPUT_PRICE \
      --budget 40

    python roleplay/validate_submission.py roleplay/runs/final_v1/submission.json

运行日志支持同 run-id、同配置断点续跑；保存 output/token/费用估计/时延，
不记录 API Key。脚本仅在 571 条全覆盖时导出 submission.json 并做严格校验。
成本估计依赖服务商正确披露价格和 token usage，不能担保隐藏费用。

## 研究复现与报告

官方 CharacterEval: https://github.com/morecry/CharacterEval
ACL 2024 论文: https://aclanthology.org/2024.acl-long.638/
官方 CharacterRM：morecry/BaichuanCharRM（约 26.5 GB，需独立 GPU 环境）。

官方流程可以重用 transform_format.py、run_char_rm.py、compute_score.py：
先展开每条样本对应指标，再用 CharacterRM 评分，最后计算维度均值。
本课程 OJ 返回 12 个指标等权 Average；论文原始榜单不是同一总分定义。
课堂 571 条子集也不同于外部 4,531 个可评分样本的完整复现结果。

每个实验需保存：实际模型 ID、提示词版本、设置、输入输出 token、费用估算、
输出长度、异常样例、以及真实 OJ 指标。严禁虚构实验成绩。
报告草稿结构在 REPORT_SKELETON.md。Codex 应使用仓库根目录的
角色扮演大作业.pdf 和 报告模板.docx 进一步核实报告格式。

## CCSwitch / Codex

CCSwitch 调整 ~/.codex/config.toml 是更换 Codex 本身用的推理模型。
它与 generate.py 的 --model 所指定的候选角色扮演模型完全独立。
切换 Codex 供应商后重启 Codex 会话，确保新配置生效；
无需为了测试 GLM/Qwen/DeepSeek 而不断重启 Codex。
