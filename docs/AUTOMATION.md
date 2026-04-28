# Automation

本项目的自动更新策略分两步推进：先做小规模定时烟测，证明采集链路可用；再做完整增量更新和数据发布。

## Current Workflow

[Law Update Smoke](../.github/workflows/law-update-smoke.yml) 每周运行一次，也可以手动触发。默认行为：

- 使用 Python 3.11。
- 安装 `requirements.txt`。
- 运行一个小规模法规采集样本。
- 上传 JSON 和 Excel 结果作为 GitHub Actions artifact。

默认样本：

```bash
python main.py --law "固定资产投资项目节能审查办法" --strategy 5
```

## Why Artifacts Instead Of Commits

自动采集会生成时间戳文件。如果直接提交回仓库，容易制造无意义 commit、数据膨胀和合规审查成本。当前阶段先把输出作为 artifact，方便维护者下载检查。

## Next Automation Milestones

- 增量更新命令：`python main.py update --since YYYY-MM-DD`。
- 数据快照：将稳定输出发布到 GitHub Releases。
- 变更报告：新增、修订、废止、来源变化分别统计。
- 失败告警：当权威数据源接口变化、解析失败率上升时自动开 issue。
- MCP 服务：让智能体可以查询更新、搜索法规、导出台账。

