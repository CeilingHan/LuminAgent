import React, { useState, useEffect } from 'react';
import { Table, Tag, Button, Space, Modal, Form, Input, Typography, message } from 'antd';
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { toolApi } from '../api';

const { Title } = Typography;

const Tools = () => {
  const [toolList, setToolList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [currentTool, setCurrentTool] = useState(null);
  const [testParams, setTestParams] = useState('{}');

  const fetchToolList = async () => {
    try {
      setLoading(true);
      const res = await toolApi.getToolList();
      setToolList(res || [
        { id: 'AskHuman', name: '询问人类', description: '向人类发起询问', tags: ['交互'] },
        { id: 'BrowserUse', name: '浏览器使用', description: '使用浏览器访问网页', tags: ['网络'] },
        { id: 'PythonExecute', name: 'Python执行', description: '执行Python代码', tags: ['计算'] },
      ]);
    } catch (error) {
      message.error('获取工具列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchToolList();
  }, []);

  const handleTestTool = (tool) => {
    setCurrentTool(tool);
    setTestParams('{}');
    setTestModalVisible(true);
  };

  const columns = [
    { title: '工具ID', dataIndex: 'id', key: 'id', width: 150 },
    { title: '工具名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description' },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags) => (
        <>
          {tags.map(tag => <Tag key={tag} size="small">{tag}</Tag>)}
        </>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Button
          type="text"
          icon={<PlayCircleOutlined />}
          onClick={() => handleTestTool(record)}
        >
          测试调用
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>工具管理(Tools)</Title>
        <Button icon={<ReloadOutlined />} onClick={fetchToolList} loading={loading}>
          刷新列表
        </Button>
      </Space>
      <Table
        columns={columns}
        dataSource={toolList}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title={`测试工具：${currentTool?.name}`}
        open={testModalVisible}
        onOk={async () => {
          try {
            await toolApi.testToolCall(currentTool.id, JSON.parse(testParams));
            message.success('工具调用成功');
            setTestModalVisible(false);
          } catch (e) {
            message.error('调用失败');
          }
        }}
        onCancel={() => setTestModalVisible(false)}
      >
        <Form.Item label="调用参数（JSON）">
          <Input.TextArea
            rows={4}
            value={testParams}
            onChange={(e) => setTestParams(e.target.value)}
          />
        </Form.Item>
      </Modal>
    </div>
  );
};

export default Tools;