import React, { useState, useEffect } from 'react';
import { Layout, Menu, Typography, Badge, Space, Spin } from 'antd';
import {
  AppstoreOutlined,
  ToolOutlined,
  TeamOutlined,
  DashboardOutlined,
  ApiOutlined,
  MessageOutlined,
  ClockCircleOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { Link, Outlet, useLocation } from 'react-router-dom';

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

const MainLayout = () => {
  const location = useLocation();
  const [agentStatus, setAgentStatus] = useState({ online: true, name: 'LuminAgent' });
  const [loading, setLoading] = useState(false);

  // Derive current key from location
  const currentKey = location.pathname.slice(1) || 'chat';

  useEffect(() => {
    const fetchAgentStatus = async () => {
      try {
        setLoading(true);
        setAgentStatus({ online: true, name: 'LuminAgent' });
      } catch (error) {
        setAgentStatus({ online: false, name: 'LuminAgent' });
      } finally {
        setLoading(false);
      }
    };
    fetchAgentStatus();
  }, []);

  const menuItems = [
    { key: 'chat', icon: <MessageOutlined />, label: <Link to="/chat">Agent对话</Link> },
    { key: 'multi-agent', icon: <TeamOutlined />, label: <Link to="/multi-agent">多Agent协同</Link> },
    { key: 'scheduled-tasks', icon: <ClockCircleOutlined />, label: <Link to="/scheduled-tasks">定时任务</Link> },
    { key: 'api-test', icon: <ApiOutlined />, label: <Link to="/api-test">API测试</Link> },
    { key: 'memory', icon: <SaveOutlined />, label: <Link to="/memory">记忆管理</Link> },
    { key: 'tools', icon: <ToolOutlined />, label: <Link to="/tools">工具管理</Link> },
    { key: 'skills', icon: <AppstoreOutlined />, label: <Link to="/skills">技能管理</Link> },
    { key: 'dashboard', icon: <DashboardOutlined />, label: <Link to="/dashboard">仪表盘</Link> },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={200} theme="light">
        <div style={{ padding: '16px', fontSize: '18px', fontWeight: 'bold' }}>LuminAgent</div>
        <Menu mode="inline" items={menuItems} selectedKeys={[currentKey]} style={{ borderRight: 0 }} />
      </Sider>

      <Layout>
        <Header style={{ padding: '0 16px', background: '#fff', boxShadow: '0 1px 4px rgba(0,0,0,0.1)' }}>
          <Space style={{ height: '100%', alignItems: 'center', float: 'right' }}>
            <Spin spinning={loading} size="small">
              <Badge status={agentStatus.online ? 'success' : 'error'} text={agentStatus.online ? `${agentStatus.name} 在线` : `${agentStatus.name} 离线`} />
            </Spin>
          </Space>
          <Title level={4} style={{ margin: 0, lineHeight: '64px' }}>
            {(() => {
              const item = menuItems.find(i => i.key === currentKey);
              return item ? item.label?.props?.children || item.key : 'Agent对话';
            })()}
          </Title>
        </Header>

        <Content style={{ margin: '16px', background: '#fff', padding: '24px', borderRadius: '4px', minHeight: 'calc(100vh - 104px)' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;