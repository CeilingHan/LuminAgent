import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Upload, Card, List, Space, Typography, Divider, message } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, FileTextOutlined, PictureOutlined } from '@ant-design/icons';
import { DownloadOutlined, SearchOutlined, ExperimentOutlined } from '@ant-design/icons';
import { Tag } from 'antd';
const { Title, Paragraph } = Typography;

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';

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
const sendMessage = async () => {
  const text = (inputText || '').trim();
  if (!text && fileList.length === 0) return;

  // 先声明所有 id
  const now = Date.now();
  const userMsgId = now;
  const assistantId = now + 1;

  // 一次性插入用户消息和空的 assistant 消息
  setMessages(prev => [...prev,
    { id: userMsgId, role: 'user', content: text, files: fileList },
    { id: assistantId, role: 'assistant', content: '' }
  ]);

  setInputText('');
  setFileList([]);
  setLoading(true);

  try {
    let uploadedPath = null;

    if (fileList.length > 0) {
      const f = fileList[0];
      const formData = new FormData();
      formData.append('file', f.file);
      const res = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      uploadedPath = data.save_path;
    }

    const res = await fetch(`${API_BASE_URL}/execute/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: text, file_path: uploadedPath }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const parsed = JSON.parse(line.slice(6));
          if (parsed.type === 'text') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + parsed.content }
                : msg
            ));
          } else if (parsed.type === 'status') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, content: parsed.content }
                : msg
            ));
          } else if (parsed.type === 'error') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, content: '❌ ' + parsed.content }
                : msg
            ));
          }
        } catch {}
      }
    }

  } catch (err) {
    message.error('请求失败，请检查后端是否启动');
  } finally {
    setLoading(false);
  }
};
const runPipeline = async () => {
  if (fileList.length === 0) {
    message.warning('请先上传PDF文献');
    return;
  }

  const now = Date.now();
  const assistantId = now + 1;

  setMessages(prev => [...prev,
    { id: now, role: 'user', content: '🔬 启动全套科研分析流水线', files: fileList },
    { id: assistantId, role: 'assistant', content: '',
      searchResults: [], stageText: '', pptxUrl: null }
  ]);
  setFileList([]);
  setLoading(true);

  try {
    const f = fileList[0];
    const formData = new FormData();
    formData.append('file', f.file);
    const upRes = await fetch(`${API_BASE_URL}/upload`, {
      method: 'POST', body: formData
    });
    const upData = await upRes.json();

    const res = await fetch(`${API_BASE_URL}/research/pipeline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: upData.save_path }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const parsed = JSON.parse(line.slice(6));

          if (parsed.type === 'text') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + parsed.content }
                : msg
            ));
          } else if (parsed.type === 'stage') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, stageText: parsed.content }
                : msg
            ));
          } else if (parsed.type === 'search_result') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, searchResults: [...(msg.searchResults || []), parsed] }
                : msg
            ));
          } else if (parsed.type === 'related') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, relatedWork: (msg.relatedWork || '') + parsed.content }
                : msg
            ));
          } else if (parsed.type === 'pptx') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg,
                    pptxUrl: `${API_BASE_URL}/download/${parsed.filename}`,
                    pptxName: parsed.filename }
                : msg
            ));
          }
        } catch {}
      }
    }
  } catch (err) {
    message.error('流水线执行失败');
  } finally {
    setLoading(false);
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
              {/* 当前阶段状态 */}
{item.stageText && (
  <div style={{
    background: '#1a1a3a', borderRadius: 6, padding: '6px 12px',
    marginBottom: 8, color: '#6C63FF', fontWeight: 'bold'
  }}>
    {item.stageText}
  </div>
)}

{/* 搜索结果卡片，逐条弹出 */}
{item.searchResults?.map((sr, i) => (
  <div key={i} style={{
    background: '#1e1e3a', borderRadius: 8, padding: 10,
    marginBottom: 8, borderLeft: '3px solid #00D4FF'
  }}>
    <div style={{ color: '#00D4FF', fontSize: 12, marginBottom: 4 }}>
      <SearchOutlined /> {sr.query}
    </div>
    {sr.results?.map((r, j) => (
      <div key={j} style={{ marginBottom: 4 }}>
        <a href={r.url} target="_blank" rel="noreferrer"
           style={{ color: '#6C63FF', fontSize: 13 }}>
          {r.title}
        </a>
        <div style={{ color: '#aaa', fontSize: 11 }}>{r.desc}</div>
      </div>
    ))}
  </div>
))}

{/* 相关工作总结 */}
{item.relatedWork && (
  <div style={{
    background: '#1a2a1a', borderRadius: 8, padding: 10,
    marginBottom: 8, borderLeft: '3px solid #00FF88'
  }}>
    <div style={{ color: '#00FF88', fontSize: 12, marginBottom: 4 }}>
      📚 相关工作总结
    </div>
    <div style={{ color: '#ccc', fontSize: 14, whiteSpace: 'pre-wrap' }}>
      {item.relatedWork}
    </div>
  </div>
)}

{/* PPT 下载按钮 */}
{item.pptxUrl && (
  <div style={{ marginTop: 10 }}>
    <a href={item.pptxUrl} download={item.pptxName}>
      <Button
        type="primary"
        icon={<DownloadOutlined />}
        style={{ background: '#6C63FF', border: 'none' }}
      >
        📊 下载分析PPT
      </Button>
    </a>
  </div>
)}

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
        icon={<ExperimentOutlined />}
        loading={loading}
        onClick={runPipeline}
        style={{ background: '#6C63FF', color: '#fff', border: 'none' }}
      >
        全套分析
      </Button>

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
