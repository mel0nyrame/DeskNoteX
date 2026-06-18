"""跨平台抽象层。

集中所有 sys.platform / sys.frozen / ctypes / pyobjc 等平台特定代码,
其他文件禁止直接判断平台或读取 sys.frozen,统一调用本文件暴露的函数。
"""

import os
import sys


def is_macos() -> bool:
    """是否为 macOS 平台。"""
    return sys.platform == "darwin"


def is_windows() -> bool:
    """是否为 Windows 平台。"""
    return sys.platform == "win32"


def _resolve_assets_dir() -> str:
    """解析 assets 目录绝对路径(打包模式/开发模式通用)。

    Returns:
        打包模式: sys._MEIPASS/assets
        开发模式: 本文件所在项目根/assets(即 src/core 的上两级)
    """
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "assets")
    # 文件位置: <project_root>/src/core/platform_utils.py
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "assets",
    )


def get_app_icon_path() -> str:
    """返回 assets 里应用图标的绝对路径(按平台优先后缀)。

    Returns:
        darwin: 先 .icns,后 .png,均不存在返回 ""
        其他: 先 .ico,后 .png,均不存在返回 ""
    """
    assets_dir = _resolve_assets_dir()
    if is_macos():
        candidates = ("icon.icns", "icon.png")
    elif is_windows():
        candidates = ("icon.ico", "icon.png")
    else:
        candidates = ("icon.png",)
    for name in candidates:
        path = os.path.join(assets_dir, name)
        if os.path.exists(path):
            return path
    return ""


def setup_platform_app() -> None:
    """在 QApplication 创建之后调用一次,做平台特定的进程初始化。

    - Windows:设置 AppUserModelID,让任务栏正确分组。
    - macOS:设置 NSApplication 激活策略为 Regular,修复 Dock 点击图标
      不激活主窗口的已知问题。pyobjc 缺失时静默跳过。
    - 其他平台:no-op。
    """
    if is_windows():
        try:
            import ctypes
            myappid = "mycompany.desknotex.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as exc:
            print(f"[platform_utils] 设置 AppUserModelID 失败: {exc}", file=sys.stderr)
        return

    if is_macos():
        try:
            import objc  # noqa: F401  仅用于触发 ImportError 检测
            from AppKit import NSApplication, NSApplicationActivationPolicyRegular
            NSApplication.sharedApplication().setActivationPolicy_(
                NSApplicationActivationPolicyRegular
            )
        except Exception as exc:
            print(
                f"[platform_utils] macOS Dock 激活修复跳过(可选依赖缺失): {exc}",
                file=sys.stderr,
            )
        return


def get_default_font_family() -> str:
    """返回平台默认中文字体名称。

    Returns:
        darwin: "PingFang SC"
        win32:  "Microsoft YaHei"
        其他:   "sans-serif"
    """
    if is_macos():
        return "PingFang SC"
    if is_windows():
        return "Microsoft YaHei"
    return "sans-serif"


def show_notification(
    tray_icon,
    title: str,
    message: str,
    category_color: str,
    duration_ms: int = 5000,
) -> None:
    """统一的系统通知入口。

    Args:
        tray_icon: 调用方传入的 QSystemTrayIcon 实例(由 MainWindow 持有)
        title: 通知标题
        message: 通知正文
        category_color: 分类颜色(当前仅作为接口占位,不影响实际显示)
        duration_ms: 通知显示时长(毫秒)

    行为:
      - macOS:  tray_icon.showMessage(...)
      - Windows 且 win10toast 可用: 走 win10toast(更接近系统通知样式)
      - 其他 / win10toast 缺失: 降级到 tray_icon.showMessage
    """
    if is_windows():
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=duration_ms // 1000, threaded=True)
            return
        except Exception as exc:
            print(f"[platform_utils] win10toast 不可用,降级到 tray: {exc}", file=sys.stderr)

    from PyQt5.QtWidgets import QSystemTrayIcon

    tray_icon.showMessage(title, message, QSystemTrayIcon.Information, duration_ms)
