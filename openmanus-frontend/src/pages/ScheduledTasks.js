import React, { useState } from 'react';
import { Button, Input, Modal, Tag, Typography, message, Switch } from 'antd';
import { ClockCircleOutlined, PlusOutlined, ReloadOutlined, ThunderboltOutlined, ProjectOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';

const CRON_PRESETS = [
  { label: '每5分钟', cron: '*/5 * * * *' },
  { label: '每小时', cron: '0 * * * *' },
  { label: '每天早上8点', cron: '0 8 * * *' },
  { label: '每天下午6点', cron: '0 18 * * *' },
  { label: '每周一早上9点', cron: '0 9 * * 1' },
];

export default function ScheduledTasks() {
  const [tasks, setTasks] = useState([]);
  const [taskForm, setTaskForm] = useState({ name: '', cron: '0 8 * * *', prompt: '', mode: 'agent' });
  const [taskView, setTaskView] = useState('list'); // 'list' | 'create' | 'history'
  const [taskHistory, setTaskHistory] = useState([]);
  const [taskHistoryJobId, setTaskHistoryJobId] = useState('');

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/scheduler/jobs`);
      const data = await res.json();
      if (data.success) setTasks(data.data || []);
    } catch {}
  };

  const createTask = async () => {
    const { name, cron, prompt, mode } = taskForm;
    if (!name.trim() || !prompt.trim()) {
      message.warning('请填写任务名称和任务描述');
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/scheduler/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, cron, prompt, mode }),
      });
      const data = await res.json();
      if (data.success) {
        message.success(`任务 "${name}" 已创建`);
        setTaskForm({ name: '', cron: '0 8 * * *', prompt: '', mode: 'agent' });
        setTaskView('list');
        fetchTasks();
      } else {
        message.error(data.error || '创建失败');
      }
    } catch {
      message.error('请求失败，请检查后端');
    }
  };

  const toggleTask = async (jobId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/scheduler/jobs/${jobId}`, { method: 'PUT' });
      const data = await res.json();
      if (data.success) {
        message.success(data.data.enabled ? '已启用' : '已停用');
        fetchTasks();
      }
    } catch {}
  };

  const deleteTask = async (jobId, name) => {
    try {
      const res = await fetch(`${API_BASE_URL}/scheduler/jobs/${jobId}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        message.success(`任务 "${name}" 已删除`);
        fetchTasks();
      }
    } catch {}
  };

  const viewHistory = async (jobId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/scheduler/jobs/${jobId}/history?limit=10`);
      const data = await res.json();
      if (data.success) {
        setTaskHistory(data.data || []);
        setTaskHistoryJobId(jobId);
        setTaskView('history');
      }
    } catch {}
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>⏰ 定时任务</Title>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<ReloadOutlined />} onClick={fetchTasks}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setTaskView('create'); }}>
            新建任务
          </Button>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: '1px solid #f0f0f0', paddingBottom: 8 }}>
        {[
          { key: 'list', label: '📋 任务列表' },
          { key: 'create', label: '➕ 新建任务' },
          { key: 'history', label: '📜 执行历史' },
        ].map(tab => (
          <Button
            key={tab.key}
            type={taskView === tab.key ? 'primary' : 'text'}
            size="small"
            onClick={() => setTaskView(tab.key)}
            style={taskView === tab.key ? { background: '#fa8c16', borderColor: '#fa8c16' } : {}}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {/* View: Task List */}
      {taskView === 'list' && (
        <div>
          {tasks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>
              <ClockCircleOutlined style={{ fontSize: 48 }} />
              <div style={{ marginTop: 12, fontSize: 15 }}>暂无定时任务</div>
              <div style={{ marginTop: 4 }}>点击右上角"新建任务"创建</div>
            </div>
          ) : (
            tasks.map(task => (
              <div key={task.id} style={{
                padding: '14px 16px', marginBottom: 10,
                background: task.enabled ? '#fff7e6' : '#fafafa',
                borderRadius: 10, border: task.enabled ? '1px solid #ffd591' : '1px solid #e0e0e0',
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, color: '#1f1f1f' }}>
                      {task.name}
                      <Tag color={task.mode === 'plan' ? 'green' : 'blue'} style={{ marginLeft: 8 }}>
                        {task.mode === 'plan' ? 'Plan' : 'Agent'}
                      </Tag>
                      {task.enabled ? (
                        <Tag color="orange" style={{ fontSize: 10 }}>运行中</Tag>
                      ) : (
                        <Tag style={{ fontSize: 10 }}>已停用</Tag>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 4, fontFamily: 'monospace' }}>
                      cron: {task.cron}
                    </div>
                    <div style={{ fontSize: 13, color: '#595959', marginTop: 6 }}>
                      {task.prompt}
                    </div>
                    <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 4 }}>
                      下次执行: {task.next_run ? new Date(task.next_run).toLocaleString('zh-CN') : '—'}
                      {task.last_summary && (
                        <span style={{ color: '#52c41a' }}> · 上次: {task.last_summary?.slice(0, 80)}</span>
                      )}
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginLeft: 12 }}>
                    <Switch size="small" checked={task.enabled} onChange={() => toggleTask(task.id)} />
                    <Button size="small" onClick={() => viewHistory(task.id)}>历史</Button>
                    <Button size="small" danger onClick={() => deleteTask(task.id, task.name)}>删除</Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* View: Create Task */}
      {taskView === 'create' && (
        <div style={{ maxWidth: 700 }}>
          <div style={{ marginBottom: 14 }}>
            <Text strong>任务名称</Text>
            <Input
              value={taskForm.name}
              onChange={(e) => setTaskForm({ ...taskForm, name: e.target.value })}
              placeholder="例如: 每天早上检查arXiv新论文"
              style={{ marginTop: 4 }}
            />
          </div>

          <div style={{ marginBottom: 14 }}>
            <Text strong>Cron 表达式</Text>
            <Input
              value={taskForm.cron}
              onChange={(e) => setTaskForm({ ...taskForm, cron: e.target.value })}
              placeholder="分 时 日 月 周 (例如: 0 8 * * *)"
              style={{ marginTop: 4, fontFamily: '"Fira Code", monospace' }}
            />
            <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>快捷:</Text>
              {CRON_PRESETS.map(p => (
                <Tag key={p.cron} style={{ cursor: 'pointer' }}
                  color={taskForm.cron === p.cron ? 'orange' : 'default'}
                  onClick={() => setTaskForm({ ...taskForm, cron: p.cron })}>
                  {p.label}: {p.cron}
                </Tag>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <Text strong>任务描述 (Prompt)</Text>
            <Input.TextArea
              value={taskForm.prompt}
              onChange={(e) => setTaskForm({ ...taskForm, prompt: e.target.value })}
              rows={4}
              placeholder="描述要执行的研究任务..."
              style={{ marginTop: 4 }}
            />
          </div>

          <div style={{ marginBottom: 14 }}>
            <Text strong>执行模式</Text>
            <div style={{ marginTop: 4, display: 'flex', gap: 8 }}>
              <Button
                type={taskForm.mode === 'agent' ? 'primary' : 'default'}
                onClick={() => setTaskForm({ ...taskForm, mode: 'agent' })}
                style={taskForm.mode === 'agent' ? { background: '#6C63FF', borderColor: '#6C63FF' } : {}}
                icon={<ThunderboltOutlined />}
              >
                Agent (单步执行)
              </Button>
              <Button
                type={taskForm.mode === 'plan' ? 'primary' : 'default'}
                onClick={() => setTaskForm({ ...taskForm, mode: 'plan' })}
                style={taskForm.mode === 'plan' ? { background: '#52c41a', borderColor: '#52c41a' } : {}}
                icon={<ProjectOutlined />}
              >
                Plan (先计划后执行)
              </Button>
            </div>
          </div>

          <Button
            type="primary"
            onClick={createTask}
            style={{ background: '#fa8c16', borderColor: '#fa8c16' }}
          >
            创建定时任务
          </Button>
        </div>
      )}

      {/* View: History */}
      {taskView === 'history' && (
        <div>
          <Button type="text" onClick={() => setTaskView('list')} style={{ marginBottom: 12 }}>
            ← 返回任务列表
          </Button>
          {taskHistory.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>
              暂无执行记录
            </div>
          ) : (
            taskHistory.map((h, i) => (
              <div key={i} style={{
                padding: '12px 14px', marginBottom: 8,
                background: h.success ? '#f6ffed' : '#fff2f0',
                borderRadius: 8, border: `1px solid ${h.success ? '#b7eb8f' : '#ffccc7'}`,
              }}>
                <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                  {h.timestamp ? new Date(h.timestamp).toLocaleString('zh-CN') : '—'}
                  <Tag color={h.success ? 'green' : 'red'} style={{ marginLeft: 8, fontSize: 10 }}>
                    {h.success ? '成功' : '失败'}
                  </Tag>
                  <Tag style={{ fontSize: 10 }}>{h.mode}</Tag>
                  {h.duration_s !== undefined && (
                    <span style={{ marginLeft: 8 }}>耗时 {h.duration_s}s</span>
                  )}
                </div>
                <div style={{ fontSize: 13, color: '#595959', marginTop: 6 }}>
                  {h.error ? (
                    <span style={{ color: '#cf1322' }}>❌ {h.error}</span>
                  ) : (
                    <span>{(h.summary || '').slice(0, 300)}</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: '#bfbfbf', marginTop: 4 }}>
                  Prompt: {(h.prompt || '').slice(0, 100)}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
