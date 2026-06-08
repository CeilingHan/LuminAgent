import React, { useState, useEffect } from 'react';
import { Button, Input, Tag, Typography, message, Badge, Divider } from 'antd';
import { PlusOutlined, ReloadOutlined, LinkOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
const { TextArea } = Input;

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';

export default function Skills() {
  const [skills, setSkills] = useState([]);
  const [tools, setTools] = useState([]);
  const [view, setView] = useState('list');
  const [form, setForm] = useState({ name: '', description: '', tools: [], trigger_keywords: '', content: '' });
  const [urlInput, setUrlInput] = useState('');

  // Load tools (GET /) and skills (GET /skills) on mount
  useEffect(() => {
    fetchTools();
    fetchSkills();
  }, []);

  const fetchTools = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/`);
      const data = await res.json();
      if (data.skills) setTools(data.skills || []);
    } catch {}
  };

  const fetchSkills = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/skills`);
      const data = await res.json();
      if (data.success) setSkills(data.data || []);
    } catch {}
  };

  const saveSkill = async () => {
    const { name, description, tools, trigger_keywords, content } = form;
    if (!name.trim() || !content.trim()) {
      message.warning('请填写名称和内容');
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/skills`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name, description, tools,
          trigger_keywords: trigger_keywords.split(/[,，]/).map(k => k.trim()).filter(Boolean),
          content,
        }),
      });
      const data = await res.json();
      if (data.success) {
        message.success(data.data.action === 'updated' ? '技能已更新' : '技能已创建');
        setForm({ name: '', description: '', tools: [], trigger_keywords: '', content: '' });
        setView('list');
        fetchSkills();
      } else {
        message.error(data.error || '保存失败');
      }
    } catch {
      message.error('请求失败');
    }
  };

  const deleteSkill = async (name) => {
    try {
      const res = await fetch(`${API_BASE_URL}/skills/${name}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        message.success(`技能 "${name}" 已删除`);
        fetchSkills();
      }
    } catch {}
  };

  const loadFromUrl = async () => {
    if (!urlInput.trim()) {
      message.warning('请输入 URL');
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/skills/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: urlInput.trim() }),
      });
      const data = await res.json();
      if (data.success) {
        message.success(`技能 "${data.data.name}" 已加载 (${data.data.action})`);
        setUrlInput('');
        setView('list');
        fetchSkills();
      } else {
        message.error(data.error || '加载失败');
      }
    } catch {
      message.error('请求失败，请检查 URL 是否可访问');
    }
  };

  const openEdit = async (skill) => {
    // Fetch full content before showing the edit form
    try {
      const res = await fetch(`${API_BASE_URL}/skills/${skill.name}`);
      const d = await res.json();
      const fullContent = d.success ? (d.data.content || '') : '';
      setForm({
        name: skill.name,
        description: skill.description || '',
        tools: skill.tools || [],
        trigger_keywords: (skill.trigger_keywords || []).join(', '),
        content: fullContent,
      });
      setView('edit');
    } catch {
      message.error('加载技能内容失败');
    }
  };

  const toggleTool = (toolKey) => {
    setForm(prev => ({
      ...prev,
      tools: prev.tools.includes(toolKey)
        ? prev.tools.filter(t => t !== toolKey)
        : [...prev.tools, toolKey],
    }));
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>📦 技能管理</Title>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<ReloadOutlined />} onClick={fetchSkills}>刷新</Button>
          <Button icon={<LinkOutlined />} onClick={() => setView('load')}>从URL加载</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => {
            setForm({ name: '', description: '', tools: [], trigger_keywords: '', content: '' });
            setView('create');
          }}>
            新建技能
          </Button>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: '1px solid #f0f0f0', paddingBottom: 8 }}>
        {[
          { key: 'list', label: '📋 技能列表' },
          { key: 'create', label: '➕ 新建' },
          { key: 'edit', label: '✏️ 编辑' },
          { key: 'load', label: '🔗 从URL加载' },
        ].map(tab => (
          <Button
            key={tab.key}
            type={view === tab.key ? 'primary' : 'text'}
            size="small"
            onClick={() => setView(tab.key)}
            disabled={tab.key === 'edit' && !form.name}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {/* View: List */}
      {view === 'list' && (
        <div>
          {/* ── Available Tools (底层工具) ── */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <ThunderboltOutlined style={{ color: '#722ed1', fontSize: 16 }} />
              <Text strong style={{ fontSize: 15 }}>可用工具 (底层能力)</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                — 创建技能时可选用，来自后端
              </Text>
              <Button size="small" icon={<ReloadOutlined />} onClick={fetchTools} style={{ marginLeft: 'auto' }}>刷新</Button>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {tools.length === 0 ? (
                <Text type="secondary">加载中...</Text>
              ) : (
                tools.map(t => (
                  <div key={t.id} style={{
                    padding: '8px 14px',
                    background: t.available !== false ? '#f9f0ff' : '#f5f5f5',
                    borderRadius: 8, border: `1px solid ${t.available !== false ? '#d3adf7' : '#e0e0e0'}`,
                    opacity: t.available !== false ? 1 : 0.5,
                  }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#1f1f1f' }}>
                      <Badge status={t.available !== false ? 'success' : 'error'} style={{ marginRight: 4 }} />
                      {t.id}
                    </div>
                    <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2, maxWidth: 240 }}>
                      {t.description}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <Divider style={{ margin: '16px 0' }} />

          {/* ── User Skills (上层技能) ── */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{ fontSize: 18 }}>📦</span>
            <Text strong style={{ fontSize: 15 }}>自定义技能 (用户编排)</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              — 共 {skills.length} 个
            </Text>
          </div>

          {skills.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 30, color: '#8c8c8c', background: '#fafafa', borderRadius: 10 }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>📦</div>
              <div>暂无自定义技能</div>
              <div style={{ marginTop: 4 }}>点击"新建技能"创建，或"从URL加载"从 GitHub 导入</div>
            </div>
          ) : (
            skills.map(skill => (
              <div key={skill.name} style={{
                padding: '14px 16px', marginBottom: 10,
                background: '#fafafa', borderRadius: 10, border: '1px solid #e0e0e0',
                cursor: 'pointer', transition: 'all 0.15s',
              }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#fff7e6'; e.currentTarget.style.border = '1px solid #ffd591'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = '#fafafa'; e.currentTarget.style.border = '1px solid #e0e0e0'; }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, color: '#1f1f1f' }}>
                      {skill.name}
                      {skill.source_url && (
                        <Tag color="orange" style={{ marginLeft: 8, fontSize: 10 }}>URL</Tag>
                      )}
                    </div>
                    <div style={{ fontSize: 13, color: '#595959', marginTop: 4 }}>
                      {skill.description || '无描述'}
                    </div>
                    {skill.trigger_keywords?.length > 0 && (
                      <div style={{ marginTop: 6 }}>
                        <Text type="secondary" style={{ fontSize: 11 }}>触发词: </Text>
                        {skill.trigger_keywords.map(kw => (
                          <Tag key={kw} color="blue" style={{ fontSize: 10, marginBottom: 2 }}>{kw}</Tag>
                        ))}
                      </div>
                    )}
                    {skill.tools?.length > 0 && (
                      <div style={{ marginTop: 4 }}>
                        <Text type="secondary" style={{ fontSize: 11 }}>工具: </Text>
                        {skill.tools.map(t => (
                          <Tag key={t} style={{ fontSize: 10, marginBottom: 2 }}>{t}</Tag>
                        ))}
                      </div>
                    )}
                    {skill.content_preview && (
                      <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 500 }}>
                        {skill.content_preview}
                      </div>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginLeft: 12 }}>
                    <Button size="small" icon={<EditOutlined />}
                      onClick={(e) => { e.stopPropagation(); openEdit(skill); }}>
                      编辑
                    </Button>
                    <Button size="small" danger icon={<DeleteOutlined />}
                      onClick={(e) => { e.stopPropagation(); deleteSkill(skill.name); }}>
                      删除
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* View: Create / Edit */}
      {(view === 'create' || view === 'edit') && (
        <div style={{ maxWidth: 750 }}>
          <div style={{ marginBottom: 12 }}>
            <Text strong>名称 (英文 slug)</Text>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="例如: literature-review"
              style={{ marginTop: 4 }}
              disabled={view === 'edit'}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <Text strong>描述 (用于检索匹配)</Text>
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="例如: 文献综述 — 搜索、整理、总结研究论文"
              style={{ marginTop: 4 }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <Text strong>触发关键词 (逗号分隔)</Text>
            <Input
              value={form.trigger_keywords}
              onChange={(e) => setForm({ ...form, trigger_keywords: e.target.value })}
              placeholder="例如: 文献综述, 调研, 研究现状, literature review"
              style={{ marginTop: 4 }}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>
              用户输入中包含任一关键词时，自动激活此技能
            </Text>
          </div>

          <div style={{ marginBottom: 12 }}>
            <Text strong>选用工具 (来自可用工具列表)</Text>
            <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {tools.length === 0 ? (
                <Text type="secondary">加载中...</Text>
              ) : (
                tools.map(t => (
                  <Tag key={t.id}
                    style={{ cursor: 'pointer' }}
                    color={form.tools.includes(t.id) ? 'purple' : 'default'}
                    onClick={() => toggleTool(t.id)}
                  >
                    {form.tools.includes(t.id) ? '✓ ' : ''}{t.id}
                  </Tag>
                ))
              )}
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <Text strong>技能内容 (Markdown 格式的系统提示)</Text>
            <TextArea
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              rows={14}
              placeholder={`# 文献综述技能

## 触发条件
当用户要求"文献综述"、"调研"、"总结研究现状"时自动激活

## 执行步骤
1. 用 web_search 搜索相关论文（中文 + 英文）
2. 提取每篇论文的核心贡献和方法
3. 按子领域分类
4. 生成 Markdown 格式的综述报告，包含引用链接

## 输出格式
### [领域名称]
- **论文**: [标题](链接) — 核心贡献
- **方法**: 关键技术
- **相关度**: ⭐⭐⭐`}
              style={{ marginTop: 4, fontFamily: '"Fira Code", "SF Mono", monospace', fontSize: 12.5 }}
            />
          </div>

          <Button type="primary" onClick={saveSkill} style={{ background: view === 'edit' ? '#722ed1' : undefined }}>
            {view === 'edit' ? '更新技能' : '创建技能'}
          </Button>
        </div>
      )}

      {/* View: Load from URL */}
      {view === 'load' && (
        <div style={{ maxWidth: 700 }}>
          <div style={{
            padding: 16, background: '#f6ffed', borderRadius: 10,
            border: '1px solid #b7eb8f', marginBottom: 16,
          }}>
            <Text strong style={{ color: '#389e0d' }}>💡 提示</Text>
            <div style={{ fontSize: 13, color: '#595959', marginTop: 4 }}>
              支持从 GitHub Raw URL 或其他公开 URL 加载技能 Markdown 文件。
              文件格式需包含 YAML frontmatter。
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <Text strong>技能文件 URL</Text>
            <Input
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://raw.githubusercontent.com/user/repo/main/skills/my-skill.md"
              style={{ marginTop: 4, fontFamily: 'monospace' }}
            />
          </div>

          <Button type="primary" icon={<LinkOutlined />} onClick={loadFromUrl}>
            从 URL 加载
          </Button>

          <div style={{ marginTop: 24 }}>
            <Text strong style={{ fontSize: 13 }}>示例 URL</Text>
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                'https://raw.githubusercontent.com/anthropics/skills/main/skills/pdf.md',
                'https://raw.githubusercontent.com/anthropics/skills/main/skills/webapp-testing.md',
              ].map(u => (
                <Button key={u} type="dashed" size="small"
                  onClick={() => setUrlInput(u)}
                  style={{ fontSize: 11, fontFamily: 'monospace', textAlign: 'left' }}>
                  📎 {u}
                </Button>
              ))}
              <Text type="secondary" style={{ fontSize: 11 }}>
                注: 示例 URL 仅供参考，实际可用性取决于目标文件是否存在
              </Text>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
