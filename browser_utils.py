from DrissionPage import ChromiumOptions, Chromium
import sys
import os
from logger import info, warning, error


class BrowserManager:
    def __init__(self, extension_path=None):
        self.browser = None
        self.extension_path = extension_path
        self.is_vercel = bool(os.environ.get("VERCEL"))

    def init_browser(self):
        """初始化浏览器"""
        try:
            if self.is_vercel:
                info("Vercel环境检测到，使用特殊配置")
                # 在 Vercel 环境中使用特殊配置
                co = ChromiumOptions()
                co.set_argument('--headless')
                co.set_argument('--no-sandbox')
                co.set_argument('--disable-dev-shm-usage')
                co.set_argument('--disable-gpu')
                co.set_argument('--disable-software-rasterizer')
                co.set_argument('--hide-scrollbars')
                co.set_argument('--disable-extensions')
                co.set_argument('--single-process')
                co.set_argument('--ignore-certificate-errors')
                co.set_argument('--remote-debugging-port=9222')
                
                try:
                    # 使用 playwright 的 chromium
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as p:
                        browser_path = p.chromium.executable_path
                        info(f"Playwright Chromium 路径: {browser_path}")
                        if os.path.exists(browser_path):
                            info(f"使用 Playwright Chromium: {browser_path}")
                            co.set_browser_path(browser_path)
                        else:
                            error("Playwright Chromium 不可用")
                            return None
                except ImportError:
                    error("Playwright 未安装，请先安装: pip install playwright")
                    return None
                except Exception as e:
                    error(f"获取 Playwright Chromium 失败: {str(e)}")
                    return None
                
            else:
                info("本地环境，使用默认配置")
                co = ChromiumOptions()
                co.set_argument('--headless')
            
            self.browser = Chromium(co)
            info("浏览器初始化成功")
            return self.browser
            
        except Exception as e:
            error(f"浏览器初始化失败: {str(e)}")
            return None

    def _get_browser_options(self):
        co = ChromiumOptions()
        browser_path = os.getenv("BROWSER_PATH", None)
        if browser_path and os.path.exists(browser_path):
            co.set_paths(browser_path=browser_path)
        try:
            extension_path = self._get_extension_path()
            if extension_path:
                co.add_extension(extension_path)
                info("浏览器扩展加载成功")
            else:
                warning("浏览器扩展未加载")
        except Exception as e:
            warning("浏览器扩展加载失败:", str(e))

        co.set_user_agent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.92 Safari/537.36"
        )
        co.set_pref("credentials_enable_service", False)
        co.set_argument("--hide-crash-restore-bubble")
        proxy = os.getenv('BROWSER_PROXY')
        if proxy:
            co.set_proxy(proxy)
        co.auto_port()
        co.headless(os.getenv('BROWSER_HEADLESS', 'True').lower() == 'true')

        if sys.platform == "darwin":
            co.set_argument("--no-sandbox")
            co.set_argument("--disable-gpu")

        return co

    def _get_extension_path(self):
        if self.extension_path and os.path.exists(self.extension_path):
            return self.extension_path
            
        script_dir = os.path.dirname(os.path.abspath(__file__))
        extension_path = os.path.join(script_dir, "turnstilePatch")
        
        if hasattr(sys, "_MEIPASS"):
            extension_path = os.path.join(sys._MEIPASS, "turnstilePatch")
        
        if os.path.exists(extension_path):
            required_files = ['manifest.json', 'script.js']
            if all(os.path.exists(os.path.join(extension_path, f)) for f in required_files):
                return extension_path
            else:
                warning("扩展所需文件不完整:", required_files)
        else:
            raise FileNotFoundError(f"扩展文件未找到: {extension_path}")
        
        return None

    def cleanup(self):
        """清理浏览器资源"""
        try:
            if self.browser:
                self.browser.quit()
                info("浏览器资源已清理")
        except Exception as e:
            error(f"清理浏览器资源失败: {str(e)}")
        finally:
            self.browser = None
