# todo-cli

面向个人开发者和 AI Coding Agent 的本地项目任务工具。用任务保存背景、验收条件、进展、阻塞原因和验证结果，在不同会话、分支和 worktree 之间继续工作。

使用 Python 标准库实现，无需模型 API、账户或后台服务。Windows 的可选 curses 界面需要 `windows-curses`。

## 安装与快速开始

Python 3.7+：

```bash
python3 -m pip install -e .

cd your-project
todo-cli init
todo-cli add "修复登录过期后无法重新登录" \
  --acceptance "过期后可重新登录" \
  --acceptance "相关回归测试通过" \
  --due tomorrow -p high -t backend

todo-cli next
# 下文 a12b 为示例 ID，请替换成实际输出的 ID 前缀（至少 4 位）
todo-cli start a12b --actor agent-login
todo-cli note a12b "已定位到 token 刷新逻辑" \
  --next-step "补充过期场景的回归测试" --actor agent-login
todo-cli handoff a12b
```

下一次会话读取 `handoff a12b --json`，即可获得任务背景、验收条件、进展、下一步、前置任务及当前 Git 上下文。

```bash
todo-cli review a12b --result "相关测试已运行并通过，待人工确认" --actor agent-login
todo-cli done a12b --result "已人工确认，关联提交 abc123" --actor agent-login
```

工具只记录操作者提供的结果，不会执行测试、切换分支、调用模型或自动修改代码。

## 项目、分支和 worktree

- 不同项目各自拥有任务清单；`projects` 和 `list --all-projects` 汇总已注册项目。
- 同一个 Git 仓库的所有分支、linked worktree 共用任务清单。
- 项目 ID 由 Git common directory 的本机绝对路径生成。分支切换不会改变 ID；移动仓库或重新克隆会得到新 ID，需要导出/导入任务。
- 一个任务可以关联多个分支。`add` 和 `start` 默认关联当前分支；`--branch` 可指定其他分支。关联不会创建或切换分支。
- detached HEAD 使用 `detached:<commit>` 标识，而不是伪造分支名。
- 非 Git 项目先执行 `init`，生成不含任务数据的 `.todo-project` 标记，子目录也能找到同一清单。

```bash
todo-cli context                         # 当前项目、分支、HEAD、工作区状态和数据位置
todo-cli projects
todo-cli list --all-projects
todo-cli list --project <项目ID或唯一名称或目录>
todo-cli list --current-branch
todo-cli link a12b --branch fix/login --url "commit:abc123"
```

数据默认存于 `~/.local/share/todo-cli/projects/<项目ID>/tasks.json`，优先遵循 `XDG_DATA_HOME`。可通过 `TODO_CLI_HOME` 指定独立数据目录。任务不会被提交到各个代码分支，也不会跨机器自动同步。

`--file /path/tasks.json` 可显式使用任意独立 JSON 清单；不会将其注册为项目。`--file` 与 `--project` 互斥。

## 每日工作

```bash
todo-cli list                    # 当前项目未完成任务
todo-cli list --all              # 包括已完成任务
todo-cli list --status done
todo-cli list --owner agent-login
todo-cli list --sort priority -t backend
todo-cli next --limit 3          # 可执行任务：进行中优先，然后逾期、优先级、日期
todo-cli today                   # 今天及之前到期、正在进行的未完成任务
todo-cli inbox                   # 无截止日期、无关联分支的 todo 任务
todo-cli add "以后研究缓存" --no-branch
todo-cli search "token"          # 搜索整个任务上下文，包括进展和结果
todo-cli show a12b
todo-cli postpone a12b +3d       # 修改原任务日期，不复制任务
todo-cli edit a12b --clear-due
todo-cli undo a12b               # 重新打开，清除负责人、完成时间和旧结果
todo-cli delete a12b --yes
```

日期支持 `YYYY-MM-DD`、ISO 日期时间、`today`、`tomorrow`、`+3d`。日期型截止时间在本机当天结束后才算逾期；带时刻的截止时间按该时刻判断。带时区的时间会换算成本机日期展示在每日视图中。

`next` 隐藏主动阻塞、待验收、已完成及前置依赖未完成的任务。它不会自动开始任务或保证任务已满足所有业务前提。

## AI Coding 工作流

### 保存接力信息

任务可以包含：

- 标题与背景描述；
- 多项验收条件；
- 关联分支、Issue、PR、提交或本地文件引用；
- 前置依赖与父子关系；
- 负责人、阻塞原因、下一步；
- 带操作者和时间的进展备注与变更历史；
- 完成或待验收的结果记录。

```bash
todo-cli add "补充登录测试" -d "覆盖 token 过期后重新登录的场景" \
  --acceptance "回归测试通过" --depends-on a12b --parent b34c \
  --link "https://github.com/owner/repo/issues/123"

todo-cli block a12b "缺少测试账号" --actor agent-login
todo-cli start a12b --actor agent-login    # 前提解决后恢复工作
todo-cli history a12b
todo-cli handoff                          # 全项目未完成任务，Markdown 输出
todo-cli handoff a12b --json               # 单任务结构化交接
```

