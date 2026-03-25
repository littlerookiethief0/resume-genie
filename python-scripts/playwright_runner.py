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
        _diag = lambda msg: print(f"[diag] {msg}", file=sys.stderr, flush=True)
        _diag(f"Python: {sys.version}")
        _diag(f"Platform: {platform.system()} {platform.machine()}")
        _diag(f"CWD: {os.getcwd()}")
        _diag(f"user_data_dir: {self.user_data_dir}")
        _diag(f"PLAYWRIGHT_BROWSERS_PATH: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '<not set>')}")

        # 主动查找 Camoufox 浏览器二进制路径
        resolved_firefox = None
        # 1) 环境变量指定
        env_firefox = os.environ.get("RESUME_GENIE_FIREFOX_PATH")
        if env_firefox and os.path.isfile(env_firefox):
            resolved_firefox = env_firefox
            _diag(f"Firefox from env: {resolved_firefox}")
        # 2) camoufox 包内置路径（正常情况）
        if not resolved_firefox:
            try:
                from camoufox.pkgman import get_path as _get_cf_path
                _pkg_path = _get_cf_path("firefox")
                _diag(f"camoufox pkg path: {_pkg_path} (exists={os.path.exists(str(_pkg_path))})")
                if os.path.exists(str(_pkg_path)):
                    resolved_firefox = str(_pkg_path)
            except Exception as _e:
                _diag(f"camoufox pkgman error: {_e}")
        # 3) 在 browsers/ 目录下搜索（CI 可能下载到这里）
        if not resolved_firefox:
            browsers_dir = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
            if browsers_dir and os.path.isdir(browsers_dir):
                _diag(f"Searching browsers dir: {browsers_dir}")
                for root, dirs, files in os.walk(browsers_dir):
                    for f in files:
                        if f in ("firefox.exe", "firefox", "camoufox.exe"):
                            candidate = os.path.join(root, f)
                            resolved_firefox = candidate
                            _diag(f"Found browser in browsers/: {candidate}")
                            break
                    if resolved_firefox:
                        break

        if resolved_firefox:
            _diag(f"Using firefox executable: {resolved_firefox}")
        else:
            _diag("WARNING: No firefox executable found, Camoufox will use its default discovery")

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
        if resolved_firefox:
            launch_kw["executable_path"] = resolved_firefox

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
