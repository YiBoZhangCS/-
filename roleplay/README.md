# CharacterEval 课程作业：运行说明（2026-11-18）

本目录实现 571 条中文角色扮演续写和 OJ 文件校验。原始数据保持在 ../基于大模型的角色扮演/。
最后上传：roleplay/runs/<run-id>/submission.json；不得上传 preview.partial.json。

## 环境

Python 3.10+。运行：python -m pip install -r roleplay/requirements.txt

API Key 已在用户的 ~/.bashrc 中定义为 ainet_key，可在当前 shell 加载并检查是否存在：

    source ~/.bashrc
    test -n "$ainet_key" && echo "API key loaded"

绝不可把 Key 放进 Git / 报告 / 运行日志。只使用服务商确认过的 HTTPS API 地址！
截图中的 http://ainet-hub.com 不是可以直接安全使用的 API base URL。
请从服务商控制台确定模型 ID、HTTPS base URL、Chat Completions 或 Responses 支持状况、
以及具体输入/输出价格（USD per million tokens）。

    export AINET_BASE_URL="https://YOUR_VERIFIED_PROVIDER_API_ENDPOINT/v1"

## 先做 smoke / dry run

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
