# 生产迁移方案：迁到 builder-mac-mini

> 状态：待确认，尚未执行。对应 Linear FIR-251。
>
> 本文合并并替代 2026-11-01 的《生产部署与迁移设计》《生产迁移检查清单》《首次部署和数据迁移
> Runbook》和 superpowers 实施计划，原文件备份在 `private/archive/2026-11-01_migration_docs/`。
> 按阶段执行：每个阶段结束先展示证据，用户确认后才进入下一阶段。

## 1. 目标与做法

- 生产（IB 日更、派生价格、策略与报表）从开发机迁到常开的 `builder-mac-mini`，开发机只做代码和研究。
  直接原因：开发机 08:00 经常没开机，日更跟着落空。
- 分两步：
  1. **本文**：把现有流程原样搬到生产机，发布靠手动 `git checkout` 到发布 tag；
  2. 生产日更稳定运行一段时间后，再决定要不要做自动发布（第 9 节）。
- 不在本文范围：修改策略或交易口径；开启下单。迁移后仍是纸面账户，订单生成与执行是否开启另行确认。
- 生产机上的操作逐步改为 `ops/ansible/` 的 playbook（规则见 `AGENTS.md`「运维约定（Ansible）」）。
  已有 `check.yml`（只读体检）、`base.yml`、`gateway.yml`；其余步骤暂按本文命令执行，转成 playbook 后在原处注明。

## 2. 已核实的环境（2026-11-01）

| 项目 | 开发机 | 生产机 `builder-mac-mini` |
| --- | --- | --- |
| 系统 | macOS 26.5.2 | macOS 26.6.2，Apple M4（arm64） |
| 数据卷 | `~/data` → `/Volumes/data/systrade` | `/Volumes/cv`，APFS，UUID `517D6A79-28DD-47FA-8C58-D4120188387A`，477 GiB，可用 413 GiB，**未加密** |
| Python | conda `invest`：3.13.2 / pandas 2.2.3 / numpy 2.2.2，pysystemtrade 为可编辑安装 | conda `mini-invest`：3.12.13 / pandas 2.1.3 / numpy 1.26.4，pysystemtrade 1.8.2 **装在 site-packages 里** |
| MongoDB | 8.0.6，dbPath 在外置卷 | 8.3.11，服务未运行 |
| pymongo / pyarrow / mongosh | 3.11.3 / 19.0.1 / 有 | 同左 |
| rsync | 系统自带 openrsync，不支持 `--info=progress2`；已装 GNU rsync 3.5.1（`/opt/homebrew/bin/rsync`） | 同左 |
| rg | 未安装 | 未安装 |
| IB Gateway | 两个实例（`sysproduction/linux/scripts/start_ib_gateways`，FIR-170） | **未安装** |
| 开机与会话 | — | 不自动登录，`autorestart 0`，不睡眠 |

2026-11-02 用 `check.yml` 复核：两个 Gateway 实例已装好（未登录，4001 / 4002 未监听），`autorestart` 已为 1；
MongoDB 已经由 `brew services` 开机自启，但用的是默认配置，dbPath 在内置盘 `/opt/homebrew/var/mongodb`（空库）。

`/Volumes/cv` 未加密，私密配置放在上面要接受这个风险；以后可以换成加密卷。

## 3. 目标布局与数据所有权

生产机上的一切都放在外置卷：

```text
/Volumes/cv/systrade/
├── code/      # git clone，检出发布 tag；private/ 在其中（除 __init__.py 外被 .gitignore 忽略，checkout 不影响）
├── data/      # parquet、mongodb、roll_calendars_csv、barchart、norgate_export(_usd)、log、backup、echos
├── venv/      # 生产 Python 环境
└── state/     # 发布记录、迁移证据
```

两个稳定软链接，让脚本和 `private_config.yaml` 里的 `~/dev/pysystemtrade`、`~/data` 不用改：

```text
~/dev/pysystemtrade -> /Volumes/cv/systrade/code
~/data              -> /Volumes/cv/systrade/data
```

只在 `/Volumes/cv` 已挂载且 UUID 正确时创建；脚本发现卷不对就退出，不在内置盘上建同名目录。

