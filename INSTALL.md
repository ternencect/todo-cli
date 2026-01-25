# todo-cli 安装指南

## 方式 1: 从分发包安装（推荐）

下载 `dist/` 目录中的文件，然后：

**使用 wheel 文件（推荐）**：
```bash
pip install todo_cli-1.0.0-py3-none-any.whl
```

**或使用源码压缩包**：
```bash
pip install todo_cli-1.0.0.tar.gz
```

## 方式 2: 从 GitHub 仓库安装

**从 GitHub 克隆并安装**：
```bash
git clone https://github.com/your-username/todo-cli.git
cd todo-cli
pip install -e .
```

**或直接从 GitHub 安装**：
```bash
pip install git+https://github.com/your-username/todo-cli.git
```

## 方式 3: 开发模式安装

如果你想要修改代码：

```bash
git clone https://github.com/your-username/todo-cli.git
cd todo-cli
pip install -e .
```

使用 `-e` 参数安装后，对代码的修改会立即生效，无需重新安装。

## 系统要求

- Python 3.7 或更高版本
- pip 包管理器

## 验证安装

安装完成后，运行以下命令验证：

```bash
todo-cli --help
todo-cli list
```

## Windows 用户注意事项

如果需要使用交互式选择功能（`todo-cli select`），请额外安装：

```bash
pip install windows-curses
```

## 卸载

```bash
pip uninstall todo-cli
```
