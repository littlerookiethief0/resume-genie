import re
import os
import platform
import subprocess
from camoufox.sync_api import Camoufox

try:
    from .local_utils import get_data_path
except ImportError:
    from local_utils import get_data_path


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
    使用 Camoufox(Firefox) 持久化 context。
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

        import sys
        print(f"[diag] Python: {sys.version}", file=sys.stderr, flush=True)
        print(f"[diag] Platform: {platform.system()} {platform.machine()}", file=sys.stderr, flush=True)
        print(f"[diag] CWD: {os.getcwd()}", file=sys.stderr, flush=True)
        print(f"[diag] user_data_dir: {self.user_data_dir}", file=sys.stderr, flush=True)
        print(f"[diag] PLAYWRIGHT_BROWSERS_PATH: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '<not set>')}", file=sys.stderr, flush=True)
        try:
            import camoufox as _cf
            print(f"[diag] camoufox version: {getattr(_cf, '__version__', 'unknown')}", file=sys.stderr, flush=True)
            from camoufox.pkgman import get_path as _get_cf_path
            _bp = _get_cf_path("firefox")
            print(f"[diag] camoufox browser path: {_bp} (exists={os.path.exists(_bp)})", file=sys.stderr, flush=True)
        except Exception as _e:
            print(f"[diag] camoufox info error: {_e}", file=sys.stderr, flush=True)

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
        )
        firefox_path = os.environ.get("RESUME_GENIE_FIREFOX_PATH")
        if firefox_path and os.path.isfile(firefox_path):
            launch_kw["executable_path"] = firefox_path

        print(f"[diag] Launching Camoufox with headless={self.headless}, os={_platform_os}", file=sys.stderr, flush=True)
        self._camoufox = Camoufox(**launch_kw)
        raw_context = self._camoufox.__enter__()
        self.context = _FirefoxContextWrapper(raw_context)
        print("[diag] Camoufox started successfully", file=sys.stderr, flush=True)

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
