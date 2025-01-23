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
                
                # 设置 Chrome 路径（Vercel 环境中的路径）
                chrome_paths = [
                    '/opt/google/chrome/chrome',  # Vercel 标准路径
                    '/usr/bin/google-chrome',     # 备选路径 1
                    '/usr/bin/chromium',          # 备选路径 2
                    '/usr/bin/chromium-browser'   # 备选路径 3
                ]
                
                chrome_found = False
                for chrome_path in chrome_paths:
                    if os.path.exists(chrome_path):
                        info(f"找到Chrome: {chrome_path}")
                        co.set_browser_path(chrome_path)
                        chrome_found = True
                        break
                
                if not chrome_found:
                    error("未找到可用的Chrome浏览器")
                    # 尝试安装 Chrome
                    try:
                        info("尝试安装Chrome...")
                        os.system("apt-get update && apt-get install -y chromium-browser")
                        if os.path.exists('/usr/bin/chromium-browser'):
                            info("Chrome安装成功")
                            co.set_browser_path('/usr/bin/chromium-browser')
                            chrome_found = True
                    except Exception as e:
                        error(f"Chrome安装失败: {str(e)}")
                        return None
                    
                if not chrome_found:
                    error("无法找到或安装Chrome浏览器")
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