| 数据 | 首次迁移 | 迁移后谁写 |
| --- | --- | --- |
| `data/parquet` | rsync，按 SHA-256 清单逐文件核对 | 只有生产机 |
| MongoDB | `mongodump` → `mongorestore`，不拷数据目录 | 只有生产机 |
| 换月日历 | 开发机工作区的 `roll_calendars_csv` 复制到 `data/roll_calendars_csv`（前置改造 P2） | 只有生产机 |
| `barchart`、`norgate_export`、`norgate_export_usd` 原始文件 | rsync | 开发机下载，单向推到生产机；导入价格库在生产机做 |
| `private/*.yaml` | rsync | 开发机修改，手动同步到生产机 |
| `private/backtests/`、`*.pck` 等运行状态 | 首次复制 | 只有生产机 |
| 日志、`backup/` 里的旧快照 | 不迁移 | 生产机新建 |

研究用数据：开发机回测需要新数据时，从生产机只读同步到开发机的单独目录，不回写生产。

## 4. 前置改造（迁移前在开发机完成并提交）

| 编号 | 问题（已核实） | 改法 |
| --- | --- | --- |
| P1 路径写死 | `run_daily_data_update` 第 37、39 行写死 `envs/invest` 与 `/Volumes/data/systrade`；`sysinit/henrik` 下另有 6 个工具写死 `/Volumes/data/systrade` | **已完成（2026-11-02）**：日更脚本开头显式 `source ~/.pysystemtrade.env`（launchd 不加载 shell 配置），Python 与代码目录取 `PYSYS_PYTHON`、`PYSYS_CODE`，数据根目录默认 `~/data`（可用 `PYSYS_DATA_ROOT` 覆盖）；6 个工具的默认路径改到 `~/data` 下 |
| P2 运行数据写进代码目录 | 框架默认的日历目录和 18 个脚本都指向代码目录里的 `data/futures/roll_calendars_csv`，失滚重建与 Barchart 导入会写入；`email.log` 因为没设 `email_store_filename` 写在当前目录，而日更脚本会先 `cd` 到代码目录；`pysystemtrade.log` 只在不带 `--file` 启动日志服务时写在当前目录（`syslogging/server.py:82`） | **已完成（2026-11-02）**：日历目录统一由 `sysdata/csv/csv_roll_calendars.py` 的 `roll_calendar_directory()` 决定，环境变量 `PYSYS_ROLL_CALENDARS_DIR` 优先，生产在 `~/.pysystemtrade.env` 里指向 `~/data/roll_calendars_csv`，开发机不设（日历仍在仓库里、受 git 管理）；用环境变量而不是 `private_config.yaml`，是因为后者会从开发机同步过去覆盖掉。`private_config.yaml` 已设 `email_store_filename: /Users/henrik/data/log/email.log`。调用日历重建的 4 处子进程改用当前解释器和绝对路径。日志服务如需启用，用 `--file ~/data/log/pysystemtrade.log` |
| P3 加载到旧代码 | 日更里 `sysinit/henrik` 的 5 个脚本按文件路径启动、不改 `sys.path`，生产机 `mini-invest` 里的 pysystemtrade 1.8.2 会被优先加载 | 生产环境用 `pip install -e ~/dev/pysystemtrade`；冒烟测试不设 `PYTHONPATH`，检查实际加载路径 |
| P4 发布前测试 | 完整 `pytest` 有 8 个旧失败：6 个 doctest 因 numpy 2 改了标量显示（`np.int64(2)`），1 个交易时间测试读到了本机 `private/` 的自定义交易时间，1 个测试断言的是旧提示文字 | **已完成（2026-11-02）**：根目录 `conftest.py` 在测试时用 numpy 1.x 的显示方式；交易时间测试在 `private/` 有自定义文件时跳过并写明原因；断言改为当前的提示文字。完整 `pytest` 0 失败（149 通过） |
| P5 命令行工具 | openrsync 不支持 `--info=progress2`；两台机器都没有 `rg` | **已完成（2026-11-02）**：两台机器都装了 GNU rsync 3.5.1（关闭自动更新与连带升级；开发机的 `xz` 因依赖从 5.8.2 升到 5.8.4）。阶段 3 改用 shell 函数 `R()` 调用并加 `--rsync-path`，实测 dry-run、`--info=progress2` 复制与清单校验通过；命令只用 `grep` / `pgrep` |
| P6 宿主环境 | 生产机未装 IB Gateway；不自动登录，断电后不自启 | **部分完成（2026-11-02）**：两个实例已按 `start_ib_gateways` 的约定装好，由 `ops/ansible/playbooks/gateway.yml` 管理（`--check` 为 0 改动，两个实例签名校验通过）；`autorestart` 已为 1。待定：是否开启自动登录、是否用 IBC 由用户决定；07:30 检查 4001 / 4002，未监听就发邮件 |
| P7 未提交的工作 | 自 10-09 起有 62 个修改、135 个新增的换月日历和 `rollconfig.csv` 未提交（11-01 统计）；其中 CAC、NIKKEI-SGX、NIKKEI-JPY、CRUDE_ICE 的日历被 10-21 的失滚重建改写，CAC、NIKKEI-SGX 的历史被截到 2000 年 | **进行中（2026-11-02）**：P1–P4 已推送到 origin/develop（`09befb041`）；Codex 的 Barchart 批次（日历、`rollconfig.csv`、合约映射脚本）待导入完成后由 Codex 按 FIR-224~250 提交。失滚重建已改为默认只在日历末尾追加（`--full` 才整体替换，接缝接不上就不写入）。CAC 已恢复完整历史并接上 1 行新换月；NIKKEI-SGX、NIKKEI-JPY、CRUDE_ICE 已恢复为提交版本，但它们的近期换月与按成交量重建的结果不一致（两个 NIKKEI 是按月还是按季度换月，CRUDE_ICE 末尾有异常行），需要对照价格库复核；被改写的版本保存在 `private/archive/2026-11-02_rewritten_calendars/` |

