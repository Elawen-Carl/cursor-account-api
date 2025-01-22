import os
import sys
import psutil
import time
import random
from logger import info, error, warning, debug

os.environ["PYTHONWARNINGS"] = "ignore"

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from browser_utils import BrowserManager
from get_email_code import EmailVerificationHandler

LOGIN_URL = "https://authenticator.cursor.sh"
SIGN_UP_URL = "https://authenticator.cursor.sh/sign-up"
SETTINGS_URL = "https://www.cursor.com/settings"
MAIL_URL = "https://mail.cx/zh/"
TOTAL_USAGE = 0


def handle_turnstile(tab):
    try:
        while True:
            try:
                challengeCheck = (
                    tab.ele("@id=cf-turnstile", timeout=2)
                    .child()
                    .shadow_root.ele("tag:iframe")
                    .ele("tag:body")
                    .sr("tag:input")
                )

                if challengeCheck:
                    time.sleep(random.uniform(1, 3))
                    challengeCheck.click()
                    time.sleep(2)
                    return True
            except:
                pass

            if tab.ele("@name=password"):
                break
            if tab.ele("@data-index=0"):
                break
            if tab.ele("Account Settings"):
                break

            time.sleep(random.uniform(1, 2))
    except Exception as e:
        error("处理验证失败:", str(e))
        return False


def get_cursor_session_token(tab, max_attempts=5, retry_interval=3):
    try:
        tab.get(SETTINGS_URL)
        time.sleep(5)

        usage_selector = (
            "css:div.col-span-2 > div > div > div > div > "
            "div:nth-child(1) > div.flex.items-center.justify-between.gap-2 > "
            "span.font-mono.text-sm\\/\\[0\\.875rem\\]"
        )
        usage_ele = tab.ele(usage_selector)
        total_usage = "null"
        if usage_ele:
            total_usage = usage_ele.text.split("/")[-1].strip()
            global TOTAL_USAGE
            TOTAL_USAGE = total_usage
            info("使用限制:", total_usage)

        info("获取Cookie中...")
        attempts = 0

        while attempts < max_attempts:
            try:
                cookies = tab.cookies()
                for cookie in cookies:
                    if cookie.get("name") == "WorkosCursorSessionToken":
                        return cookie["value"].split("%3A%3A")[1]

                attempts += 1
                if attempts < max_attempts:
                    warning("未找到Cursor会话Token，重试中...")
                    time.sleep(retry_interval)
                else:
                    error("未找到Cursor会话Token")

            except Exception as e:
                error("获取Token失败:", str(e))
                attempts += 1
                if attempts < max_attempts:
                    info("重试获取Token，等待时间:", retry_interval)
                    time.sleep(retry_interval)

        return False

    except Exception as e:
        warning("获取Token过程出错:", str(e))
        return False


def get_temp_email(tab):
    max_retries = 15
    last_email = None
    stable_count = 0

    info("等待获取临时邮箱...")
    for i in range(max_retries):
        try:
            email_input = tab.ele("css:input.bg-gray-200[disabled]", timeout=3)
            if email_input:
                current_email = email_input.attr("value")
                if current_email and "@" in current_email:
                    if current_email == last_email:
                        stable_count += 1
                        if stable_count >= 2:
                            info("成功获取邮箱")
                            return current_email
                    else:
                        stable_count = 0
                        last_email = current_email
                        info("当前邮箱:", current_email)

            info("等待邮箱分配...")
            time.sleep(1)

        except Exception as e:
            warning("获取邮箱出错:", str(e))
            time.sleep(1)
            stable_count = 0

    error("未能获取邮箱")
    raise ValueError("未能获取邮箱")


def sign_up_account(browser, tab, account_info):
    info("开始注册账号")
    info("账号信息:", f"邮箱: {account_info['email']}, 姓名: {account_info['first_name']} {account_info['last_name']}")
    tab.get(SIGN_UP_URL)

    try:
        if tab.ele("@name=first_name"):
            debug("填写姓名信息...")
            tab.actions.click("@name=first_name").input(account_info["first_name"])
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=last_name").input(account_info["last_name"])
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=email").input(account_info["email"])
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@type=submit")
            info("基本信息提交成功")

    except Exception as e:
        error(f"填写姓名信息失败: {str(e)}")
        return False

    debug("处理验证码...")
    handle_turnstile(tab)

    try:
        if tab.ele("@name=password"):
            debug("设置密码...")
            tab.ele("@name=password").input(account_info["password"])
            time.sleep(random.uniform(1, 3))

            tab.ele("@type=submit").click()
            info("密码设置成功")

    except Exception as e:
        error(f"密码设置失败: {str(e)}")
        return False

    time.sleep(random.uniform(1, 3))
    if tab.ele("This email is not available."):
        warning("邮箱已被使用")
        return False

    debug("处理最终验证...")
    handle_turnstile(tab)

    email_handler = EmailVerificationHandler(browser, MAIL_URL)

    while True:
        try:
            if tab.ele("Account Settings"):
                info("注册成功，已进入账号设置页面")
                break
            if tab.ele("@data-index=0"):
                debug("等待验证码...")
                code = email_handler.get_verification_code(account_info["email"])
                if not code:
                    error("获取验证码失败")
                    return False

                debug(f"输入验证码: {code}")
                i = 0
                for digit in code:
                    tab.ele(f"@data-index={i}").input(digit)
                    time.sleep(random.uniform(0.1, 0.3))
                    i += 1
                info("验证码输入完成")
                break
        except Exception as e:
            error(f"验证码处理失败: {str(e)}")

    debug("完成最终验证...")
    handle_turnstile(tab)
    info("账号注册流程完成")
    return True


