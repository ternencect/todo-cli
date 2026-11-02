# 安装与升级

需要 Python 3.7+。核心 CLI 使用标准库；安装打包由 setuptools 提供。

```bash
git clone https://github.com/ternencect/todo-cli.git
cd todo-cli
python3 -m pip install -e .
todo-cli --help
```

也可不安装直接运行：

```bash
python3 /absolute/path/to/todo-cli/todo.py --help
```

在需要管理的项目目录执行 `todo-cli init`。Git 项目中的分支和 linked worktree 共享任务数据；非 Git 项目通过 `.todo-project` 标记定位。

Windows 的交互选择器可选安装 `python -m pip install windows-curses`；未安装时使用数字菜单。Agent 使用 JSON 命令，无需 curses。

## 升级旧任务

新版默认数据位于用户数据目录。旧版当前目录中的 `tasks.json` 不会被自动迁移或删除：

```bash
todo-cli --file ./tasks.json list --all
todo-cli init
todo-cli import ./tasks.json
```

先确认项目正确，再导入。重复 ID 会拒绝整次导入。默认列表隐藏已完成任务，使用 `--all` 查看。

可通过 `TODO_CLI_HOME` 自定义数据目录。完整工作流、存储语义和机器接口见 [README](README.md)。

卸载程序：`python3 -m pip uninstall todo-cli`。卸载不会主动删除任务数据。