P1–P4 都要改代码：单独开工单，在开发机测试通过后合入 `origin/develop`，再打首个发布 tag。

## 5. 发布方式（手动）

开发机：

```bash
git switch develop && git pull --ff-only
pytest                                  # 必须 0 失败（P4）
tag=prod-$(date +%Y%m%d)-1              # 同一天再发布时递增
git tag -a "$tag" -m "Production release $tag"
git push origin "$tag"                  # 只推这个 tag
```

生产机（先确认没有生产进程在运行）：

```bash
cd ~/dev/pysystemtrade
git fetch --tags origin
git checkout --detach "$tag"
git status --short                      # 必须为空：P2 之后代码目录不再写运行数据
echo "$(date '+%F %T') $tag" >> /Volumes/cv/systrade/state/releases.log
```

回退：`git checkout --detach <上一个 tag>`。tag 推送后不移动、不删除，需要修正就发新序号。

## 6. 迁移步骤

### 阶段 1：冻结与基线（开发机）

1. 停写：`launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.henrik.systrade.update.plist`；
   确认 Codex 的 Barchart 批次导入已经完成或暂停；`pgrep -fl 'sysproduction|sysinit|run_daily_data_update'` 没有输出。
2. 退出开发机上的两个 IB Gateway：同一个 IB 用户名同时只能有一个会话。
3. 生成基线，后面所有比对只以这一份为准：

```bash
base=~/data/backup/pre-migration-$(date +%Y%m%d)
mkdir -p "$base" && cd "$base"
(cd ~/data/parquet && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256) > parquet.sha256
mongodump --uri=mongodb://127.0.0.1:27017 --gzip --archive=mongo.archive
shasum -a 256 mongo.archive > mongo.archive.sha256
cp -Rp ~/dev/pysystemtrade/data/futures/roll_calendars_csv roll_calendars_csv   # 复制前先复核 P7 里 3 个日历的近期换月
mongosh --quiet --eval 'db.adminCommand({listDatabases: 1}).databases.forEach(d => {
  const x = db.getSiblingDB(d.name);
  x.getCollectionNames().forEach(c => print(d.name, c, x[c].countDocuments({})));
})' > mongo_counts.txt
```

4. 另记 Parquet 文件数与总大小、三类原始下载的文件数。

门禁：没有写进程；基线文件齐全；用户确认。

### 阶段 2：生产机准备（不碰业务数据）

1. 卷与目录：

```bash
diskutil info /Volumes/cv | grep 517D6A79-28DD-47FA-8C58-D4120188387A
mkdir -p /Volumes/cv/systrade/data/{mongodb,log} /Volumes/cv/systrade/state/migration
```

