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

**核心原则：单子与服务同步推进——接到任务的第一件事是登记并置为 In Progress，不是干完（或提交）时补单。**

为什么：Linear 用「进入 In Progress → 进入 Done」的时间戳统计每张单的消耗时间。如果完工或提交时才补单，
`startedAt` 会是空的、`completedAt` 也不等于真实完成时间，工时统计失真。因此**禁止补单**。

标准流程（每个任务都要完整走一遍）：

| 步骤 | 动作 | Linear 状态 |
| --- | --- | --- |
| 1. 接到任务（**动手之前**） | 在 Future Trading 里查是否已有对应 issue；没有就新建：中文标题，描述含「目标 / 计划 / 交付物（仓库内路径）」，labels 带 `codex` | **In Progress** |
| 2. 执行中 | 有偏差、换做法、发现新问题时随时在描述或评论里补充实际做法与原因；跨多次会话保持 In Progress | In Progress |
| 3. 完成 | 写清最终结果、验证证据、交付物路径，然后置 Done | Done |
| 4. 不做了 | 明确写原因后置 Canceled，不要留着不动 | Canceled |

细则：

- **建单时显式传 `state: In Progress`**（`save_issue` 默认落到 Backlog，不指定就会时间戳缺失），
  这样 `startedAt` 才等于真实开工时刻。
- **不要跳步**：不允许「建单即 Done」，也不允许「做完后再补单置 Done」。
  哪怕只是几分钟的小事，也先建 In Progress、做完再置 Done，保留真实时间戳。
- 只有明确标注「**仅登记、暂不处理**」的记录型 issue 才建 Todo/Backlog，并在描述里写明原因；
  一旦开始处理，立刻改回 In Progress。
- 同一件工作跨多轮会话时一直保持 In Progress，收尾再置 Done；不要中途 Canceled 后另建新单。
- 每个 issue 收尾必须包含：最终结果、验证证据（命令或输出要点）、交付物（仓库内文件路径）。
- issue 标题与描述使用中文，描述至少包含三部分：目标、完成内容、交付物（写明仓库内文件路径）。
- **凡由 Codex 创建或处理的 issue，一律打上 `codex` 标签**，便于区分人工与 agent 的工作；创建 issue 时在 labels 里带上它。
- 团队 Firestone（key `FIR`）的关键 ID：
  - teamId `2fae9868-2e43-4bb0-b3ce-ca77829195ad`
  - projectId（Future Trading）`80f281b2-7c27-4998-9e80-7ea04b477b73`
  - stateId：Todo `c6fca1c8-ea50-4775-8b36-c388f78468d9`、In Progress `d7cf0fdf-a533-42c2-b7d2-b9e3076ac262`、In Review `7f13bd76-e850-426c-ac00-d3989e1de54b`、Done `39352f93-f5b1-4f51-bbc8-9a61bda04a48`

## 运维约定（Ansible）

**核心原则：生产机 `builder-mac-mini` 上的安装、配置、同步和服务启停，一律写成 `ops/ansible/` 下的
playbook 来执行，不在生产机上手敲命令。** 开发机是控制机，在 `ops/ansible` 目录下运行；用法见
`ops/ansible/README.md`。

为什么：手工操作没有记录，也无法复核生产机现状；playbook 可以先试跑看差异，事后再跑一遍就能确认机器
与仓库描述一致。

- **先试跑再执行**：会改动机器的 playbook 先加 `--check` 运行（diff 已默认开启），把结果给用户看，
  用户确认后才去掉 `--check` 正式执行。`playbooks/check.yml` 只读，随时可以跑。
- **幂等**：正式执行后再 `--check` 一遍，应为 `changed=0`。只能执行一次的任务（例如首次导入）要在
  任务名里写明，并用 `creates`、`when` 等条件防止重复执行。
- **手工改动要回写**：紧急情况下在生产机上手工处理过的，事后补进对应 role，并用 `--check` 确认
  `changed=0`。
- **不放进 playbook 自动执行**：IB 登录与二次验证、下单、发邮件等对外动作，以及删除数据
  （`--delete`、`rm`、`mongorestore --drop` 之类）。确需执行时单独征得用户同意。
- **写外置卷前先校验卷 UUID**（`group_vars/all.yml` 的 `prod_volume_uuid`），不一致立即失败，
  防止卷没挂载时写进内置盘上的同名目录。
- **密钥不进仓库**：`private/` 的内容不写进 playbook 或变量文件；处理密钥的任务加 `no_log: true`
  和 `diff: false`（运行日志 `~/Library/Logs/systrade/ansible.log` 会记录 diff）。
- 常量（路径、端口、卷 UUID、Gateway 实例）只在 `group_vars/all.yml` 定义；新增操作就新建或扩展
  role，playbook 只负责组合 role。
- 需要 `sudo` 的任务用 `become`，由用户在自己的终端加 `--ask-become-pass` 执行，agent 不保存、不索要密码。
