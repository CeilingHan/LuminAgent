import React, { useState } from 'react';
import { Form, Button, Input, Select, Card, Typography, Space, Tabs, message } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { agentApi } from '../api';

const { Title, Text, Code } = Typography;
const { Option } = Select;
const { TabPane } = Tabs;

const ApiTest = () => {
  // 状态管理
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState('');
  const [responseStatus, setResponseStatus] = useState(''); // success/error/empty

  // 预设技能列表（实际可从接口获取）
  const skillOptions = [
    { id: 'Browser use', name: '浏览器使用' },
    { id: 'Python Execute', name: 'Python代码执行' },
    { id: 'Ask human', name: '询问人类' },
    { id: 'Replace String', name: '字符串替换' },
    { id: 'Planning', name: '任务规划' },
  ];

  // 调用Agent技能
  const handleCallSkill = async () => {
    try {
      setLoading(true);
      setResponse('');
      setResponseStatus('');

      const values = form.getFieldsValue();
      const requestData = {
        skillId: values.skillId,
        agentName: 'Manus Agent',
        parameters: JSON.parse(values.parameters || '{}'),
      };

      // 调用后端接口
      const res = await agentApi.callAgentSkill(requestData);
      
      // 格式化响应
      setResponse(JSON.stringify(res, null, 2));
      setResponseStatus('success');
      message.success('技能调用成功');
    } catch (error) {
      setResponse(JSON.stringify(error.response?.data || error.message, null, 2));
      setResponseStatus('error');
      message.error('技能调用失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Title level={3}>API测试 - 技能调用</Title>
      <Tabs defaultActiveKey="1">
        <TabPane tab="技能调用" key="1">
          <Card style={{ marginBottom: 16 }}>
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                skillId: 'Browser use',
                parameters: '{"url": "https://www.baidu.com"}',
              }}
            >
              <Form.Item
                name="skillId"
                label="选择技能"
                rules={[{ required: true, message: '请选择要调用的技能' }]}
              >
                <Select style={{ width: '100%' }}>
                  {skillOptions.map(skill => (
                    <Option key={skill.id} value={skill.id}>
                      {skill.name} ({skill.id})
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item
                name="parameters"
                label="调用参数（JSON格式）"
                rules={[
                  { required: true, message: '请输入调用参数' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      try {
                        JSON.parse(value);
                        return Promise.resolve();
                      } catch (e) {
                        return Promise.reject(new Error('请输入合法的JSON格式'));
                      }
                    },
                  }),
                ]}
              >
                <Input.TextArea
                  rows={6}
                  placeholder='例如：{"url": "https://www.baidu.com"}'
                  style={{ fontFamily: 'monospace' }}
                />
              </Form.Item>

              <Form.Item>
                <Space>
                  <Button 
                    type="primary" 
                    icon={<SendOutlined />} 
                    onClick={handleCallSkill}
                    loading={loading}
                  >
                    发送请求
                  </Button>
                  <Button 
                    onClick={() => {
                      form.resetFields();
                      setResponse('');
                      setResponseStatus('');
                    }}
                  >
                    重置
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>

          {/* 响应结果 */}
          <Card title="响应结果">
            {response ? (
              <Code
                style={{ 
                  backgroundColor: responseStatus === 'success' ? '#f6ffed' : '#fff2f0',
                  color: responseStatus === 'success' ? '#52c41a' : '#f5222d',
                  minHeight: '200px',
                  whiteSpace: 'pre-wrap'
                }}
              >
                {response}
              </Code>
            ) : (
              <Text type="secondary">未发起请求，点击"发送请求"后显示响应结果</Text>
            )}
          </Card>
        </TabPane>

        <TabPane tab="接口文档" key="2">
          <Card>
            <Title level={4}>技能调用接口说明</Title>
            <Text strong>接口地址：</Text> <Code>/agent/skill/call</Code>
            <br />
            <Text strong>请求方法：</Text> <Code>POST</Code>
            <br />
            <Text strong>请求头：</Text> <Code>Content-Type: application/json</Code>
            <br />
            <Text strong>请求参数示例：</Text>
            <Code block>
{`{
  "skillId": "Browser use",
  "agentName": "Manus Agent",
  "parameters": {
    "url": "https://www.baidu.com"
  }
}`}
            </Code>
            <Text strong>响应成功示例：</Text>
            <Code block>
{`{
  "code": 200,
  "message": "success",
  "data": {
    "result": "页面内容：百度首页...",
    "skillId": "Browser use",
    "executionTime": 1200
  }
}`}
            </Code>
          </Card>
        </TabPane>
      </Tabs>
    </div>
  );
};

export default ApiTest;