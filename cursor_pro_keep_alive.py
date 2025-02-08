import os
import sys
import psutil
import time
import random
from logger import info, info, warning, info

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
MAIL_URL = "https://24mail.json.cm/"
TOTAL_USAGE = 0


def handle_turnstile(tab):
    info("=============正在检测 Turnstile 验证=============")
    try:
        while True:
            try:
                if tab.ele("@name=password"):
                    info("验证成功 - 已到达密码输入页面")
                    break
                if tab.ele("@data-index=0"):
                    info("验证成功 - 已到达验证码输入页面")
                    break
                if tab.ele("Account Settings"):
                    info("验证成功 - 已到达账户设置页面")
                    break

                info("检测 Turnstile 验证...")
                challengeCheck = (
                    tab.ele("@id=cf-turnstile", timeout=2)
                    .child()
                    .shadow_root.ele("tag:iframe")
                    .ele("tag:body")
                    .sr("tag:input")
                )

                if challengeCheck:
                    info("检测到 Turnstile 验证，正在处理...")
                    time.sleep(random.uniform(1, 3))
                    challengeCheck.click()
                    time.sleep(2)
                    info("Turnstile 验证通过")
                    return True
            except:
                pass

            time.sleep(random.uniform(1, 2))
    except Exception as e:
        info(f"Turnstile 验证失败: {str(e)}")
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
            info(f"使用限制: {total_usage}")

        info("获取Cookie中...")
        attempts = 0

        while attempts < max_attempts:
            try:
                cookies = tab.cookies()
                for cookie in cookies:
                    if cookie.get("name") == "WorkosCursorSessionToken":
                        user = cookie["value"].split("%3A%3A")[0]
                        token = cookie["value"].split("%3A%3A")[1]
                        info(f"获取到账号Token: {token}, 用户: {user}")
                        return token, user

                attempts += 1
                if attempts < max_attempts:
                    warning("未找到Cursor会话Token，重试中...")
                    time.sleep(retry_interval)
                else:
                    info("未找到Cursor会话Token")

            except Exception as e:
                info(str(e))
                attempts += 1
                if attempts < max_attempts:
                    info(f"重试获取Token，等待时间: {retry_interval}")
                    time.sleep(retry_interval)

        return False

    except Exception as e:
        warning(f"获取Token过程出错: {str(e)}")
        return False


def get_selector_for_url(url):
    if "22.do" in url:
        return "css:p.text-email"
    elif "24mail.json.cm" in url:
        return "css:input#shortid"
    elif "internxt.com" in url:
        return "css:p[data-relingo-block='true']"
    elif "spambox.xyz" in url:
        return "css:div#email_id"
    return None


def get_email_value(element, url):
    if "24mail.json.cm" in url:
        # 对于 24mail.json.cm，直接从 input 元素获取值
        value = element.value
        if value:
            return value
        try:
            # 尝试使用 JavaScript 获取值
            value = element.run_js("return this.value")
            if value:
                return value
        except:
            pass
        return element.attr("value")
    return element.text


def change_email(tab):
    try:
        # 点击 Change 按钮切换邮箱
        change_button = tab.ele("css:div#idChange")
        if change_button:
            change_button.click()
            time.sleep(2)  # 等待新邮箱生成
            return True
        return False
    except Exception as e:
        info(f"切换邮箱失败: {str(e)}")
        return False


def get_temp_email(tab):
    max_retries = 15
    last_email = None
    stable_count = 0

    info("=============等待获取临时邮箱=============")

    # 根据URL选择对应的选择器
    selector = get_selector_for_url(tab.url)
    info(f"获取到选择器: {selector}")
    if not selector:
        raise ValueError("不支持的邮箱服务提供商")

    for i in range(max_retries):
        try:
            email_element = tab.ele(selector, timeout=3)
            if email_element:

                # 尝试获取邮箱值
                current_email = get_email_value(email_element, tab.url)
                if current_email and "@" in current_email:
                    if current_email == last_email:
                        stable_count += 1
                        if stable_count >= 2:
                            info("成功获取邮箱")
                            return current_email
                    else:
                        stable_count = 0
                        last_email = current_email
                        info(f"当前邮箱: {current_email}")

            info("等待邮箱分配")
            time.sleep(2)  # 增加等待时间

        except Exception as e:
            warning(f"获取邮箱出错: {str(e)}")
            time.sleep(2)  # 增加等待时间
            stable_count = 0

    info("=============未能获取邮箱=============")
    raise ValueError("未能获取邮箱")


