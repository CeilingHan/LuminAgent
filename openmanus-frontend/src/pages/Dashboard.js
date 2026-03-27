import React, { useState, useEffect } from 'react';
import { Card, Statistic, Row, Col, Table, Tag, Progress, Space, Typography } from 'antd';
import { CheckCircleOutlined, ExclamationCircleOutlined, ToolOutlined, TeamOutlined, AppstoreOutlined } from '@ant-design/icons';
import { agentApi, skillApi, toolApi } from '../api';

const { Title, Text } = Typography;

const Dashboard = () => {
  // 状态管理：核心统计数据
  const [stats, setStats] = useState({
    skillCount: 0,
    toolCount: 0,
    agentCount: 1, // 默认1个Agent
    activeSkillCount: 0,
  });
  const [recentCalls, setRecentCalls] = useState([]);
  const [loading, setLoading] = useState(true);

  // 获取仪表盘数据
  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        // 并行请求数据
        const [skillRes, toolRes, agentRes] = await Promise.all([
          skillApi.getSkillList(),
          toolApi.getToolList(),
          agentApi.getMultiAgentList(),
        ]);

        // 统计数据
        setStats({
          skillCount: skillRes.length || 0,
          activeSkillCount: skillRes.filter(skill => skill.enabled).length || 0,
          toolCount: toolRes.length || 0,
          agentCount: agentRes.length || 1,
        });

        // 模拟最近调用记录（实际项目可替换为真实接口）
        setRecentCalls([
          { id: 1, skill: 'Browser use', agent: 'Manus Agent', status: 'success', time: '2026-03-23 10:23:45' },
          { id: 2, skill: 'Python Execute', agent: 'Manus Agent', status: 'failed', time: '2026-03-23 10:15:30' },
          { id: 3, skill: 'Ask human', agent: 'Manus Agent', status: 'success', time: '2026-03-23 09:45:12' },
        ]);
      } catch (error) {
        console.error('获取仪表盘数据失败:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  // 最近调用记录列配置
  const callColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '调用技能',
      dataIndex: 'skill',
      key: 'skill',
    },
    {
      title: '执行Agent',
      dataIndex: 'agent',
      key: 'agent',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Tag color={status === 'success' ? 'success' : 'error'}>
          {status === 'success' ? '成功' : '失败'}
        </Tag>
      ),
    },
    {
      title: '调用时间',
      dataIndex: 'time',
      key: 'time',
    },
  ];

  return (
    <div>
      <Title level={3}>OpenManus 仪表盘</Title>
      
      {/* 核心统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="技能总数(Skills)"
              value={stats.skillCount}
              prefix={<AppstoreOutlined />}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="活跃技能数"
              value={stats.activeSkillCount}
              suffix={`/${stats.skillCount}`}
              prefix={<CheckCircleOutlined />}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="工具总数(Tools)"
              value={stats.toolCount}
              prefix={<ToolOutlined />}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Agent数量"
              value={stats.agentCount}
              prefix={<TeamOutlined />}
              loading={loading}
            />
          </Card>
        </Col>
      </Row>

      {/* 技能激活率 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24}>
          <Card title="技能激活率">
            <Progress
              percent={stats.skillCount > 0 ? Math.round((stats.activeSkillCount / stats.skillCount) * 100) : 0}
              status="normal"
              strokeWidth={16}
              format={(percent) => `${percent}% (${stats.activeSkillCount}/${stats.skillCount})`}
            />
          </Card>
        </Col>
      </Row>

      {/* 最近调用记录 */}
      <Card title="最近技能调用记录">
        <Table
          columns={callColumns}
          dataSource={recentCalls}
          rowKey="id"
          pagination={{ pageSize: 5 }}
          loading={loading}
          locale={{ emptyText: '暂无调用记录' }}
        />
      </Card>
    </div>
  );
};

export default Dashboard;