class EmailGenerator:
    FIRST_NAMES = [
        "james",
        "john",
        "robert",
        "michael",
        "william",
        "david",
        "richard",
        "joseph",
        "thomas",
        "charles",
        "christopher",
        "daniel",
        "matthew",
        "anthony",
        "donald",
        "emma",
        "olivia",
        "ava",
        "isabella",
        "sophia",
        "mia",
        "charlotte",
        "amelia",
        "harper",
        "evelyn",
        "abigail",
        "emily",
        "elizabeth",
        "sofia",
        "madison",
    ]

    LAST_NAMES = [
        "smith",
        "johnson",
        "williams",
        "brown",
        "jones",
        "garcia",
        "miller",
        "davis",
        "rodriguez",
        "martinez",
        "hernandez",
        "lopez",
        "gonzalez",
        "wilson",
        "anderson",
        "thomas",
        "taylor",
        "moore",
        "jackson",
        "martin",
        "lee",
        "perez",
        "thompson",
        "white",
        "harris",
        "sanchez",
        "clark",
        "ramirez",
        "lewis",
        "robinson",
    ]

    def __init__(
        self,
        password="".join(
            random.choices(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*",
                k=12,
            )
        ),
        first_name=None,
        last_name=None,
    ):
        self.default_password = password
        self.default_first_name = first_name or random.choice(self.FIRST_NAMES)
        self.default_last_name = last_name or random.choice(self.LAST_NAMES)
        self.email = None

    def set_email(self, email):
        self.email = email

    def get_account_info(self):
        if not self.email:
            raise ValueError("Email address not set")
        return {
            "email": self.email,
            "password": self.default_password,
            "first_name": self.default_first_name.capitalize(),
            "last_name": self.default_last_name.capitalize(),
        }

    def _save_account_info(self, token, total_usage):
        try:
            from database import async_session, AccountModel
            import asyncio

            async def save_to_db():
                debug(f"开始保存账号信息: {self.email}")
                async with async_session() as session:
                    # 检查账号是否已存在
                    from sqlalchemy import select
                    result = await session.execute(
                        select(AccountModel).where(AccountModel.email == self.email)
                    )
                    existing_account = result.scalar_one_or_none()
                    
                    if existing_account:
                        debug("更新现有账号信息")
                        existing_account.token = token
                        existing_account.password = self.default_password
                        existing_account.usage_limit = str(total_usage)
                    else:
                        debug("创建新账号记录")
                        account = AccountModel(
                            email=self.email,
                            password=self.default_password,
                            token=token,
                            usage_limit=str(total_usage)
                        )
                        session.add(account)
                    
                    await session.commit()
                    info(f"账号 {self.email} 信息保存成功")
                    return True

            return asyncio.run(save_to_db())
        except Exception as e:
            error(f"保存账号信息失败: {str(e)}")
            return False


def cleanup_and_exit(browser_manager=None, exit_code=0):
    """清理资源并退出程序"""
    try:
        if browser_manager:
            info("正在关闭浏览器")
            browser_manager.quit()

        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except:
                pass

        info("程序正常退出")
        sys.exit(exit_code)

    except Exception as e:
        error("清理退出时发生错误:", str(e))
        sys.exit(1)


def main():
    browser_manager = None
    try:
        browser_manager = BrowserManager()
        browser = browser_manager.init_browser()

        mail_tab = browser.new_tab(MAIL_URL)
        browser.activate_tab(mail_tab)
        time.sleep(2)

        email_js = get_temp_email(mail_tab)

        email_generator = EmailGenerator()
        email_generator.set_email(email_js)
        account_info = email_generator.get_account_info()

        signup_tab = browser.new_tab(SIGN_UP_URL)
        browser.activate_tab(signup_tab)
        time.sleep(2)

        signup_tab.run_js("try { turnstile.reset() } catch(e) { }")

        if sign_up_account(browser, signup_tab, account_info):
            token = get_cursor_session_token(signup_tab)
            info("获取到账号Token:", token)
            if token:
                email_generator._save_account_info(token, TOTAL_USAGE)
            else:
                error("获取Cursor会话Token失败")
        else:
            error("注册失败")
        info("注册流程完成")
        cleanup_and_exit(browser_manager, 0)

    except Exception as e:
        error("主程序错误:", str(e))
        import traceback
        error("错误详情:", traceback.format_exc())
        cleanup_and_exit(browser_manager, 1)
    finally:
        cleanup_and_exit(browser_manager, 1)


if __name__ == "__main__":
    main()
