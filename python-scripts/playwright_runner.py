import re
import os
import platform
import struct
import subprocess
import sys

# Windows ARM64 + x86_64 Python: Camoufox 不支持 win-arm64，但 x86_64 Firefox
# 可通过 WoW64 模拟正常运行，覆盖架构检测使其使用 x86_64 二进制
if (platform.system() == "Windows"
        and platform.machine().lower() in ("arm64", "aarch64")
        and struct.calcsize("P") * 8 == 64):
    platform.machine = lambda: "AMD64"

from camoufox.sync_api import Camoufox

try:
    from .local_utils import get_data_path
except ImportError:
    from local_utils import get_data_path


def _ensure_camoufox_executable(_diag):
    """
    确保本机已存在 Camoufox 官方浏览器二进制，并返回其绝对路径。
    仅使用 camoufox/pkgman 管理的路径；若缺失则执行一次 `python -m camoufox fetch`。
    浏览器下载在用户本机缓存目录，不随桌面客户端安装包分发。
    不支持系统 Firefox、Playwright 预置 firefox 或其它可执行文件覆盖。
    """
    from camoufox.pkgman import get_path as _get_cf_path

    def _firefox_path():
        return str(_get_cf_path("firefox"))

    try:
        path = _firefox_path()
    except Exception as e:
        _diag(f"camoufox get_path error: {e}")
        raise RuntimeError(
            "无法解析 Camoufox 浏览器路径，请确认已安装 camoufox Python 包。"
        ) from e

    if os.path.isfile(path):
        _diag(f"Camoufox browser present: {path}")
        return path

    _diag("Camoufox binary missing, running: python -m camoufox fetch")
    r = subprocess.run(
        [sys.executable, "-m", "camoufox", "fetch"],
        timeout=900,
        env=os.environ.copy(),
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"camoufox fetch 失败 (exit {r.returncode})，请检查网络后重试，"
            f"或手动执行: {sys.executable} -m camoufox fetch"
        )

    path = _firefox_path()
    if not os.path.isfile(path):
        raise RuntimeError(
            f"camoufox fetch 已完成但仍找不到 Camoufox 可执行文件: {path}"
        )
    _diag(f"Camoufox fetch finished, using: {path}")
    return path


def _detect_screen_size():
    """检测屏幕逻辑分辨率，失败时返回平台安全默认值。"""
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.check_output(
                [
                    "python3", "-c",
                    "import Quartz;"
                    "b=Quartz.CGDisplayBounds(Quartz.CGMainDisplayID());"
                    "print(int(b.size.width),int(b.size.height))",
                ],
                timeout=5,
                stderr=subprocess.DEVNULL,
            ).decode().strip()
            w, h = out.split()
            return int(w), int(h)
        if system == "Windows":
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        pass
    if system == "Darwin":
        return 1440, 900
    if system == "Windows":
        return 1920, 1080
    return 1366, 768


class _FirefoxContextWrapper:
    """
    包装 Firefox 持久化 context：new_page() 优先复用已有页面，避免多窗口。
    Firefox 中 new_page() 会开新窗口而非新标签。
    """

    def __init__(self, context):
        self._context = context

    def new_page(self):
        if self._context.pages:
            page = self._context.pages[0]
        else:
            page = self._context.new_page()
        try:
            page.evaluate(
                "window.moveTo(0,0);"
                "window.resizeTo(screen.availWidth, screen.availHeight);"
            )
        except Exception:
            pass
        return page

    def __getattr__(self, name):
        return getattr(self._context, name)


