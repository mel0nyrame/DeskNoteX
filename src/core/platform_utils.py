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


def activate_application() -> None:
    """在 macOS 上 un-hide 并激活当前 application 及所有窗口。

    解决 QMainWindow.hide() 后整个 application 进入 hidden 状态、
    再调 showNormal()/show() 也无法恢复显示的问题:
      1. NSApp.unhide_ 解除 application hidden
      2. 遍历所有 NSWindow 主动 makeKeyAndOrderFront_,确保窗口重新到最前
      3. activateIgnoringOtherApps_ 抢占焦点

    仅 macOS 生效,其他平台 no-op。pyobjc 缺失时静默忽略。
    """
    if not is_macos():
        return
    try:
        from AppKit import NSApplication
        ns_app = NSApplication.sharedApplication()
        ns_app.unhide_(None)
        for window in ns_app.windows():
            try:
                window.makeKeyAndOrderFront_(None)
            except Exception:
                pass
        ns_app.activateIgnoringOtherApps_(True)
    except Exception as exc:
        print(
            f"[platform_utils] macOS activate_application 失败: {exc}",
            file=sys.stderr,
        )


def show_notification(
    tray_icon,
    title: str,
    message: str,
    category_color: str,
    duration_ms: int = 5000,
) -> None:
    """统一的系统通知入口。

    Args:
        tray_icon: 调用方传入的 tray 对象(QSystemTrayIcon 实例,
                  macOS 上是 NSStatusItem 包装对象 —— 此参数 macOS 路径忽略)
        title: 通知标题
        message: 通知正文
        category_color: 分类颜色(当前仅作为接口占位,不影响实际显示)
        duration_ms: 通知显示时长(毫秒)

    行为:
      - macOS:  走 show_macos_notification(NSUserNotification,已废弃但可用)
      - Windows 且 win10toast 可用: 走 win10toast(更接近系统通知样式)
      - 其他 / win10toast 缺失: 降级到 tray_icon.showMessage(QSystemTrayIcon)
    """
    if is_macos():
        show_macos_notification(title, message, duration_ms)
        return

    if is_windows():
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=max(1, duration_ms // 1000), threaded=True)
            return
        except Exception as exc:
            print(f"[platform_utils] win10toast 不可用,降级到 tray: {exc}", file=sys.stderr)

    from PyQt5.QtWidgets import QSystemTrayIcon

    if hasattr(tray_icon, 'showMessage'):
        tray_icon.showMessage(title, message, QSystemTrayIcon.Information, duration_ms)


def make_tray_icon(size: int = 18):
    """生成 macOS menu bar 用的 template icon。

    macOS 的 menu bar (俗称"顶部状态栏",用户口语可能叫"docker 栏")
    对 tray icon 有特殊规则:
      1. 必须是 template image —— 只用黑色 + alpha,其他颜色被忽略
      2. 系统自动反色:深色菜单栏下显示白色,浅色下显示黑色
      3. 系统自动应用圆形遮罩 —— 让 icon 融入 menu bar 视觉

    之前用 `QApplication.style().standardIcon(SP_ComputerIcon)` 是彩色
    Qt 内置图标,macOS 不会应用圆形遮罩,所以用户看到的是完整方形图片。

    关键:PyQt5 的 QIcon 在 macOS 上默认不会传 template 标记,即使我们用
    QPixmap 画了纯黑 + alpha 的图形,macOS 仍然把它当彩色图片处理,不遮罩。
    必须**直接用 NSImage + setTemplate_(True)**,然后转回 QPixmap 给 QIcon。

    Args:
        size: icon 像素尺寸,默认 18(macOS menu bar 标准尺寸)

    Returns:
        QIcon 实例,可直接传给 QSystemTrayIcon.setIcon(...)

    参考:
      https://developer.apple.com/design/human-interface-guidelines/menus
      ("Use template images for menu bar icons" 一节)
      https://developer.apple.com/documentation/appkit/nsimage/1520047-istemplateimage
    """
    if is_macos():
        try:
            return _make_tray_icon_nsimage(size)
        except Exception as exc:
            print(
                f"[platform_utils] NSImage template icon 创建失败,"
                f"回退到 QPixmap: {exc}",
                file=sys.stderr,
            )

    return _make_tray_icon_qpixmap(size)


def _make_tray_icon_nsimage(size: int):
    """macOS 路径:用 NSImage + setTemplate_(True) 创建 template icon。

    这是 macOS 上唯一可靠地让 menu bar 应用圆形遮罩的方式。
    """
    from AppKit import (
        NSImage, NSColor, NSBezierPath,
    )
    from PyQt5.QtGui import QImage, QPixmap, QIcon

    img = NSImage.alloc().initWithSize_((size, size))
    # 必须在画图前标记 template,否则画完后 setTemplate_ 可能不生效
    img.setTemplate_(True)

    img.lockFocus()
    try:
        # 便签本外形(圆角矩形,纯黑)
        NSColor.colorWithCalibratedWhite_alpha_(0.0, 1.0).set()
        rect = ((2, 2), (size - 4, size - 4))
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            rect, 2, 2,
        )
        path.fill()

        # 3 条便签横线(白色 + 稍透明,在黑色便签上模拟文字)
        NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.75).set()
        for i in range(3):
            y = 6 + i * 3
            if y + 1 > size - 2:
                break
            NSBezierPath.fillRect_(((4, y), (size - 8, 1)))
    finally:
        img.unlockFocus()

    # NSImage → TIFF data → QImage → QPixmap → QIcon
    tiff_data = img.TIFFRepresentation()
    qimg = QImage()
    qimg.loadFromData(bytes(tiff_data), "TIFF")
    pix = QPixmap.fromImage(qimg)
    if pix.isNull():
        raise RuntimeError("NSImage TIFF → QPixmap 转换失败")
    return QIcon(pix)


