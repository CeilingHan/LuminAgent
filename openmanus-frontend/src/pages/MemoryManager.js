import React, { useState } from 'react';
import { Button, Input, Tag, Typography, message } from 'antd';
import { SaveOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import TextArea from 'antd/es/input/TextArea';

const { Title, Text } = Typography;

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';

const MEMORY_TYPES = [
  { key: 'user', label: '👤 用户', color: 'blue' },
  { key: 'project', label: '📁 项目', color: 'green' },
  { key: 'feedback', label: '💬 反馈', color: 'orange' },
  { key: 'reference', label: '📚 参考', color: 'purple' },
];

export default function MemoryManager() {
  const [memories, setMemories] = useState([]);
  const [memoryForm, setMemoryForm] = useState({ name: '', type: 'project', description: '', content: '' });
  const [memoryView, setMemoryView] = useState('list'); // 'list' | 'create' | 'view'
  const [memoryDetail, setMemoryDetail] = useState(null);

  const fetchMemories = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/memory`);
      const data = await res.json();
      if (data.success) setMemories(data.data || []);
    } catch {}
  };

  const saveMemory = async () => {
    const { name, type, description, content } = memoryForm;
    if (!name.trim() || !content.trim()) {
      message.warning('请填写名称和内容');
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/memory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, type, description, content }),
      });
      const data = await res.json();
      if (data.success) {
        message.success(data.data.action === 'updated' ? '记忆已更新' : '记忆已创建');
        setMemoryForm({ name: '', type: 'project', description: '', content: '' });
        setMemoryView('list');
        fetchMemories();
      } else {
        message.error(data.error || '保存失败');
      }
    } catch {
      message.error('请求失败');
    }
  };

  const deleteMemory = async (name) => {
    try {
      const res = await fetch(`${API_BASE_URL}/memory/${name}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        message.success(`记忆 "${name}" 已删除`);
        fetchMemories();
      }
    } catch {}
  };

  const viewMemory = async (name) => {
    try {
      const res = await fetch(`${API_BASE_URL}/memory/${name}`);
      const data = await res.json();
      if (data.success) {
        setMemoryDetail(data.data);
        setMemoryView('view');
      }
    } catch {}
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>🧠 记忆管理</Title>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<ReloadOutlined />} onClick={fetchMemories}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setMemoryView('create')}>
            新建记忆
          </Button>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: '1px solid #f0f0f0', paddingBottom: 8 }}>
        {[
          { key: 'list', label: '📋 记忆列表' },
          { key: 'create', label: '➕ 新建' },
          { key: 'view', label: memoryDetail ? '📄 ' + memoryDetail.name : '📄 详情' },
        ].map(tab => (
          <Button
            key={tab.key}
            type={memoryView === tab.key ? 'primary' : 'text'}
            size="small"
            onClick={() => setMemoryView(tab.key)}
            style={memoryView === tab.key ? { background: '#722ed1', borderColor: '#722ed1' } : {}}
            disabled={tab.key === 'view' && !memoryDetail}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {/* View: List */}
      {memoryView === 'list' && (
        <div>
          {memories.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>
              <SaveOutlined style={{ fontSize: 48 }} />
              <div style={{ marginTop: 12, fontSize: 15 }}>暂无记忆</div>
              <div style={{ marginTop: 4 }}>点击右上角"新建记忆"添加</div>
              <div style={{ marginTop: 8, fontSize: 12 }}>记忆文件保存在 data/memory/ 目录</div>
            </div>
          ) : (
            memories.map(m => (
              <div key={m.name} style={{
                padding: '12px 14px', marginBottom: 8,
                background: '#fafafa', borderRadius: 10, border: '1px solid #e0e0e0',
                cursor: 'pointer', transition: 'all 0.15s',
              }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#f3f0ff'; e.currentTarget.style.border = '1px solid #d3adf7'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = '#fafafa'; e.currentTarget.style.border = '1px solid #e0e0e0'; }}
                onClick={() => viewMemory(m.name)}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, color: '#1f1f1f' }}>
                      {m.name}
                      <Tag color={MEMORY_TYPES.find(t => t.key === m.type)?.color || 'default'} style={{ marginLeft: 8 }}>
                        {m.type}
                      </Tag>
                    </div>
                    <div style={{ fontSize: 13, color: '#595959', marginTop: 4 }}>
                      {m.description || m.content_preview?.slice(0, 120)}
                    </div>
                    {m.updated_at && (
                      <div style={{ fontSize: 11, color: '#bfbfbf', marginTop: 2 }}>
                        更新于: {new Date(m.updated_at).toLocaleString('zh-CN')}
                      </div>
                    )}
                  </div>
                  <Button size="small" danger
                    onClick={(e) => { e.stopPropagation(); deleteMemory(m.name); }}
                    style={{ marginLeft: 10 }}>
                    删除
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* View: Create */}
      {memoryView === 'create' && (
        <div style={{ maxWidth: 700 }}>
          <div style={{ marginBottom: 12 }}>
            <Text strong>名称 (slug)</Text>
            <Input
              value={memoryForm.name}
              onChange={(e) => setMemoryForm({ ...memoryForm, name: e.target.value })}
              placeholder="例如: project-my-research"
              style={{ marginTop: 4 }}
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <Text strong>类型</Text>
            <div style={{ marginTop: 4, display: 'flex', gap: 6 }}>
              {MEMORY_TYPES.map(t => (
                <Tag key={t.key} style={{ cursor: 'pointer' }}
                  color={memoryForm.type === t.key ? t.color : 'default'}
                  onClick={() => setMemoryForm({ ...memoryForm, type: t.key })}>
                  {t.label}
                </Tag>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: 12 }}>
            <Text strong>描述 (用于检索匹配)</Text>
            <Input
              value={memoryForm.description}
              onChange={(e) => setMemoryForm({ ...memoryForm, description: e.target.value })}
              placeholder="一句话描述这个记忆"
              style={{ marginTop: 4 }}
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <Text strong>内容 (Markdown)</Text>
            <TextArea
              value={memoryForm.content}
              onChange={(e) => setMemoryForm({ ...memoryForm, content: e.target.value })}
              rows={12}
              placeholder="Markdown 格式的记忆内容..."
              style={{ marginTop: 4 }}
            />
          </div>
          <Button
            type="primary"
            onClick={saveMemory}
            style={{ background: '#722ed1', borderColor: '#722ed1' }}
          >
            保存记忆
          </Button>
        </div>
      )}

      {/* View: Detail */}
      {memoryView === 'view' && memoryDetail && (
        <div style={{ maxWidth: 800 }}>
          <Button type="text" onClick={() => setMemoryView('list')} style={{ marginBottom: 12 }}>
            ← 返回列表
          </Button>
          <div style={{ marginBottom: 10 }}>
            <span style={{ fontSize: 18, fontWeight: 600 }}>{memoryDetail.name}</span>
            <Tag color={MEMORY_TYPES.find(t => t.key === memoryDetail.type)?.color || 'default'} style={{ marginLeft: 10 }}>
              {memoryDetail.type}
            </Tag>
          </div>
          {memoryDetail.description && (
            <div style={{ fontSize: 13, color: '#8c8c8c', marginBottom: 12 }}>
              {memoryDetail.description}
            </div>
          )}
          <div style={{
            padding: 16, background: '#fafafa', borderRadius: 10,
            fontSize: 14, lineHeight: 1.9, whiteSpace: 'pre-wrap', color: '#1f1f1f',
            border: '1px solid #e0e0e0', minHeight: 120,
          }}>
            {memoryDetail.content}
          </div>
          {memoryDetail.links?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>关联: {memoryDetail.links.join(', ')}</Text>
            </div>
          )}
          {memoryDetail.updated_at && (
            <div style={{ marginTop: 8, fontSize: 12, color: '#bfbfbf' }}>
              更新于: {new Date(memoryDetail.updated_at).toLocaleString('zh-CN')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