def sign_up_account(browser, tab, account_info, mail_tab):
    info("=============开始注册账号=============")
    info(
        f"账号信息: 邮箱: {account_info['email']}, 姓名: {account_info['first_name']} {account_info['last_name']}"
    )
    tab.get(SIGN_UP_URL)
    try:
        if tab.ele("@name=first_name"):
            info("=============正在填写个人信息=============")
            tab.actions.click("@name=first_name").input(account_info["first_name"])
            info(f"已输入名字: {account_info['first_name']}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=last_name").input(account_info["last_name"])
            info(f"已输入姓氏: {account_info['last_name']}")
            time.sleep(random.uniform(1, 3))

            tab.actions.click("@name=email").input(account_info["email"])
            info(f"已输入邮箱: {account_info['email']}")
            time.sleep(random.uniform(1, 3))

            info("=============提交个人信息=============")
            tab.actions.click("@type=submit")

    except Exception as e:
        info(f"填写个人信息失败: {str(e)}")
        return "ERROR"

    handle_turnstile(tab)

    if tab.ele("Can‘t verify the user is human. Please try again.") or tab.ele(
        "Can't verify the user is human. Please try again."
    ):
        info("检测到turnstile验证失败，正在重试...")
        return "EMAIL_USED"

    try:
        if tab.ele("@name=password"):
            info("设置密码...")
            tab.ele("@name=password").input(account_info["password"])
            time.sleep(random.uniform(1, 2))

            info("提交密码...")
            tab.ele("@type=submit").click()
            info("密码设置成功,等待系统响应....")

            # if tab.ele("This email is not available"):
            #     info("邮箱已被使用")
            #     return "EMAIL_USED"

            # if tab.ele("Sign up is restricted."):
            #     info("注册限制")
            #     return "SIGNUP_RESTRICTED"

            # if tab.ele("Unable to verify the user is human"):
            #     info("需要更换邮箱")
            #     return "VERIFY_FAILED"

    except Exception as e:
        info(f"密码设置失败: {str(e)}")
        return "ERROR"

    info("处理最终验证...")
    handle_turnstile(tab)

    if tab.ele("This email is not available."):
        info("邮箱已被使用")
        return "EMAIL_USED"

    if tab.ele("Sign up is restricted."):
        info("注册限制")
        return "SIGNUP_RESTRICTED"

    # 创建邮件处理器，使用mail_tab
    email_handler = EmailVerificationHandler(browser, mail_tab)

    while True:
        info("等待注册成功...")
        try:
            if tab.ele("Account Settings"):
                info("注册成功，已进入账号设置页面")
                break
            if tab.ele("@data-index=0"):
                info("等待验证码...")
                # 切换到邮箱标签页
                browser.activate_tab(mail_tab)
                code = email_handler.get_verification_code(account_info["email"])
                if not code:
                    info("获取验证码失败")
                    return "ERROR"

                # 切换回注册标签页
                browser.activate_tab(tab)
                info(f"输入验证码: {code}")
                i = 0
                for digit in code:
                    tab.ele(f"@data-index={i}").input(digit)
                    time.sleep(random.uniform(0.3, 0.6))
                    i += 1
                info("验证码输入完成")
                time.sleep(random.uniform(3, 5))
                break
        except Exception as e:
            info(f"验证码处理失败: {str(e)}")
            return "ERROR"

    info("完成最终验证...")
    handle_turnstile(tab)
    time.sleep(random.uniform(3, 5))
    info("账号注册流程完成")
    return "SUCCESS"


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

    def _save_account_info(self, user, token, total_usage):
        try:
            from database import get_session, AccountModel
            import asyncio

            async def save_to_db():
                info(f"开始保存账号信息: {self.email}")
                async with get_session() as session:
                    # 检查账号是否已存在
                    from sqlalchemy import select

                    result = await session.execute(
                        select(AccountModel).where(AccountModel.email == self.email)
                    )
                    existing_account = result.scalar_one_or_none()

                    if existing_account:
                        info("更新现有账号信息")
                        existing_account.token = token
                        existing_account.user = user
                        existing_account.password = self.default_password
                        existing_account.usage_limit = str(total_usage)
                    else:
                        info("创建新账号记录")
                        account = AccountModel(
                            email=self.email,
                            password=self.default_password,
                            token=token,
                            user=user,
                            usage_limit=str(total_usage),
                        )
                        session.add(account)

                    await session.commit()
                    info(f"账号 {self.email} 信息保存成功")
                    return True

            return asyncio.run(save_to_db())
        except Exception as e:
            info(f"保存账号信息失败: {str(e)}")
            return False


