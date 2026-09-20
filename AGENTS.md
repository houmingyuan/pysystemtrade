# AGENTS.md

## Linear 项目关联

本仓库（Codex 项目 `pysystemtrade`，路径 `/Users/henrik/dev/pysystemtrade`）关联到 Linear 项目 **Future Trading**：

| 项 | 值 |
| --- | --- |
| Linear 工作区 | firestone（https://linear.app/firestonecn） |
| 项目名称 | Future Trading |
| 项目 ID | `80f281b2-7c27-4998-9e80-7ea04b477b73` |
| 项目链接 | https://linear.app/firestonecn/project/future-trading-af102910a801 |

### 使用约定

- 需要读写 issue、项目、里程碑时，使用名为 `linear` 的 MCP 服务器（`https://mcp.linear.app/mcp`）。
- 未指明项目时，默认在 **Future Trading** 项目下操作。
- 同一工作区下还有 `alpha-invest`（`6cf31384-a6ff-4b8e-9a75-08f9dfe3397f`）与 `高尔夫辅助训练系统`（`464462ab-8a32-44b6-bf28-febc23eafe71`）两个项目，仅在用户明确指定时使用。

### 工作登记约定

- 在本仓库执行的每项工作都要在 Linear 登记：开工前先查 Future Trading 项目里是否已有对应 issue，没有则新建，避免重复登记。
- **开工时先建 issue 并置为 In Progress**，把计划做的事写进描述；工作过程中如有偏差，说明实际做法；**完成后把状态更新为 Done**，并在收尾时说明最终结果。
- 不要把 issue 建成即 Done——除非任务在登记时确实已经完成，且没有可拆分的过程工作。
- issue 标题与描述使用中文，描述至少包含三部分：目标、完成内容、交付物（写明仓库内文件路径）。
- **凡由 Codex 创建或处理的 issue，一律打上 `codex` 标签**，便于区分人工与 agent 的工作；创建 issue 时在 labels 里带上它。
- 团队 Firestone（key `FIR`）的关键 ID：
  - teamId `2fae9868-2e43-4bb0-b3ce-ca77829195ad`
  - projectId（Future Trading）`80f281b2-7c27-4998-9e80-7ea04b477b73`
  - stateId：Todo `c6fca1c8-ea50-4775-8b36-c388f78468d9`、In Progress `d7cf0fdf-a533-42c2-b7d2-b9e3076ac262`、In Review `7f13bd76-e850-426c-ac00-d3989e1de54b`、Done `39352f93-f5b1-4f51-bbc8-9a61bda04a48`