def _make_tray_icon_qpixmap(size: int):
    """fallback:用 QPixmap + QPainter 画 template 风格 icon。

    注意:仅靠 QPixmap 画纯黑 + alpha 不够,PyQt5 在 macOS 上不会
    自动把 QIcon 标记为 template。这个 fallback 用于 pyobjc 缺失
    的情况(此时 macOS 上仍可能显示为方形)。
    """
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QPixmap, QPainter, QColor, QIcon

    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)

    p = QPainter(pix)
    try:
        p.setRenderHint(QPainter.Antialiasing)

        margin = 2

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 255))
        p.drawRoundedRect(
            margin, margin,
            size - 2 * margin - 1, size - 2 * margin - 1,
            2, 2,
        )

        p.setBrush(QColor(255, 255, 255, 220))
        line_top = 6
        line_spacing = max(2, (size - 2 * margin - 4) // 4)
        line_left = margin + 2
        line_right = size - margin - 2
        for i in range(3):
            y = line_top + i * line_spacing
            if y + 1 > size - margin:
                break
            p.drawRect(line_left, y, line_right - line_left, 1)
    finally:
        p.end()

    return QIcon(pix)


class _MacosStatusItemTarget:
    """NSMenuItem target,把 macOS selector 调用桥接到 Python 回调。

    macOS 的 NSMenuItem 必须通过 target-action 模式响应点击:
      item.setTarget_(target)
      item.setAction_("invoke_show:")
    target 需要响应 invoke_show: selector。这里把 selector 实现为 Python 回调。

    实现说明:为避免在 Windows/Linux 模块导入时强依赖 pyobjc,
    这个类用 type() 在 _make_macos_target_class() 内动态创建,
    实际继承 NSObject + objc.super。
    """


_macos_target_class_cache = None


def _make_macos_target_class():
    """动态创建继承 NSObject 的 target class,只在 macOS 上调用一次。

    pyobjc 不允许重复定义同名 Objective-C class,所以必须模块级缓存。
    第二次及之后的调用直接返回已创建的 class。
    """
    global _macos_target_class_cache
    if _macos_target_class_cache is not None:
        return _macos_target_class_cache

    import objc
    from AppKit import NSObject

    class _MacosStatusItemTargetImpl(NSObject):
        def initWithCallbacks_(self, callbacks):
            self = objc.super(_MacosStatusItemTargetImpl, self).init()
            if self is None:
                return None
            self._callbacks = callbacks
            return self

        def invokeShow_(self, sender):
            if "show" in self._callbacks:
                self._callbacks["show"]()

        def invokeHide_(self, sender):
            if "hide" in self._callbacks:
                self._callbacks["hide"]()

        def invokeQuit_(self, sender):
            if "quit" in self._callbacks:
                self._callbacks["quit"]()

    _macos_target_class_cache = _MacosStatusItemTargetImpl
    return _macos_target_class_cache


def create_macos_status_item(on_show, on_hide, on_quit,
                              tooltip="DeskNoteX"):
    """在 macOS 上直接用 NSStatusBar 创建状态栏项。

    完全绕过 PyQt5 的 QSystemTrayIcon。QSystemTrayIcon.setIcon(QIcon)
    在 PyQt5 内部把 QIcon 转 NSImage 时会强制把 isTemplate 设为 False,
    导致 macOS menu bar 不应用圆形遮罩 —— 用户看到完整方形图片。

    这里直接走 NSStatusBar.setImage_(template_NSImage),让 macOS
    真正按 template image 处理(自动反色 + 应用 menu bar 圆形遮罩)。

    Args:
        on_show: Python 回调,菜单"显示"项点击时触发
        on_hide: Python 回调,菜单"隐藏"项点击时触发
        on_quit: Python 回调,菜单"退出"项点击时触发
        tooltip: 鼠标 hover 显示的文字

    Returns:
        (status_item, target_obj, bar) 元组:
        - status_item: NSStatusItem 实例
        - target_obj: NSObject 持有,防止 GC 后 selector 失效
        - bar: NSStatusBar 实例(用于 removeStatusItem_)
    """
    from AppKit import (
        NSStatusBar, NSImage, NSColor, NSBezierPath,
        NSMenu, NSMenuItem,
    )

    # 1. 创建 template NSImage(纯黑 + alpha 便签本图形)
    size = 22  # macOS menu bar 标准尺寸
    img = NSImage.alloc().initWithSize_((size, size))
    img.setTemplate_(True)
    img.lockFocus()
    try:
        NSColor.colorWithCalibratedWhite_alpha_(0.0, 1.0).set()
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((2, 2), (size - 4, size - 4)), 2, 2,
        )
        path.fill()
        NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.75).set()
        for i in range(3):
            y = 6 + i * 3
            if y + 1 > size - 2:
                break
            NSBezierPath.fillRect_(((4, y), (size - 8, 1)))
    finally:
        img.unlockFocus()

    # 2. 创建 status item
    bar = NSStatusBar.systemStatusBar()
    item = bar.statusItemWithLength_(-1.0)  # NSVariableStatusItemLength
    item.setImage_(img)
    item.setToolTip_(tooltip)

    # 3. 创建菜单 + target
    target_cls = _make_macos_target_class()
    target = target_cls.alloc().initWithCallbacks_({
        "show": on_show,
        "hide": on_hide,
        "quit": on_quit,
    })

    menu = NSMenu.alloc().init()

    show_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "显示", "invokeShow:", "",
    )
    show_item.setTarget_(target)
    menu.addItem_(show_item)

    hide_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "隐藏", "invokeHide:", "",
    )
    hide_item.setTarget_(target)
    menu.addItem_(hide_item)

    menu.addItem_(NSMenuItem.separatorItem())

    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "退出", "invokeQuit:", "",
    )
    quit_item.setTarget_(target)
    menu.addItem_(quit_item)

    item.setMenu_(menu)

    return item, target, bar


def remove_macos_status_item(status_item, bar):
    """从 menu bar 移除 NSStatusItem。"""
    try:
        bar.removeStatusItem_(status_item)
    except Exception as exc:
        print(
            f"[platform_utils] remove_macos_status_item 失败: {exc}",
            file=sys.stderr,
        )


def show_macos_notification(title, message, duration_ms=5000):
    """在 macOS 上用 NSUserNotification 显示系统通知。

    NSUserNotification 在 macOS 10.14+ 已废弃,但仍可用。UNUserNotificationCenter
    需要 bundle ID 和 code signing,这里不引入这种复杂性。
    """
    try:
        from AppKit import NSUserNotification, NSUserNotificationCenter
        note = NSUserNotification.alloc().init()
        note.setTitle_(str(title))
        note.setInformativeText_(str(message))
        center = NSUserNotificationCenter.defaultUserNotificationCenter()
        if center is not None:
            center.deliverNotification_(note)
    except Exception as exc:
        print(
            f"[platform_utils] show_macos_notification 失败: {exc}",
            file=sys.stderr,
        )
