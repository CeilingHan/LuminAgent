import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Upload, Card, List, Space, Typography, Divider, message } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, FileTextOutlined, PictureOutlined } from '@ant-design/icons';

const { Title, Paragraph } = Typography;

export default function Chat() {
  const [messages, setMessages] = useState([
    { id: 1, role: 'assistant', content: '你好！支持文字、粘贴图片、上传图片、PDF、文件等任意格式' },
  ]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [fileList, setFileList] = useState([]);
  const inputRef = useRef(null);

  // ======================
  // 粘贴图片监听（Ctrl+V）
  // ======================
  useEffect(() => {
    const handlePaste = (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (let item of items) {
        if (item.type.indexOf('image') !== -1) {
          const file = item.getAsFile();
          const url = URL.createObjectURL(file);
          setFileList(prev => [...prev, {
            file,
            url,
            type: 'image',
            name: 'pasted_image.png'
          }]);
          message.success('已粘贴图片');
        }
      }
    };
    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, []);

  // ======================
  // 上传文件/图片
  // ======================
  const handleUpload = (file) => {
    const url = URL.createObjectURL(file);
    const type = file.type.startsWith('image') ? 'image' : 'file';
    setFileList(prev => [...prev, { file, url, type, name: file.name }]);
    return false; // 不自动上传
  };

  // ======================
  // 统一上传到后端并发送
  // ======================
  const sendMessage = async () => {
    // ✅ 修复：先判断 inputText 是否存在，再 trim
    const text = (inputText || '').trim();
    if (!text && fileList.length === 0) return;

    // 先把用户消息显示出来
    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: text,
      files: fileList,
    };
    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setLoading(true);

    try {
      let uploadedPath = null;

      // 只取第一个文件传给AI（多文件可后续扩展）
      if (fileList.length > 0) {
        const f = fileList[0];
        const formData = new FormData();
        formData.append('file', f.file);

        const res = await fetch('http://localhost:8000/upload', {
          method: 'POST',
          body: formData,
        });
        const data = await res.json();
        uploadedPath = data.save_path;
      }

      // 发送给AI
      const res = await fetch('http://localhost:8000/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: text,
          file_path: uploadedPath,
        }),
      });

      const data = await res.json();
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.result || data.error || '执行完成',
      }]);

    } catch (err) {
      message.error('请求失败，请检查后端是否启动');
    } finally {
      setLoading(false);
      setFileList([]);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 200px)' }}>
      <Title level={3}>📎 科研多模态AI助手（文字+图片+PDF+文件）</Title>
      <Divider />

      <List
        style={{ flex: 1, overflowY: 'auto', paddingBottom: 10 }}
        dataSource={messages}
        renderItem={(item) => (
          <List.Item
            style={{
              display: 'flex',
              justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <Card
              size="small"
              style={{
                maxWidth: '75%',
                backgroundColor: item.role === 'user' ? '#e6f7ff' : '#fce9ff',
                borderLeft: item.role === 'assistant' ? '3px solid #9333ea' : 'none',
              }}
            >
              <Space align="center">
                {item.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                <strong>{item.role === 'user' ? '我' : 'AI助手'}</strong>
              </Space>
              <Divider style={{ margin: '4px 0' }} />

              {item.files?.map((f, i) =>
                f.type === 'image' ? (
                  <img
                    key={i}
                    src={f.url}
                    style={{ width: '100%', borderRadius: 6, marginBottom: 6 }}
                  />
                ) : (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <FileTextOutlined />
                    <span>{f.name}</span>
                  </div>
                )
              )}

              <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                {item.content}
              </Paragraph>
            </Card>
          </List.Item>
        )}
      />

      {/* 预览已选文件 */}
      {fileList.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
          {fileList.map((f, i) =>
            f.type === 'image' ? (
              <img key={i} src={f.url} style={{ height: 40, borderRadius: 4 }} />
            ) : (
              <div key={i} style={{ padding: '2px 8px', background: '#eee', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                <FileTextOutlined />
                {f.name}
              </div>
            )
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <Upload beforeUpload={handleUpload} showUploadList={false}>
          <Button icon={<PictureOutlined />}>文件/图片</Button>
        </Upload>

        <Input
          ref={inputRef}
          value={inputText}
          // ✅ 修复：正确获取输入框值
          onChange={(e) => setInputText(e.target.value)}
          onPressEnter={sendMessage}
          placeholder="输入指令，或粘贴图片，或上传文件…"
          style={{ flex: 1 }}
        />

        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={loading}
          onClick={sendMessage}
        >
          发送
        </Button>
      </div>
    </div>
  );
}