class PlaywrightBrowserManager:
    """
    使用 Camoufox 持久化 context（仅官方 Camoufox 二进制，不经由系统 Firefox）。
    支持 with 用法和 start/close_tabs/disconnect 用法。
    """

    def __init__(self, user_data_dir=None, headless=False):
        self.user_data_dir = user_data_dir or get_data_path("camoufox_profile")
        self.headless = headless
        self._camoufox = None
        self.context = None
        _default_ua = {
            "Darwin": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        }.get(platform.system(), "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0")
        self.user_agent = os.environ.get("RESUME_GENIE_USER_AGENT", _default_ua)

    def start(self):
        """启动 Camoufox 持久化 context，返回 context。已启动时直接返回当前 context。"""
        if self.context is not None:
            return self.context

        _diag = lambda msg: print(f"[diag] {msg}", file=sys.stderr, flush=True)
        camoufox_exe = _ensure_camoufox_executable(_diag)
        _diag(f"Python: {sys.version}")
        _diag(f"Platform: {platform.system()} {platform.machine()}")
        _diag(f"CWD: {os.getcwd()}")
        _diag(f"user_data_dir: {self.user_data_dir}")

        os.makedirs(self.user_data_dir, exist_ok=True)
        _platform_os = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(
            platform.system(), "macos"
        )
        launch_kw = dict(
            persistent_context=True,
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            os=_platform_os,
            locale="zh-CN,zh,en-US",
            user_agent=self.user_agent,
            viewport=None,
            window=_detect_screen_size(),
            color_scheme="light",
            fonts=[
                "PingFang SC",
                "Hiragino Sans GB",
                "Helvetica Neue",
                "Arial",
            ],
            config={
                "fonts:spacing_seed": 0,
                "disableTheming": True,
            },
            executable_path=camoufox_exe,
        )

        _diag(f"Launching Camoufox with headless={self.headless}, os={_platform_os}")
        self._camoufox = Camoufox(**launch_kw)
        raw_context = self._camoufox.__enter__()
        self.context = _FirefoxContextWrapper(raw_context)
        _diag("Camoufox started successfully")

        return self.context

    def close_tabs(self, keyword: str):
        """关闭 URL 中包含 keyword 的页面。"""
        if self.context is None:
            return
        for page in list(self.context.pages):
            try:
                if keyword in page.url:
                    page.close()
            except Exception:
                pass

    def disconnect(self):
        """关闭 context 并停止 Playwright。"""
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None
        if self._camoufox:
            try:
                self._camoufox.__exit__(None, None, None)
            except Exception:
                pass
            self._camoufox = None

    def __enter__(self):
        self.start()
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


    @staticmethod
    def action_and_capture(page, action, url_pattern, timeout=30000):
        """执行动作并捕获匹配的网络响应"""
        def match(resp):
            return url_pattern in resp.url if isinstance(url_pattern, str) else re.search(url_pattern, resp.url)
        try:
            with page.expect_response(match, timeout=timeout) as resp_info:
                action()
            return resp_info.value.json()
        except Exception:
            return {}

    @staticmethod
    def action_and_capture_binary(page, action, url_pattern, timeout=30000):
        """执行动作并捕获二进制响应"""
        def match(resp):
            return url_pattern in resp.url if isinstance(url_pattern, str) else re.search(url_pattern, resp.url)
        try:
            with page.expect_response(match, timeout=timeout) as resp_info:
                action()
            return resp_info.value.body()
        except Exception:
            return b""

    @staticmethod
    def action_and_download(page, action, save_path, timeout=30000):
        """执行动作触发下载并保存文件"""
        with page.expect_download(timeout=timeout) as download_info:
            action()
        download = download_info.value
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        with open(download.path(), "rb") as f:
            binary_data = f.read()
        with open(save_path, "wb") as f:
            f.write(binary_data)
        return binary_data

    
    def action_and_download_binary(self, page, action, save_path, timeout=30000):
        """
        执行动作触发下载，将文件保存到 save_path，并返回 PDF 二进制数据。

        参数:
            page: Playwright 页面
            action: 触发下载的 lambda，如 lambda: page.locator("...").click()
            save_path: 保存文件的完整路径（含文件名）
        返回:
            bytes: 文件二进制数据
        """
        with page.expect_download(timeout=timeout) as download_info:
            action()
        download = download_info.value
        with open(download.path(), "rb") as f:
            binary_data = f.read()
        dirpart = os.path.dirname(save_path)
        if dirpart:
            os.makedirs(dirpart, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(binary_data)
        return binary_data
