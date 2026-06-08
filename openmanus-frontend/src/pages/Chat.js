import React, { useState, useRef, useEffect } from 'react';
import { Input, Button, Upload, Card, List, Space, Typography, Divider, message, Switch, Modal } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, FileTextOutlined, PictureOutlined } from '@ant-design/icons';
import { DownloadOutlined, SearchOutlined, ExperimentOutlined, ThunderboltOutlined, CodeOutlined, ProjectOutlined } from '@ant-design/icons';
import { Tag, Drawer } from 'antd';
import { CloseOutlined, LinkOutlined, ExpandOutlined } from '@ant-design/icons';
const { Title, Paragraph, Text } = Typography;

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';

export default function Chat() {
  const [messages, setMessages] = useState([
    { id: 1, role: 'assistant', content: '你好！支持文字、粘贴图片、上传图片、PDF、文件等任意格式。\n🔥 Agent 模式：自动搜索网络 → 总结回答 → 附参考链接\n📋 Plan 模式：制定执行计划 → 逐步完成任务 → 生成总结\n🐍 点击 Python 按钮编写并执行 Python 代码' },
  ]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [fileList, setFileList] = useState([]);
  const [agentMode, setAgentMode] = useState(false);  // Agent模式开关
  const [planMode, setPlanMode] = useState(false);    // Plan模式开关
  const inputRef = useRef(null);

  // ── Skill 选择器状态 ──
  const [activeSkill, setActiveSkill] = useState(null);       // 当前选中的 skill
  const [allSkills, setAllSkills] = useState([]);             // 所有可用 skill (custom + tools)
  const [showSkillDropdown, setShowSkillDropdown] = useState(false);
  const [skillSearch, setSkillSearch] = useState('');         // / 后面的搜索文本
  const dropdownRef = useRef(null);

  // ── Python 代码编辑器状态 ──
  const [codeModalVisible, setCodeModalVisible] = useState(false);
  const [pyCode, setPyCode] = useState('# 在此编写 Python 代码\n# 例如：\nprint("Hello, World!")\nprint(1 + 2 * 3)\n');
  const [pyTimeout, setPyTimeout] = useState(10);

  // ── 右侧详情面板状态 ──
  const [detailPanel, setDetailPanel] = useState(null); // null | single result item
  const [searchListPanel, setSearchListPanel] = useState(null); // null | {query, results: [...]}

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
  // 加载 Skills (用于 / 快捷选择)
  // ======================
  useEffect(() => {
    const loadSkills = async () => {
      try {
        // Load custom skills + built-in tools
        const [skillRes, toolRes] = await Promise.all([
          fetch(`${API_BASE_URL}/skills`),
          fetch(`${API_BASE_URL}/`),
        ]);
        const skillData = await skillRes.json();
        const toolData = await toolRes.json();
        const skills = [];
        // Custom skills
        if (skillData.success) {
          (skillData.data || []).forEach(s => skills.push({
            name: s.name,
            description: s.description || '自定义技能',
            type: 'skill',
            trigger_keywords: s.trigger_keywords,
            tools: s.tools,
          }));
        }
        // Built-in tools
        (toolData.skills || []).forEach(t => {
          skills.push({
            name: t.id,
            description: t.description || '内置工具',
            type: 'tool',
            available: t.available,
          });
        });
        setAllSkills(skills);
      } catch {}
    };
    loadSkills();
  }, []);

  // ── 点击外部关闭 Skill 下拉 ──
  useEffect(() => {
    const handleClick = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowSkillDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
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
    { id: assistantId, role: 'assistant', content: '', searchResults: [], stageText: '', toolCalls: [] }
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

    // 🔥 Plan模式：走 /plan/stream，先计划再执行
    // 🔥 Agent模式：走 /agent/stream，支持浏览器/搜索等工具调用
    // 普通模式：走 /execute/stream，纯文本对话
    const endpoint = planMode
      ? `${API_BASE_URL}/plan/stream`
      : agentMode
        ? `${API_BASE_URL}/agent/stream`
        : `${API_BASE_URL}/execute/stream`;

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: text, file_path: uploadedPath, max_steps: 15, skill_name: activeSkill?.name || '' }),
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
                ? { ...msg, stageText: parsed.content }
                : msg
            ));
          } else if (parsed.type === 'tool_call') {
            // Agent 决定调用的工具
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, toolCalls: [...(msg.toolCalls || []), ...parsed.tools.map((t, i) => `${t}(${parsed.args[i] || ''})`)] }
                : msg
            ));
          } else if (parsed.type === 'tool_result') {
            // 工具执行结果
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, toolResult: parsed.content }
                : msg
            ));
          } else if (parsed.type === 'error') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + '\n❌ ' + parsed.content }
                : msg
            ));
          } else if (parsed.type === 'search_result') {
            // 🔥 自动预搜索结果（不开浏览器）
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, searchResults: [...(msg.searchResults || []), parsed] }
                : msg
            ));
          } else if (parsed.type === 'plan_created') {
            // 📋 Plan mode: 计划已生成
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, plan: { plan_id: parsed.plan_id, title: parsed.title, steps: (parsed.steps || []).map(s => ({ text: s.text, status: s.status })) } }
                : msg
            ));
          } else if (parsed.type === 'step_start') {
            // 📋 Plan mode: 步骤开始执行
            setMessages(prev => prev.map(msg => {
              if (msg.id !== assistantId || !msg.plan) return msg;
              const newSteps = msg.plan.steps.map((s, i) =>
                i === parsed.step_index ? { ...s, status: 'in_progress' } : s
              );
              return { ...msg, plan: { ...msg.plan, steps: newSteps } };
            }));
          } else if (parsed.type === 'step_completed') {
            // 📋 Plan mode: 步骤执行完成
            setMessages(prev => prev.map(msg => {
              if (msg.id !== assistantId || !msg.plan) return msg;
              const newSteps = msg.plan.steps.map((s, i) =>
                i === parsed.step_index ? { ...s, status: 'completed' } : s
              );
              return { ...msg, plan: { ...msg.plan, steps: newSteps } };
            }));
          } else if (parsed.type === 'step_error') {
            // 📋 Plan mode: 步骤执行失败
            setMessages(prev => prev.map(msg => {
              if (msg.id !== assistantId || !msg.plan) return msg;
              const newSteps = msg.plan.steps.map((s, i) =>
                i === parsed.step_index ? { ...s, status: 'error' } : s
              );
              return { ...msg, plan: { ...msg.plan, steps: newSteps } };
            }));
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

// ======================
// Python 代码直接执行
// ======================
const runPythonCode = async () => {
  const code = (pyCode || '').trim();
  if (!code) {
    message.warning('请输入 Python 代码');
    return;
  }

  setCodeModalVisible(false);

  const now = Date.now();
  const userMsgId = now;
  const assistantId = now + 1;

  setMessages(prev => [...prev,
    { id: userMsgId, role: 'user', content: '🐍 执行 Python 代码：\n```python\n' + code + '\n```' },
    { id: assistantId, role: 'assistant', content: '', searchResults: [], stageText: '', toolCalls: [] }
  ]);

  setLoading(true);

  try {
    const res = await fetch(`${API_BASE_URL}/execute/python`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code, timeout: pyTimeout }),
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
                ? { ...msg, stageText: parsed.content }
                : msg
            ));
          } else if (parsed.type === 'tool_result') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, toolResult: parsed.content }
                : msg
            ));
          } else if (parsed.type === 'tool_call') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, toolCalls: [...(msg.toolCalls || []), ...parsed.tools.map((t, i) => `${t}(${parsed.args[i] || ''})`)] }
                : msg
            ));
          } else if (parsed.type === 'error') {
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + '\n❌ ' + parsed.content }
                : msg
            ));
          }
        } catch {}
      }
    }

    // Reset code editor to a fresh template
    setPyCode('# 在此编写 Python 代码\n# 例如：\nprint("Hello, World!")\nprint(1 + 2 * 3)\n');

  } catch (err) {
    message.error('Python 执行请求失败，请检查后端是否启动');
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

              {/* ── 工具调用标签 ── */}
              {item.toolCalls?.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  {item.toolCalls.map((tc, i) => (
                    <Tag key={i} color="purple" icon={<ThunderboltOutlined />} style={{ marginBottom: 4 }}>
                      🛠️ {tc}
                    </Tag>
                  ))}
                </div>
              )}

              {/* ── 工具执行结果 (隐藏 web_search 的上下文文本，仅展示代码执行等) ── */}
              {item.toolResult && !(item.searchResults?.length > 0) && (
                <div style={{
                  marginTop: 10,
                  background: '#f8f9fa',
                  borderRadius: 8,
                  border: '1px solid #e0e0e0',
                  borderLeft: '3px solid #52c41a',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    background: '#f0f9eb',
                    padding: '4px 12px',
                    fontSize: 11,
                    color: '#389e0d',
                    fontWeight: 600,
                    borderBottom: '1px solid #d9f7be',
                  }}>
                    ✅ 执行结果
                  </div>
                  <pre style={{
                    margin: 0,
                    padding: '10px 14px',
                    fontFamily: '"Fira Code", "SF Mono", "Menlo", "Consolas", monospace',
                    fontSize: 12.5,
                    lineHeight: 1.55,
                    color: '#1f1f1f',
                    background: 'white',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    maxHeight: 280,
                    overflow: 'auto',
                  }}>
                    {item.toolResult}
                  </pre>
                </div>
              )}

              {/* ── Plan Card ── */}
              {item.plan && (() => {
                const completed = item.plan.steps.filter(s => s.status === 'completed').length;
                const total = item.plan.steps.length;
                return (
                  <div style={{
                    marginTop: 10,
                    background: 'linear-gradient(135deg, #f6ffed 0%, #f0fff0 100%)',
                    borderRadius: 10,
                    border: '1px solid #b7eb8f',
                    padding: '14px 16px',
                  }}>
                    <div style={{
                      fontSize: 14, fontWeight: 600, color: '#389e0d',
                      marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6,
                    }}>
                      📋 {item.plan.title}
                    </div>
                    {item.plan.steps.map((step, i) => {
                      const statusIcons = {
                        completed: '✅',
                        in_progress: '🔄',
                        error: '❌',
                      };
                      const icon = statusIcons[step.status] || '○';
                      const colors = {
                        completed: { bg: '#f6ffed', border: '#b7eb8f', text: '#8c8c8c', decoration: 'line-through' },
                        in_progress: { bg: '#e6f7ff', border: '#91caff', text: '#1f1f1f', decoration: 'none' },
                        error: { bg: '#fff2f0', border: '#ffccc7', text: '#cf1322', decoration: 'none' },
                      };
                      const c = colors[step.status] || { bg: '#fafafa', border: '#f0f0f0', text: '#1f1f1f', decoration: 'none' };
                      return (
                        <div key={i} style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          padding: '6px 10px', marginBottom: 4,
                          background: c.bg, borderRadius: 6,
                          border: `1px solid ${c.border}`, fontSize: 13,
                        }}>
                          <span style={{ fontSize: 14, flexShrink: 0 }}>{icon}</span>
                          <span style={{
                            color: c.text, flex: 1,
                            textDecoration: c.decoration,
                          }}>
                            {i + 1}. {step.text}
                          </span>
                        </div>
                      );
                    })}
                    <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                      进度: {completed}/{total}
                      <div style={{
                        flex: 1, height: 4, background: '#f0f0f0', borderRadius: 2, overflow: 'hidden',
                      }}>
                        <div style={{
                          height: '100%', width: `${total > 0 ? (completed / total) * 100 : 0}%`,
                          background: 'linear-gradient(90deg, #52c41a, #73d13d)',
                          borderRadius: 2, transition: 'width 0.3s ease',
                        }} />
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* ── 当前阶段状态 ── */}
              {item.stageText && (
                <div style={{
                  background: '#f0f5ff', borderRadius: 6, padding: '6px 12px',
                  marginBottom: 6, marginTop: 4, color: '#2f54eb',
                  fontWeight: 500, fontSize: 13, border: '1px solid #d6e4ff',
                }}>
                  {item.stageText}
                </div>
              )}

              {/* ── 搜索结果浮窗按钮 (不在 chat 中显示长列表) ── */}
              {item.searchResults?.length > 0 && (() => {
                // Flatten all results across all search batches
                const all = item.searchResults.flatMap(sr => sr.results || []);
                const queries = item.searchResults.map(sr => sr.query).join(' + ');
                const totalResults = all.length;
                const domains = [...new Set((all.map(r => {
                  try { return new URL(r.url).hostname.replace('www.', ''); } catch { return ''; }
                }).filter(Boolean)))];
                if (totalResults === 0) return null;

                return (
                  <div
                    onClick={() => setSearchListPanel({ query: queries, results: all })}
                    style={{
                      marginTop: 10,
                      padding: '10px 14px',
                      background: 'linear-gradient(135deg, #e6f4ff 0%, #f0f5ff 100%)',
                      borderRadius: 10,
                      border: '1px solid #91caff',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'linear-gradient(135deg, #bae0ff 0%, #d6e4ff 100%)';
                      e.currentTarget.style.boxShadow = '0 2px 8px rgba(22,119,255,0.2)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'linear-gradient(135deg, #e6f4ff 0%, #f0f5ff 100%)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    <div style={{
                      background: '#1677ff', color: '#fff', borderRadius: '50%',
                      width: 36, height: 36, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', flexShrink: 0,
                    }}>
                      <SearchOutlined style={{ fontSize: 16 }} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#1677ff' }}>
                        找到 {totalResults} 条搜索结果
                      </div>
                      <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 1 }}>
                        来自 {domains.length} 个来源 · 查询: {queries.length > 40 ? queries.slice(0, 40) + '...' : queries}
                      </div>
                    </div>
                    <Tag color="blue" style={{ margin: 0 }}>点击查看详情</Tag>
                  </div>
                );
              })()}

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

        {/* Skill 选择器 + 输入框 */}
        <div style={{ flex: 1, position: 'relative' }} ref={dropdownRef}>
          {/* 已选 Skill 标签放在输入框上方 */}
          {activeSkill && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '2px 4px', marginBottom: 2,
            }}>
              <Tag
                closable
                onClose={() => { setActiveSkill(null); }}
                color={activeSkill.type === 'tool' ? 'purple' : 'orange'}
                icon={activeSkill.type === 'tool' ? <ThunderboltOutlined /> : null}
              >
                /{activeSkill.name}
              </Tag>
              <Text type="secondary" style={{ fontSize: 11 }}>{activeSkill.description?.slice(0, 50)}</Text>
            </div>
          )}

          {/* Skill 下拉菜单 */}
          {showSkillDropdown && (
            <div style={{
              position: 'absolute', bottom: '100%', left: 0, right: 0,
              marginBottom: 4, maxHeight: 280, overflow: 'auto',
              background: '#fff', borderRadius: 10,
              border: '1px solid #e0e0e0', boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
              zIndex: 1000,
            }}>
              {/* 分组标题 */}
              {(() => {
                const filtered = skillSearch
                  ? allSkills.filter(s =>
                      s.name.toLowerCase().includes(skillSearch.toLowerCase()) ||
                      (s.description || '').toLowerCase().includes(skillSearch.toLowerCase()))
                  : allSkills;
                const customSkills = filtered.filter(s => s.type === 'skill');
                const builtinTools = filtered.filter(s => s.type === 'tool');
                return (
                  <>
                    {/* 自定义技能 */}
                    {customSkills.length > 0 && (
                      <div>
                        <div style={{ padding: '6px 14px', fontSize: 10, color: '#bfbfbf', fontWeight: 600, textTransform: 'uppercase' }}>
                          📦 自定义技能
                        </div>
                        {customSkills.map(s => (
                          <div key={s.name} style={{
                            padding: '8px 14px', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: 8,
                            borderBottom: '1px solid #fafafa',
                          }}
                            onMouseEnter={(e) => e.currentTarget.style.background = '#fff7e6'}
                            onMouseLeave={(e) => e.currentTarget.style.background = '#fff'}
                            onClick={() => {
                              setActiveSkill(s);
                              setShowSkillDropdown(false);
                              setSkillSearch('');
                              // Remove the / from inputText
                              const idx = inputText.lastIndexOf('/');
                              if (idx >= 0) {
                                setInputText(inputText.slice(0, idx));
                              }
                            }}
                          >
                            <span style={{ fontSize: 14, fontWeight: 600, color: '#fa8c16' }}>/</span>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: 13, fontWeight: 600 }}>{s.name}</div>
                              <div style={{ fontSize: 11, color: '#8c8c8c' }}>{s.description}</div>
                              {s.trigger_keywords?.length > 0 && (
                                <div style={{ marginTop: 2 }}>
                                  {s.trigger_keywords.slice(0, 3).map(kw => (
                                    <Tag key={kw} style={{ fontSize: 9, padding: '0 4px', marginRight: 2 }}>{kw}</Tag>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 内置工具 */}
                    {builtinTools.length > 0 && (
                      <div>
                        <div style={{ padding: '6px 14px', fontSize: 10, color: '#bfbfbf', fontWeight: 600, textTransform: 'uppercase' }}>
                          🔧 内置工具
                        </div>
                        {builtinTools.map(t => (
                          <div key={t.name} style={{
                            padding: '8px 14px', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: 8,
                            borderBottom: '1px solid #fafafa',
                            opacity: t.available !== false ? 1 : 0.4,
                          }}
                            onMouseEnter={(e) => { if (t.available !== false) e.currentTarget.style.background = '#f9f0ff'; }}
                            onMouseLeave={(e) => e.currentTarget.style.background = '#fff'}
                            onClick={() => {
                              if (t.available === false) return;
                              setActiveSkill(t);
                              setShowSkillDropdown(false);
                              setSkillSearch('');
                              const idx = inputText.lastIndexOf('/');
                              if (idx >= 0) {
                                setInputText(inputText.slice(0, idx));
                              }
                            }}
                          >
                            <span style={{ fontSize: 14, fontWeight: 600, color: '#722ed1' }}>/</span>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: 13, fontWeight: 600 }}>
                                {t.name}
                                {t.available === false && <Tag color="error" style={{ marginLeft: 4, fontSize: 9 }}>OFF</Tag>}
                              </div>
                              <div style={{ fontSize: 11, color: '#8c8c8c' }}>{t.description}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {filtered.length === 0 && (
                      <div style={{ padding: '16px 14px', textAlign: 'center', color: '#bfbfbf', fontSize: 13 }}>
                        没有匹配的技能
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          )}

          <Input
            ref={inputRef}
            value={inputText}
            onChange={(e) => {
              const val = e.target.value;
              setInputText(val);
              // Detect / to show skill dropdown
              if (val.endsWith('/')) {
                setShowSkillDropdown(true);
                setSkillSearch('');
              } else if (showSkillDropdown) {
                const lastSlashIdx = val.lastIndexOf('/');
                if (lastSlashIdx >= 0) {
                  // Keep dropdown open, update search
                  const search = val.slice(lastSlashIdx + 1);
                  if (search.includes(' ')) {
                    setShowSkillDropdown(false);
                  } else {
                    setSkillSearch(search);
                  }
                } else {
                  setShowSkillDropdown(false);
                }
              }
            }}
            onPressEnter={(e) => {
              if (showSkillDropdown) {
                // If dropdown is open and user presses Enter, select first match
                const filtered = skillSearch
                  ? allSkills.filter(s =>
                      s.name.toLowerCase().includes(skillSearch.toLowerCase()) ||
                      (s.description || '').toLowerCase().includes(skillSearch.toLowerCase()))
                  : allSkills;
                if (filtered.length > 0) {
                  const first = filtered[0];
                  setActiveSkill(first);
                  setShowSkillDropdown(false);
                  setSkillSearch('');
                  const idx = inputText.lastIndexOf('/');
                  if (idx >= 0) {
                    setInputText(inputText.slice(0, idx));
                  }
                } else {
                  setShowSkillDropdown(false);
                }
              } else {
                // Normal Enter → send
                sendMessage();
              }
            }}
            placeholder={
              activeSkill
                ? `已选择 /${activeSkill.name} — 输入消息...`
                : planMode ? "Plan模式：制定执行计划，逐步完成任务..." : agentMode ? "Agent模式：自动搜索网络后总结回答，附参考链接" : "输入 / 选择技能，或直接输入消息…"
            }
            style={{ flex: 1 }}
          />
        </div>

        {/* Agent模式开关 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '0 6px', background: agentMode ? '#6C63FF15' : '#f5f5f5', borderRadius: 6, border: agentMode ? '1px solid #6C63FF' : '1px solid #d9d9d9' }}>
          <ThunderboltOutlined style={{ color: agentMode ? '#6C63FF' : '#999', fontSize: 12 }} />
          <span style={{ fontSize: 11, color: agentMode ? '#6C63FF' : '#999', whiteSpace: 'nowrap' }}>Agent</span>
          <Switch size="small" checked={agentMode} onChange={(v) => { setAgentMode(v); if (v) setPlanMode(false); }} />
        </div>

        {/* Plan模式开关 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '0 6px', background: planMode ? '#52c41a15' : '#f5f5f5', borderRadius: 6, border: planMode ? '1px solid #52c41a' : '1px solid #d9d9d9' }}>
          <ProjectOutlined style={{ color: planMode ? '#52c41a' : '#999', fontSize: 12 }} />
          <span style={{ fontSize: 11, color: planMode ? '#52c41a' : '#999', whiteSpace: 'nowrap' }}>Plan</span>
          <Switch size="small" checked={planMode} onChange={(v) => { setPlanMode(v); if (v) setAgentMode(false); }} />
        </div>

        <Button
        icon={<ExperimentOutlined />}
        loading={loading}
        onClick={runPipeline}
        style={{ background: '#6C63FF', color: '#fff', border: 'none' }}
      >
        全套分析
      </Button>

        <Button
          icon={<CodeOutlined />}
          onClick={() => setCodeModalVisible(true)}
          style={{ background: '#306998', color: '#FFD43B', border: 'none', fontWeight: 'bold' }}
        >
          Python
        </Button>

        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={loading}
          onClick={sendMessage}
          style={{ background: planMode ? '#52c41a' : agentMode ? '#6C63FF' : undefined }}
        >
          发送
        </Button>
      </div>

      {/* ── Python 代码编辑器弹窗 ── */}
      <Modal
        title="🐍 Python 代码编辑器"
        open={codeModalVisible}
        onOk={runPythonCode}
        onCancel={() => setCodeModalVisible(false)}
        okText="▶ 执行"
        cancelText="取消"
        width={700}
        destroyOnClose={false}
      >
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary">直接输入 Python 代码并执行，无需经过 LLM 改写。支持多行代码、粘贴代码。</Text>
        </div>
        <Input.TextArea
          value={pyCode}
          onChange={(e) => setPyCode(e.target.value)}
          rows={16}
          style={{
            fontFamily: '"Fira Code", "SF Mono", "Menlo", "Consolas", monospace',
            fontSize: 13,
            lineHeight: 1.6,
            background: '#1e1e2e',
            color: '#cdd6f4',
            border: '1px solid #45475a',
          }}
          placeholder="# 在此编写或粘贴 Python 代码"
          spellCheck={false}
        />
        <div style={{ marginTop: 8, display: 'flex', gap: 16, alignItems: 'center' }}>
          <Text type="secondary">超时时间：</Text>
          <Input
            type="number"
            value={pyTimeout}
            onChange={(e) => setPyTimeout(parseInt(e.target.value) || 5)}
            min={1}
            max={30}
            style={{ width: 80 }}
          />
          <Text type="secondary">秒</Text>
          <Text type="secondary" style={{ marginLeft: 'auto' }}>
            ⚡ 快捷键：Ctrl+Enter 执行
          </Text>
        </div>
      </Modal>

      {/* ── 右侧搜索结果面板 (列表 + 详情二级) ── */}
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <SearchOutlined style={{ color: '#1677ff' }} />
            <span style={{ fontSize: 15 }}>
              {detailPanel ? '结果详情' : (searchListPanel ? `搜索结果 (${searchListPanel.results.length} 条)` : '搜索结果')}
            </span>
          </div>
        }
        placement="right"
        width={580}
        open={!!detailPanel || !!searchListPanel}
        onClose={() => { setDetailPanel(null); setSearchListPanel(null); }}
        extra={
          detailPanel ? (
            <Button
              type="text"
              icon={<CloseOutlined />}
              onClick={() => setDetailPanel(null)}
              style={{ marginRight: 4 }}
            >
              返回列表
            </Button>
          ) : (
            <Button
              type="text"
              icon={<CloseOutlined />}
              onClick={() => setSearchListPanel(null)}
            />
          )
        }
        styles={{ body: { padding: detailPanel ? '16px 20px' : '12px 16px' } }}
      >
        {/* ── Level 1: 搜索结果列表 ── */}
        {searchListPanel && !detailPanel && (
          <div>
            <div style={{
              fontSize: 12, color: '#8c8c8c', marginBottom: 12,
              padding: '6px 10px', background: '#fafafa', borderRadius: 6,
            }}>
              <SearchOutlined style={{ marginRight: 6 }} />
              {searchListPanel.query}
            </div>
            {searchListPanel.results.map((r, j) => (
              <div
                key={j}
                onClick={() => setDetailPanel(r)}
                style={{
                  padding: '10px 12px',
                  marginBottom: 6,
                  borderRadius: 8,
                  background: '#ffffff',
                  border: '1px solid #f0f0f0',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#e6f4ff';
                  e.currentTarget.style.border = '1px solid #91caff';
                  e.currentTarget.style.boxShadow = '0 1px 4px rgba(22,119,255,0.12)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = '#ffffff';
                  e.currentTarget.style.border = '1px solid #f0f0f0';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <span style={{
                    background: '#1677ff', color: '#fff', borderRadius: '50%',
                    width: 22, height: 22, fontSize: 11, fontWeight: 700,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0, marginTop: 1,
                  }}>
                    {j + 1}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600, color: '#1f1f1f', marginBottom: 3 }}>
                      {r.title}
                    </div>
                    <div style={{
                      fontSize: 11, color: '#8c8c8c', overflow: 'hidden',
                      textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      <LinkOutlined style={{ marginRight: 4 }} />
                      {r.url}
                    </div>
                    {r.description && (
                      <div style={{ fontSize: 12, color: '#595959', lineHeight: 1.5, marginTop: 4 }}>
                        {r.description.length > 200 ? r.description.slice(0, 200) + '...' : r.description}
                      </div>
                    )}
                  </div>
                  <ExpandOutlined style={{ color: '#bbb', fontSize: 12, flexShrink: 0, marginTop: 4 }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Level 2: 单条结果详情 ── */}
        {detailPanel && (
          <div>
            <Title level={4} style={{ marginTop: 0, color: '#1677ff' }}>
              {detailPanel.title}
            </Title>

            <div style={{ marginBottom: 16 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <LinkOutlined /> 来源链接
              </Text>
              <div style={{ marginTop: 4 }}>
                <a
                  href={detailPanel.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    fontSize: 12, color: '#1677ff', wordBreak: 'break-all',
                    textDecoration: 'underline',
                  }}
                >
                  {detailPanel.url}
                </a>
                <Button
                  type="link"
                  size="small"
                  icon={<LinkOutlined />}
                  href={detailPanel.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ marginLeft: 6, padding: 0 }}
                >
                  打开原网页
                </Button>
              </div>
            </div>

            {detailPanel.description && (
              <div style={{ marginBottom: 16 }}>
                <Text strong style={{ fontSize: 13 }}>📝 摘要</Text>
                <Paragraph style={{
                  marginTop: 6, padding: 12, background: '#fafafa',
                  borderRadius: 6, fontSize: 13, lineHeight: 1.8,
                  color: '#434343', whiteSpace: 'pre-wrap',
                }}>
                  {detailPanel.description}
                </Paragraph>
              </div>
            )}

            {detailPanel.content_preview && (
              <div style={{ marginBottom: 16 }}>
                <Text strong style={{ fontSize: 13 }}>📄 内容预览</Text>
                <pre style={{
                  marginTop: 6, padding: 14, background: '#fafafa',
                  borderRadius: 6, fontSize: 12, lineHeight: 1.7,
                  color: '#434343', whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word', maxHeight: 400, overflow: 'auto',
                  border: '1px solid #f0f0f0',
                }}>
                  {detailPanel.content_preview}
                </pre>
              </div>
            )}

            {detailPanel.source && (
              <Tag color="blue" style={{ marginTop: 4 }}>
                来源引擎: {detailPanel.source}
              </Tag>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
