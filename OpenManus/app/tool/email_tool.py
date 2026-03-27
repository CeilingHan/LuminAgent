from app.tool.base import BaseTool
from pydantic import Field
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

class EmailTool(BaseTool):
    name: str = "send_email"
    description: str = "发送邮件到备用邮箱，用于备份AI生成的内容"
    
    subject: str = Field(..., description="邮件标题")
    content: str = Field(..., description="邮件正文内容")
    to_email: str = Field(..., description="收件人邮箱（备用邮箱）")

    async def execute(self, subject: str, content: str, to_email: str):
        # 发件人配置（请修改为你的邮箱信息）
        from_email = "your-email@example.com"
        from_password = "your-app-password"  # 邮箱授权码/应用密码
        smtp_server = "smtp.example.com"     # SMTP服务器，如smtp.qq.com、smtp.163.com
        smtp_port = 465                     # SSL端口，通常为465

        try:
            # 构建邮件
            msg = MIMEText(content, "plain", "utf-8")
            msg["From"] = formataddr(("AI助手", from_email))
            msg["To"] = formataddr(("备用邮箱", to_email))
            msg["Subject"] = subject

            # 发送邮件
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                server.login(from_email, from_password)
                server.sendmail(from_email, [to_email], msg.as_string())
            
            return f"✅ 邮件发送成功！\n标题：{subject}\n收件人：{to_email}"
        except Exception as e:
            return f"❌ 邮件发送失败：{str(e)}"