2. 工具与宿主（已完成）：在开发机的 `ops/ansible` 下运行 `ansible-playbook playbooks/base.yml playbooks/gateway.yml`，
   先 `--check`。`autorestart` 已为 1。两个 IB Gateway 按 `start_ib_gateways` 的约定：
   - `~/Applications/IB Gateway 10.50/`：纸面，设置目录 `~/Jts`，API 端口 4002；
   - `~/Applications/IB Gateway 10.50 Live/`：实盘，设置目录 `~/Jts-live`，API 端口 4001，
     `ibgateway.vmoptions` 加 `-DjtsConfigDir=/Users/henrik/Jts-live`；
   - 两个实例的 API 都只信任 127.0.0.1。
3. 代码与软链接：

```bash
git clone https://github.com/houmingyuan/pysystemtrade.git /Volumes/cv/systrade/code
cd /Volumes/cv/systrade/code && git checkout --detach <首个发布 tag>
mkdir -p ~/dev && ln -s /Volumes/cv/systrade/code ~/dev/pysystemtrade && ln -s /Volumes/cv/systrade/data ~/data
```

4. Python 环境：与开发机同版本，不克隆 `mini-invest`。

```bash
# 开发机：导出后删掉 pysystemtrade 那一行，再拷到生产机
conda env export -n invest --no-builds > invest.yml
# 生产机
conda env create -p /Volumes/cv/systrade/venv -f invest.yml
/Volumes/cv/systrade/venv/bin/pip install -e ~/dev/pysystemtrade
```

   再写生产机的 `~/.pysystemtrade.env`：从开发机复制一份，把 `PYSYS_PYTHON` 和 `PATH` 里的
   `$HOME/miniconda3/envs/invest/bin` 改成 `/Volumes/cv/systrade/venv/bin`，再加一行
   `export PYSYS_ROLL_CALENDARS_DIR="$HOME/data/roll_calendars_csv"`。日更脚本从这个文件读取
   Python 与代码目录（P1），读写换月日历的脚本从这里取日历目录（P2）。

5. 冒烟测试：不设 `PYTHONPATH`，也不在代码目录下运行。

```bash
cd ~/data && /Volumes/cv/systrade/venv/bin/python -c "
import os, sysproduction
path = os.path.realpath(sysproduction.__file__)
print(path)
assert path.startswith('/Volumes/cv/systrade/code/')"
```

6. MongoDB：照开发机的做法用 `brew services`。它已经用默认配置在运行，先 `brew services stop mongodb-community`，
   再把 `/opt/homebrew/etc/mongod.conf` 的 `dbPath` 改为
   `/Volumes/cv/systrade/data/mongodb`、日志改为 `/Volumes/cv/systrade/data/log/mongod.log`，再
   `brew services start mongodb-community`。卷未挂载时 mongod 找不到 dbPath 会启动失败；brew 生成的启动项是
   `KeepAlive false`，失败后**不会**自动重试，所以阶段 5 的日更入口要在卷就绪后检查并拉起 mongod。

门禁：卷 UUID 正确；两个软链接只指向外置卷；冒烟测试通过；MongoDB 在线；`git status --short` 为空。

### 阶段 3：数据迁移

开发机执行（`base` 同阶段 1）：

```bash
R() { /opt/homebrew/bin/rsync --rsync-path=/opt/homebrew/bin/rsync "$@"; }   # 用函数：zsh 不拆分变量里的空格
P=builder-mac-mini:/Volumes/cv/systrade
R -an --checksum --itemize-changes ~/data/parquet/ $P/data/parquet/ | head    # 先 dry-run
R -a --checksum --partial --info=progress2 ~/data/parquet/ $P/data/parquet/
for d in barchart norgate_export norgate_export_usd; do R -a --partial ~/data/$d/ $P/data/$d/; done
R -a "$base/roll_calendars_csv/" $P/data/roll_calendars_csv/
R -a --exclude archive/ --exclude __pycache__/ --exclude .DS_Store \
    ~/dev/pysystemtrade/private/ $P/code/private/
R -a "$base"/{mongo.archive,mongo.archive.sha256,parquet.sha256,mongo_counts.txt} $P/state/migration/
```

生产机执行：

