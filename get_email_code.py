from DrissionPage.common import Keys
import time
import re
from logger import info, error


class EmailVerificationHandler:
    def __init__(self, browser, tab):
        self.browser = browser
        self.tab = tab
        self.mail_url = tab.url if tab else None

    def get_verification_code(self, email):
        info(f"处理邮箱验证码，当前邮箱: {email}")
        code = None

        try:
            info("开始处理邮件")
            code = self._get_latest_mail_code(self.tab)

        except Exception as e:
            error(f"获取邮箱验证码失败: {str(e)}")

        return code

    def _get_latest_mail_code(self, tab):
        code = None
        retry_count = 0
        max_retries = 3

        # 特殊处理24mail.json.cm
        if "24mail.json.cm" in tab.url:
            while retry_count < max_retries:
                try:
                    # 等待并点击邮件列表中的第一个tr
                    email_row = tab.ele("css:tbody#maillist tr:first-child", timeout=2)
                    if email_row:
                        info("找到邮件，点击展开")
                        email_row.click()
                        time.sleep(2)
                        break

                    retry_count += 1
                
                except Exception as e:
                    error(f"获取邮件失败: {str(e)}")
                    time.sleep(2)
                    retry_count += 1

            if retry_count >= max_retries:
                error("未找到验证邮件")
                raise Exception("未找到验证邮件")

        info("开始获取验证码")
        max_retries = 10
        for attempt in range(max_retries):
            try:
                # 直接获取包含验证码的div
                content_td = tab.ele("css:div[style*='font-family:-apple-system'][style*='letter-spacing:2px;']", timeout=2)
                if content_td:
                    content = content_td.text
                    if content:
                        # 直接获取6位数字
                        matches = re.findall(r'\b\d{6}\b', content)
                        if matches:
                            info(f"找到验证码: {matches[0]}")
                            return matches[0]

                info("等待验证码加载...")
                time.sleep(2)

            except Exception as e:
                error(f"获取验证码失败: {str(e)}")
                time.sleep(2)

        error("未找到验证码")
        return None

    def _cleanup_mail(self, tab):
        if tab.ele("@id=delete_mail"):
            tab.actions.click("@id=delete_mail")
            time.sleep(1)

        if tab.ele("@id=confirm_mail"):
            tab.actions.click("@id=confirm_mail")
