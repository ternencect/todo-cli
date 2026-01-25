# todo-cli

一个功能完整的命令行待办事项管理工具，使用 Python 标准库实现，零依赖。

## 功能特性

- **基本功能**：添加、删除、编辑、查看任务
- **优先级管理**：支持高/中/低优先级
- **状态跟踪**：待办、进行中、已完成
- **标签分类**：支持多标签管理
- **每日总结**：将未完成任务延续到次日并打标签
- **智能提醒**：运行时显示即将到期的任务，支持日期排序
- **搜索过滤**：按关键词、标签、状态、优先级搜索和过滤
- **交互式选择**：TUI 界面辅助选择任务
- **彩色输出**：直观的终端彩色显示

## 安装

```bash
# 克隆仓库
git clone https://github.com/ternencect/todo-cli.git
cd todo-cli

# 安装
python setup.py install
```

## 使用方法

### 添加任务

```bash
# 基本用法
todo-cli add "完成项目文档"

# 添加带描述的任务
todo-cli add "学习 Python" -d "完成基础教程"

# 设置优先级
todo-cli add "紧急任务" -p high

# 添加标签
todo-cli add "锻炼身体" -t health

# 设置截止日期
todo-cli add "提交报告" --due 2026-01-26

# 组合使用
todo-cli add "完成项目" -d "编写文档和代码" -p high -t work project --due 2026-01-26
```

### 查看任务

```bash
# 列出所有任务
todo-cli list

# 按状态过滤
todo-cli list --status todo
todo-cli list --status in_progress
todo-cli list --status done

# 按优先级过滤
todo-cli list --priority high

# 按标签过滤
todo-cli list -t work

# 排序
todo-cli list --sort created    # 按创建时间
todo-cli list --sort due        # 按截止日期
todo-cli list --sort priority   # 按优先级
todo-cli list --sort status     # 按状态
```

### 显示任务详情

```bash
# 使用完整 ID 或前几位
todo-cli show 709386d2
```

### 编辑任务

```bash
# 修改状态
todo-cli edit 709386d2 --status in_progress
todo-cli edit 709386d2 --status done

# 修改优先级
todo-cli edit 709386d2 --priority high

# 修改标签
todo-cli edit 709386d2 -t new1 new2

# 修改截止日期
todo-cli edit 709386d2 --due 2026-01-30

# 组合修改
todo-cli edit 709386d2 --title "新标题" --status done --priority high
```

### 删除任务

```bash
todo-cli delete 709386d2
```

### 搜索任务

```bash
# 在标题、描述、标签中搜索
todo-cli search "项目"
todo-cli search "Python"
```

### 每日总结

```bash
# 查看今日未完成任务
todo-cli summary

# 查看指定日期的未完成任务
todo-cli summary --date 2026-01-25

# 将未完成任务延续到今天
todo-cli summary --continue
```

### 交互式选择

```bash
# TUI 界面选择任务
todo-cli select

# 按状态过滤后选择
todo-cli select --status todo
```

## 数据存储

任务数据默认存储在当前工作目录的 `tasks.json` 文件中。

## 优先级说明

- **高 (high)**: 红色 `!!!`
- **中 (medium)**: 黄色 `!!`
- **低 (low)**: 绿色 `!`

## 状态说明

- **待办 (todo)**: `[ ]`
- **进行中 (in_progress)**: `[~]`
- **已完成 (done)**: `[x]`

## 系统要求

- Python 3.7+
- 零依赖（仅使用 Python 标准库）

## 注意事项

- **Windows 用户**：TUI 功能需要安装 `windows-curses` 包
  ```bash
  pip install windows-curses
  ```
- **任务 ID**：可以使用完整 UUID 或前 4-8 位进行操作
- **数据安全**：编辑操作会自动保存，建议定期备份 `tasks.json`

## 开发

```bash
# 运行测试
python todo.py --help

# 添加测试任务
python todo.py add "测试任务" -p high -t test
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

[MIT License](LICENSE)

## 链接

- GitHub: https://github.com/ternencect/todo-cli
- 问题反馈: https://github.com/ternencect/todo-cli/issues
