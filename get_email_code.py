from DrissionPage.common import Keys
import time
import re
from logger import info, error


class EmailVerificationHandler:
    def __init__(self, browser, mail_url):
        self.browser = browser
        self.mail_url = mail_url

    def get_verification_code(self, email):
        info(f"处理邮箱验证码，当前邮箱: {email}")
        code = None

        try:
            info("开始处理邮件")
            tab_mail = self.browser.new_tab(self.mail_url)
            self.browser.activate_tab(tab_mail)

            code = self._get_latest_mail_code(tab_mail)

            # self._cleanup_mail(tab_mail)

            tab_mail.close()

        except Exception as e:
            error(f"获取邮箱验证码失败: {str(e)}")

        return code

    def _get_latest_mail_code(self, tab):
        code = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                email_row = tab.ele("css:tbody > tr.border-b.cursor-pointer", timeout=2)
                if email_row:
                    subject_cell = email_row.ele("css:td:nth-child(2)")
                    if subject_cell and "Verify your email address" in subject_cell.text:
                        info("找到验证邮件")
                        email_row.click()
                        time.sleep(2)
                        break

                info("等待邮件加载...")
                time.sleep(2)
                tab.refresh()
                time.sleep(3)
                retry_count += 1
            
            except Exception as e:
                error(f"获取邮件失败: {str(e)}")
                time.sleep(2)
                retry_count += 1

        if retry_count >= max_retries:
            error("未找到验证邮件")
            raise Exception("未找到验证邮件")

        max_retries = 10
        for attempt in range(max_retries):
            try:
                content_td = tab.ele("css:td.px-3.text-black.text-base", timeout=2)
                if content_td:
                    content = content_td.text
                    if content:
                        matches = re.findall(r'\b\d{6}\b', content)
                        for match in matches:
                            if "verification code" in content.lower() or "verify" in content.lower():
                                info(f"找到验证码: {match}")
                                return match

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
