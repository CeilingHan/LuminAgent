import React, { useState } from 'react';
import { Button, Card, message, Space, Typography, Divider } from 'antd';
import { RobotOutlined, MailOutlined } from '@ant-design/icons';

const { Title, Paragraph } = Typography;

// 这是一个独立的测试页面：只用来测试【发送邮件功能】
export default function EmailTestPage() {
  // 模拟 AI 返回的内容
  const aiReply = "这是 AI 生成的测试内容，用于发送到备用邮箱备份。";

  // 邮件确认弹窗状态
  const [confirmSend, setConfirmSend] = useState(null);

  // 点击【发送到邮箱】
  const handleSendEmail = (content) => {
    setConfirmSend({
      subject: "AI 内容备份",
      content: content,
      to_email: "your-backup-email@example.com", // <-- 改成你自己的备用邮箱
    });
  };

  // 确认 / 取消 发送
  const confirmSendEmail = async (confirm) => {
    if (!confirm) {
      setConfirmSend(null);
      return;
    }

    try {
      // 调用后端发送邮件
      const res = await fetch("http://localhost:8000/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: `发送邮件，标题：${confirmSend.subject}，内容：${confirmSend.content}，收件人：${confirmSend.to_email}`,
        }),
      });

      const data = await res.json();
      message.success(data.result || "✅ 邮件发送成功！");
    } catch (err) {
      message.error("❌ 发送失败，请检查后端是否启动");
    }

    setConfirmSend(null);
  };

  return (
    <div style={{ maxWidth: 700, margin: "50px auto", padding: 20 }}>
      <Title level={3}>📧 邮件发送测试页面（独立版）</Title>
      <Divider />

      {/* AI 回复展示 */}
      <Card
        style={{
          backgroundColor: "#fce9ff",
          borderLeft: "3px solid #9333ea",
        }}
      >
        <Space>
          <RobotOutlined />
          <strong>AI 回复</strong>
        </Space>
        <Divider style={{ margin: "4px 0" }} />
        <Paragraph>{aiReply}</Paragraph>

        {/* 发送到邮箱按钮 */}
        <Button
          type="primary"
          icon={<MailOutlined />}
          onClick={() => handleSendEmail(aiReply)}
          style={{ marginTop: 10 }}
        >
          📧 发送到备用邮箱
        </Button>
      </Card>

      {/* 确认弹窗 */}
      {confirmSend && (
        <div
          style={{
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            background: "#fff",
            padding: "24px",
            borderRadius: "12px",
            boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
            zIndex: 9999,
            width: 360,
          }}
        >
          <h3>📨 确认发送邮件？</h3>
          <p><strong>标题：</strong>{confirmSend.subject}</p>
          <p><strong>收件人：</strong>{confirmSend.to_email}</p>
          <p style={{ fontSize: 12, color: "#666" }}>
            <strong>内容预览：</strong>
            {confirmSend.content.slice(0, 50)}...
          </p>

          <Divider />
          <Space style={{ width: "100%", justifyContent: "flex-end" }}>
            <Button onClick={() => confirmSendEmail(false)}>取消</Button>
            <Button type="primary" onClick={() => confirmSendEmail(true)}>
              ✅ 确认发送
            </Button>
          </Space>
        </div>
      )}
    </div>
  );
}