def cleanup_and_exit(browser_manager=None, exit_code=0):
    """清理资源并退出程序"""
    try:
        if browser_manager:
            info("正在关闭浏览器")
            if hasattr(browser_manager, "browser"):
                browser_manager.browser.quit()

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
        info(f"清理退出时发生错误: {str(e)}")
        sys.exit(1)


def main():
    browser_manager = None
    max_retries = 3  # 最大重试次数
    current_retry = 0

    try:
        browser_manager = BrowserManager()
        browser = browser_manager.init_browser()

        while current_retry < max_retries:
            try:
                mail_tab = browser.new_tab(MAIL_URL)
                browser.activate_tab(mail_tab)
                time.sleep(2)

                email_js = get_temp_email(mail_tab)

                email_generator = EmailGenerator()
                email_generator.set_email(email_js)
                account_info = email_generator.get_account_info()

                signup_tab = browser.new_tab(LOGIN_URL)
                browser.activate_tab(signup_tab)

                signup_tab.run_js("try { turnstile.reset() } catch(e) { }")
                result = sign_up_account(browser, signup_tab, account_info, mail_tab)

                if result == "SUCCESS":
                    token, user = get_cursor_session_token(signup_tab)
                    info(f"获取到账号Token: {token}, 用户: {user}")
                    if token:
                        email_generator._save_account_info(user, token, TOTAL_USAGE)
                        info("注册流程完成")
                        cleanup_and_exit(browser_manager, 0)
                    else:
                        info("获取Cursor会话Token失败")
                        current_retry += 1
                elif result in ["EMAIL_USED", "SIGNUP_RESTRICTED", "VERIFY_FAILED"]:
                    info(f"遇到问题: {result}，尝试切换邮箱...")
                    browser.activate_tab(mail_tab)  # 切换到邮箱标签页
                    if change_email(mail_tab):
                        new_email = get_temp_email(mail_tab)
                        if new_email:
                            info(f"成功切换到新邮箱: {new_email}")
                            account_info["email"] = new_email
                            browser.activate_tab(signup_tab)  # 切换回注册标签页
                            continue  # 使用新邮箱重试注册
                    info("切换邮箱失败，准备重试...")
                    current_retry += 1
                else:  # ERROR
                    info("遇到错误，准备重试...")
                    current_retry += 1

                # 关闭标签页，准备下一次尝试
                signup_tab.close()
                mail_tab.close()
                time.sleep(2)

            except Exception as e:
                info(f"当前尝试发生错误: {str(e)}")
                current_retry += 1
                time.sleep(2)
                try:
                    # 尝试关闭可能存在的标签页
                    if "signup_tab" in locals():
                        signup_tab.close()
                    if "mail_tab" in locals():
                        mail_tab.close()
                except:
                    pass

        info(f"达到最大重试次数 {max_retries}，注册失败")
        cleanup_and_exit(browser_manager, 1)

    except Exception as e:
        info(f"主程序错误: {str(e)}")
        import traceback

        info(f"错误详情: {traceback.format_exc()}")
        cleanup_and_exit(browser_manager, 1)
    finally:
        cleanup_and_exit(browser_manager, 1)


if __name__ == "__main__":
    main()
