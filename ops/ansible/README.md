# ops/ansible

在开发机（控制机）上管理生产机 `builder-mac-mini` 的 Ansible 项目。使用规则见仓库根目录
`AGENTS.md` 的「运维约定（Ansible）」，迁移步骤见 `docs/production_migration_cn.md`。

## 用法

```bash
cd ~/dev/pysystemtrade/ops/ansible
ansible-playbook playbooks/check.yml              # 只读体检，随时可跑
ansible-playbook playbooks/gateway.yml --check    # 试跑：列出会改什么（diff 默认开启）
ansible-playbook playbooks/gateway.yml            # 用户确认试跑结果后再执行
```

带 `become` 的任务（例如 `pmset`）要加 `--ask-become-pass`，由用户在自己的终端里输入密码。

## 内容

| playbook | 作用 | 机器 |
| --- | --- | --- |
| `check.yml` | 只读体检：外置卷 UUID、磁盘余量、Gateway 安装、4001/4002 端口、进程、软件版本、MongoDB dbPath、`autorestart` | prod |
| `base.yml` | Homebrew 基础软件（GNU rsync），不自动更新、不连带升级 | dev、prod |
| `gateway.yml` | 两个 IB Gateway 实例：从开发机同步安装目录和设置目录、实盘实例的 `jtsConfigDir`、签名校验 | prod |

- 常量（路径、端口、卷 UUID、Gateway 实例）只在 `group_vars/all.yml` 定义；playbook 只组合 `roles/` 里的 role。
- 运行日志：开发机 `~/Library/Logs/systrade/ansible.log`。

## 依赖

- 开发机：`brew install ansible`（ansible-core 2.21，自带 `ansible.posix`、`community.general`）。
- 两台机器都有 GNU rsync `/opt/homebrew/bin/rsync`；生产机用 `~/miniconda3/bin/python3` 运行 Ansible 模块。

## 已知的坑

- `synchronize` 把 `rsync_opts` 拼成一行命令再拆分，带空格的参数要先 `map('quote')`。
- `synchronize` 读 `ansible_rsync_path` 时不展开模板，只能写字面路径。
- 任务名里不要引用 `item`：任务名在循环之前展开，会报 undefined。
- 生产机非交互 ssh 的 `PATH` 只有 `/usr/bin:/bin:/usr/sbin:/sbin`，Homebrew 的程序要写全路径。

## 待做（阶段二）

目录与软链接（先校验卷 UUID）、`~/.pysystemtrade.env`、MongoDB（dbPath 改到外置卷）、Python 环境、
代码发布、数据同步、launchd 日更。每做一项，把迁移文档里对应的手工命令换成 playbook。
