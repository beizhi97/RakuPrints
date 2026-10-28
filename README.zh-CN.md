# RakuPrints 乐印

<img src="assets/icon.png" width="80" alt="RakuPrints 图标">

Windows 批量打印工具，可将 PDF、Excel、Word 和 PowerPoint 文件加入同一个队列，按顺序打印。

[English](README.md) · [日本語](README.ja.md) · **简体中文**

本仓库是 [sukun-inu/RakuPrints](https://github.com/sukun-inu/RakuPrints) 的中文优化 Fork，保留原作者及 MIT 许可证信息。

## 本 Fork 的中文优化

- 调整打印、双面翻页、工作表和文件列表操作的中文用语。
- 翻译文件选择框、Excel 方向分析和应用自身的打印错误提示。
- 中文界面优先使用微软雅黑，并加载 Qt 的简体中文标准按钮翻译。
- 修复切换语言、刷新设置选项时重复触发设置变更信号的问题。
- 提供[中文使用说明](docs/USAGE.zh-CN.md)，说明“勾选”和“选中”的区别。
- 支持每个文件独立设置打印页码，例如 `2`、`3-6`、`1,3,5-8`，适用于 PDF、Word、Excel 和 PowerPoint。
- 更新检查与在线更新说明指向本 Fork；尚未发布 Release 时视为暂无更新。

## 环境要求

- Windows。
- 打印 Excel、Word、PowerPoint 需要本机安装对应的 Microsoft Office 桌面应用。
- 仅打印 PDF 不需要 Microsoft Office。
- 从源码运行需要 Python，以及 [requirements.txt](requirements.txt) 中的依赖。本次开发验证使用 Python 3.12。

## 从源码运行

在 PowerShell 中执行：

```powershell
git clone https://github.com/beizhi97/RakuPrints.git
cd RakuPrints
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.main
```

在右侧“显示”区域将语言设为“中文(简体)”。初次启动默认跟随系统语言；中文 Windows 会自动选用简体中文。

上游已经发布的安装包不包含本 Fork 的修改。如需安装包，请查看[本 Fork 的 Releases](https://github.com/beizhi97/RakuPrints/releases)，以实际发布的文件为准；未发布时请从源码运行。

## 开始使用

1. 拖入文件，或点击“添加文件”“添加文件夹”。添加文件夹会递归加入子文件夹中的受支持文件。
2. 确认打印机、份数、双面翻页和纸张尺寸。
3. 点击“开始打印”，打印所有已勾选的文件。也可选中若干行，点击“打印所选文件”。
4. 如有失败任务，在“帮助 → 日志摘要”中查看详情，或点击“重试失败任务”。

**只打印某个文件的指定页**：选中文件，点击“指定打印页”（或右键菜单、`Ctrl+Alt+R`），填写页码后确认，再点击“打印所选文件”。留空恢复全部页；多选时可在同一窗口逐个填写不同范围。列表的“打印页码”列会显示当前设置，双击该列也可修改。

“移出列表”只移除队列记录，不会删除磁盘上的原文件。更多操作见[中文使用说明](docs/USAGE.zh-CN.md)。

## 开发验证与构建

```powershell
# 回归测试，不向打印机发送任务
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 构建 Windows 程序
.\.venv\Scripts\python.exe -m PyInstaller RakuPrint.spec --noconfirm
```

页码功能已经用实际 PDF 绘制输出、模拟打印后端，以及本机 Microsoft Office 12.0 的原生 PDF 导出验证。未向实体打印机发送测试任务；设备打印效果仍需实际确认。页码语义与 Excel 工作表规则见[指定打印页](docs/USAGE.zh-CN.md#8-指定打印页)。

已安装 Microsoft Office 的 Windows 环境可运行原生导出验证脚本。脚本仅创建内存中的示例文档、导出临时 PDF 并检查取页结果，不调用设备打印：

```powershell
.\.venv\Scripts\python.exe scripts\verify_page_exports.py word
.\.venv\Scripts\python.exe scripts\verify_page_exports.py excel
.\.venv\Scripts\python.exe scripts\verify_page_exports.py ppt
```

可执行文件输出到 `dist\RakuPrint\RakuPrint.exe`。创建安装程序的现有入口为 `scripts\build.ps1`，需要 Inno Setup 6；安装器目前保留上游的日文和英文界面。

界面和模拟测试通过不代表实际打印已验证。不同 Office 版本、打印机驱动和真实设备仍需现场测试；操作系统、Office、驱动返回的原始错误信息可能使用其自身的界面语言。

## 文档与许可证

- [中文使用说明](docs/USAGE.zh-CN.md)
- [日文架构说明](docs/ARCHITECTURE.ja.md)
- [日文开发说明](docs/DEVELOPMENT.ja.md)
- [MIT 许可证](LICENSE) — Copyright (c) 2026 Hibiki Suzuki