父任务需要等待子任务完成；显式依赖也需要先完成。工具拒绝循环依赖、缺失引用和删除仍被引用的任务。有验收条件的任务必须提供非空结果才能完成，结果也可以在 `review` 时记录。任务验收仍由人或 Agent 负责。

### 认领与并发

每个 Agent 使用独立且稳定的操作者名称：

```bash
export TODO_ACTOR=agent-login
todo-cli start a12b
todo-cli note a12b "完成实现，待验证"
```

`start` 会认领任务；其他操作者不能直接编辑、完成或删除该任务。接管需要明确的 `--force`，历史会记录接管。其他操作者可以追加普通备注；修改“下一步”仍受认领检查约束。

认领是协作约定，不是安全权限系统。使用相同 actor 的多个进程被视为同一操作者。负责人不会自动超时释放；遗留任务可显式接管。

保存采用 OS 文件锁、内容版本检查、临时文件原子替换及上一版本 `.bak` 备份。并发写入冲突返回退出码 4，不会覆盖其他进程的更新。调用者应重新读取、检查状态，再决定是否重试。

### 稳定的机器接口

全局参数 `--json`、`--actor`、`--file`、`--project` 可放在命令前或后。

```bash
todo-cli list --json
todo-cli add --input-json '{"title":"补充登录测试","acceptance":["回归通过"],"request_id":"issue-123-test"}' --json
# 或从 stdin 读取：
printf '%s' '{"title":"检查文档","branches":[],"request_id":"docs-1"}' | todo-cli add --input-json - --json
```

`--input-json` 的字段名使用模型名称：`title`、`description`、`priority`、`tags`、`due_date`、`branches`、`acceptance`、`dependencies`、`parent_id`、`links`、`request_id`。CLI 显式参数覆盖 JSON 中对应字段，未知字段会报错。

相同项目中的相同 `request_id` 和原始输入只创建一次任务，即使任务后来被编辑，重试仍返回原任务。相同键用于不同输入会报错。需要稳定重试时建议显式传入 `branches` 和绝对日期，避免当前分支或相对日期变化导致输入不同。

成功响应：

```json
{"ok": true, "schema_version": 1, "data": {"id": "...", "title": "..."}}
```

失败响应：

```json
{"ok": false, "schema_version": 1, "error": {"code": "conflict", "message": "任务已被其他进程修改，请重新读取后重试"}}
```

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 2 | 参数、输入或工作流校验失败 |
| 3 | 任务或项目不存在 |
| 4 | 并发写入冲突 |
| 5 | 存储损坏或读写失败 |
| 130 | 操作取消 |

JSON 模式的结果及错误均输出到 stdout，不混入彩色输出或交互提示。删除和批量调整日期需要 `--yes`；`select` 仅用于交互终端。帮助信息仍使用标准 argparse 帮助文本。

可把 [Agent 工作流示例](docs/AGENT_WORKFLOW.md) 中的约定加入项目的 Agent 指令中。无需让 Agent 直接编辑任务 JSON。

## 编辑、导入和旧版迁移

```bash
todo-cli edit a12b --title "新标题" --priority high --tags backend auth
todo-cli edit a12b --acceptance "测试通过" "文档更新"
todo-cli edit a12b --dependencies b34c c56d
todo-cli edit a12b --dependencies          # 清空依赖
todo-cli edit a12b --branches             # 清空关联分支
todo-cli edit a12b --parent ""            # 解除父任务

todo-cli export --json > /tmp/tasks-export.json
todo-cli import /tmp/tasks-export.json
```

导入接受旧版原始任务数组及新版 `export --json` 的成功响应。ID、request-id 冲突、无效数据或引用会使整次导入失败；不会部分覆盖已有任务。导出包含历史和上下文，分享前请检查内容。

**从 1.x 升级：** 默认位置不再是当前目录的 `tasks.json`，不会自动扫描或搬动旧文件。可以继续显式访问，或导入当前项目：

```bash
todo-cli --file ./tasks.json list --all
todo-cli init
todo-cli import ./tasks.json
```

`list` 现在默认隐藏已完成任务。`summary --continue --yes` 会将原任务截止日期调整到今天，不再创建副本。`summary --date` 展示截至该日期已创建、当前仍未完成的任务，不是历史状态快照。

原命令简写继续支持：`-a` 添加、`-l` 列表、`-s` 详情、`-e` 编辑、`-d` 删除、`/` 或 `-S` 搜索、`-m` 总结、`-` 交互选择。

存储损坏会明确报错并保留原文件。`.bak` 保存上一次成功写入前的内容；恢复前请先另外保存损坏文件。备份只保留上一版本，不替代长期备份。不要将数据目录放在不能可靠支持文件锁/原子替换的共享文件系统上。

## 开发与范围

```bash
python3 -B -m unittest discover -s tests -v
python3 -B todo.py --help
```

测试覆盖项目隔离、真实 Git worktree、AI 交接流程、认领冲突、依赖循环、日期边界、旧格式迁移、原子导入、多进程写入冲突及写盘失败。

目前提供本地 CLI 与 JSON 接口；不内置 MCP 服务、LLM 调用、跨机器同步或自动执行器。项目身份是本机路径级别，不会把两个独立克隆自动合并。操作历史用于协作追溯，不是防篡改审计日志。

MIT License，详见 [LICENSE](LICENSE)。
