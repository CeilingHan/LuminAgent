import React, { useState, useEffect } from 'react';
import { Card, List, Badge, Typography, Space, Button, message } from 'antd';
import { TeamOutlined, ReloadOutlined } from '@ant-design/icons';
import { agentApi } from '../api';

const { Title, Text } = Typography;

const MultiAgent = () => {
  const [agentList, setAgentList] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAgentList = async () => {
    try {
      setLoading(true);
      const res = await agentApi.getMultiAgentList();
      setAgentList(res || [
        { id: 'manus-1', name: 'Manus Agent', status: 'online', skills: ['BrowserUse', 'PythonExecute'] },
        { id: 'manus-2', name: 'Planning Agent', status: 'offline', skills: ['Planning'] },
      ]);
    } catch (error) {
      message.error('获取Agent列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgentList();
  }, []);

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>多Agent协同</Title>
        <Button icon={<ReloadOutlined />} onClick={fetchAgentList} loading={loading}>
          刷新列表
        </Button>
      </Space>
      <List
        grid={{ gutter: 16, column: 2 }}
        dataSource={agentList}
        renderItem={(agent) => (
          <List.Item>
            <Card>
              <Space>
                <TeamOutlined style={{ fontSize: 24 }} />
                <div>
                  <Text strong>{agent.name}</Text>
                  <br />
                  <Badge
                    status={agent.status === 'online' ? 'success' : 'error'}
                    text={agent.status === 'online' ? '在线' : '离线'}
                  />
                  <br />
                  <Text type="secondary">技能：{agent.skills.join(', ')}</Text>
                </div>
              </Space>
            </Card>
          </List.Item>
        )}
      />
    </div>
  );
};

export default MultiAgent;