```bash
cd /Volumes/cv/systrade/state/migration
shasum -a 256 -c mongo.archive.sha256
(cd ~/data/parquet && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256) | cmp - parquet.sha256
chmod 700 ~/dev/pysystemtrade/private && find ~/dev/pysystemtrade/private -type f -exec chmod 600 {} +
mongorestore --uri=mongodb://127.0.0.1:27017 --gzip --archive=mongo.archive
```

恢复后，用 `python -m sysproduction.interactive_controls`（在 `~/data` 下运行）清理开发机带过来的运行状态：
菜单 30 清除已占用的 IB client id，菜单 44 把已经不在运行的进程标记为关闭。最后按阶段 1 的
`mongo_counts.txt` 核对各 collection 文档数。

门禁：Parquet 清单一致；archive 校验一致；restore 无错误；各 collection 文档数一致；全程未用 `--delete`。

### 阶段 4：生产验证（只读）

1. 走生产代码的数据层读库（同时验证环境、MongoDB 和 Parquet），末端日期应与开发机基线一致：

```bash
cd ~/data && /Volumes/cv/systrade/venv/bin/python -c "
from sysproduction.data.prices import diagPrices
print(diagPrices().get_adjusted_prices('SOFR').index[-1])"
```

2. IB：确认开发机的 Gateway 已退出；生产机人工登录两个实例，`start_ib_gateways --status` 显示 4001、4002
   都在监听；`private_config.yaml` 仍是纸面账户（`ib_port: 4002`，`broker_account` 为纸面账号）。

门禁：读库正常；Gateway 已登录；账户配置未变；用户确认切换。

### 阶段 5：切换

1. 生产机安装日更 launchd：plist 沿用开发机的 `com.henrik.systrade.update.plist`（每天 08:00，
   `LimitLoadToSessionType: Aqua`），入口改为内置盘上的 `~/Library/Application Support/systrade/run-update.sh`：
   先检查卷 UUID（未挂载时最多等 30 分钟），再确认 mongod 在运行（没有就
   `launchctl kickstart gui/$(id -u)/sh.brew.mongodb-community`），最后
   `exec /bin/zsh ~/dev/pysystemtrade/sysproduction/linux/scripts/run_daily_data_update`。
   入口放在内置盘，卷没挂载时也能留下失败记录。
2. 手动跑一次日更。验收口径是**不比源端基线差**：尖峰被拒的合约数、multiple prices 落后的品种数都不增加。
   不要用 `check_daily_data_update.py --max-spikes 0` 这样的绝对门槛：源端 10-22 的日志本身就有
   56 个合约尖峰被拒、35 个品种落后。
3. 次日 08:00 观察自动运行。

门禁：开发机日更已卸载；生产日更只写外置卷；首轮结果不劣于基线。

### 阶段 6：收尾

把发布 tag 与 commit、卷信息、两项校验结果、各类计数、首轮日更摘要，以及一次回退演练
（checkout 上一个 tag 再切回）的结果写回 FIR-251。

## 7. 中止与回退

- 任一门禁不通过就停，不进入下一阶段。
- 切换前中止：开发机数据没被改动，`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.henrik.systrade.update.plist`
  恢复开发机日更即可。
- 切换后回退：代码 checkout 上一个 tag；数据以阶段 1 的基线为准；MongoDB 用基线 archive 重建（先经用户确认）。
- 任何时候都不删除已复制的数据，不使用 `--delete`。

## 8. 迁移后的日常

- 每天 08:00 前用屏幕共享登录两个 Gateway；07:30 的端口检查失败会发邮件（P6）。
- 发布按第 5 节手动操作。
- 新下载的原始文件：开发机 `rsync`（不带 `--delete`）推到生产机 `data/`，导入价格库在生产机执行。
- 研究用数据：从生产机只读同步到开发机的单独目录。

## 9. 以后再定：自动发布

生产日更稳定运行一段时间（例如连续 4 周），而且发布频繁到手动操作不方便时，再做 tag 轮询、原子切换和
自动回滚。2026-11-01 的原设计（bare 仓库、每个 tag 一个 worktree、120 秒轮询）可作参考，见
`private/archive/2026-11-01_migration_docs/`。那套设计要求代码目录不写运行数据，所以 P2 是前提；
另外每个 tag 一个 worktree 时 `private/` 需要改用 `PYSYS_PRIVATE_CONFIG_DIR` 等方式放到代码目录之外。
