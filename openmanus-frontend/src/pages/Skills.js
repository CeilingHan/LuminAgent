import React, { useState, useEffect } from 'react';
import { Table, Tag, Button, Space, Modal, Form, Input, Select, Typography, message, Switch } from 'antd';
import { EditOutlined, DeleteOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { skillApi } from '../api';

const { Title, Text } = Typography;
const { Option } = Select;

const Skills = () => {
  // 状态管理
  const [skillList, setSkillList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingSkill, setEditingSkill] = useState(null);
  const [form] = Form.useForm();

  // 获取技能列表
  const fetchSkillList = async () => {
    try {
      setLoading(true);
      const res = await skillApi.getSkillList();
      setSkillList(res || []);
    } catch (error) {
      message.error('获取技能列表失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSkillList();
  }, []);

  // 切换技能启用状态
  const handleToggleSkill = async (skillId, enabled) => {
    try {
      await skillApi.toggleSkillStatus(skillId, !enabled);
      setSkillList(
        skillList.map(skill => 
          skill.id === skillId ? { ...skill, enabled: !enabled } : skill
        )
      );
      message.success(`技能已${!enabled ? '启用' : '禁用'}`);
    } catch (error) {
      message.error(`切换技能状态失败`);
      console.error(error);
    }
  };

  // 打开编辑/新增弹窗
  const handleOpenModal = (skill = null) => {
    setEditingSkill(skill);
    form.setFieldsValue(skill || {
      id: '',
      name: '',
      description: '',
      tags: [],
      enabled: true,
    });
    setModalVisible(true);
  };

  // 保存技能（新增/编辑）
  const handleSaveSkill = async () => {
    try {
      const values = form.getFieldsValue();
      // 实际项目中替换为新增/编辑接口
      if (editingSkill) {
        // 编辑逻辑
        setSkillList(
          skillList.map(skill => 
            skill.id === editingSkill.id ? { ...skill, ...values } : skill
          )
        );
        message.success('技能编辑成功');
      } else {
        // 新增逻辑
        const newSkill = {
          id: values.id || `skill_${Date.now()}`,
          ...values,
          examples: [],
          tool_class: null,
        };
        setSkillList([...skillList, newSkill]);
        message.success('技能新增成功');
      }
      setModalVisible(false);
    } catch (error) {
      message.error('保存技能失败');
      console.error(error);
    }
  };

  // 列配置
  const columns = [
    {
      title: '技能ID',
      dataIndex: 'id',
      key: 'id',
      width: 150,
    },
    {
      title: '技能名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags) => (
        <>
          {tags.map(tag => (
            <Tag key={tag} size="small">{tag}</Tag>
          ))}
        </>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled) => (
        <Switch
          checked={enabled}
          onChange={(checked) => handleToggleSkill(editingSkill?.id || '', enabled)}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="small">
          <Button 
            type="text" 
            icon={<EditOutlined />} 
            onClick={() => handleOpenModal(record)}
          >
            编辑
          </Button>
          <Button 
            type="text" 
            danger 
            icon={<DeleteOutlined />}
            onClick={() => {
              setSkillList(skillList.filter(skill => skill.id !== record.id));
              message.success('技能已删除');
            }}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>技能管理(Skills)</Title>
        <Button 
          type="primary" 
          icon={<PlusOutlined />} 
          onClick={() => handleOpenModal()}
        >
          新增技能
        </Button>
        <Button 
          icon={<ReloadOutlined />} 
          onClick={fetchSkillList}
          loading={loading}
        >
          刷新列表
        </Button>
      </Space>

      <Table
        columns={columns}
        dataSource={skillList}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: '暂无技能数据' }}
      />

      {/* 新增/编辑技能弹窗 */}
      <Modal
        title={editingSkill ? '编辑技能' : '新增技能'}
        open={modalVisible}
        onOk={handleSaveSkill}
        onCancel={() => setModalVisible(false)}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
        >
          <Form.Item
            name="id"
            label="技能ID"
            rules={[{ required: true, message: '请输入技能ID' }]}
            disabled={!!editingSkill}
          >
            <Input placeholder="例如：Browser use" />
          </Form.Item>
          <Form.Item
            name="name"
            label="技能名称"
            rules={[{ required: true, message: '请输入技能名称' }]}
          >
            <Input placeholder="例如：Browser use Tool" />
          </Form.Item>
          <Form.Item
            name="description"
            label="技能描述"
            rules={[{ required: true, message: '请输入技能描述' }]}
          >
            <Input.TextArea rows={4} placeholder="详细描述技能功能" />
          </Form.Item>
          <Form.Item
            name="tags"
            label="技能标签"
            rules={[{ required: true, message: '请选择技能标签' }]}
          >
            <Select
              mode="tags"
              placeholder="请输入或选择标签（如：Use Browser）"
            >
              <Option value="Use Browser">Use Browser</Option>
              <Option value="Execute Python Code">Execute Python Code</Option>
              <Option value="Ask human for help">Ask human for help</Option>
              <Option value="Task Planning">Task Planning</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="enabled"
            label="启用状态"
            valuePropName="checked"
          >
            <Switch defaultChecked />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Skills;