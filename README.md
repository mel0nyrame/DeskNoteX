# 📝 DeskNoteX - 桌面便签任务管理

一个简洁美观的桌面便签应用，基于 Python + PyQt5 构建，支持任务管理、分类标签、优先级设置和提醒通知。

## macOS 运行说明

项目主分支最初面向 Windows，本节说明在 macOS 上运行所需的额外步骤。

### 直接从源码运行

```bash
# 推荐使用虚拟环境（项目不强制依赖特定虚拟环境位置）
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# 可选：修复 Dock 点击图标不激活主窗口的问题
pip install pyobjc-framework-Cocoa

python main.py
```

### 已知限制

- **Linux 不在官方支持范围**：本项目维护者当前无 Linux 环境进行验证。若需 Linux 支持，欢迎基于 `src/core/platform_utils.py` 的抽象层提交 PR。
- **Dock 激活**：未安装 `pyobjc-framework-Cocoa` 时，Dock 点击图标可能不会重新激活已隐藏的主窗口。安装该可选依赖即可修复。
- **中文字体**：macOS 上首次启动会自动使用 "PingFang SC"；Windows 用户行为无变化。
- **应用图标**：darwin 优先使用 `assets/icon.icns`，若不存在则用 `assets/icon.png`。如果你想贡献一个 `.icns` 文件，放到 `assets/` 目录下即可被自动识别。

### 打包成 .app（本项目未提供官方方案）

本仓库的 `build.py` 目前仍以 Windows 图标为主。要在 macOS 上打包为 `.app`，可参考以下命令自行调整（未在 PR 范围内）：

```bash
pyinstaller --name=DeskNoteX --windowed --icon=assets/icon.icns main.py
```

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| **任务管理** | 创建、编辑、删除任务，支持搜索筛选 |
| **分类标签** | 自定义分类，按颜色区分不同类型 |
| **优先级** | 高/中/低三级优先级，醒目提示 |
| **截止日期** | 设置任务截止时间，到期提醒 |
| **状态追踪** | 全部/进行中/已完成，清晰分类 |
| **数据统计** | 任务完成率、分类分布可视化 |
| **主题切换** | 浅色/深色模式，支持自定义主题色 |
| **边缘贴边** | 窗口自动贴边收纳，不占桌面空间 |
| **系统托盘** | 最小化到托盘，后台常驻提醒 |

## 🚀 快速启动

### 方式一：直接运行（需 Python 环境）

```bash
cd DeskNoteX
pip install -r requirements.txt
python main.py
