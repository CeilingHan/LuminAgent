// src/api/index.js
const API_BASE_URL = "http://localhost:8000";

// 对接 OpenManus MCP 后端
export const agentApi = {
  getAgentCard: () => fetch(`${API_BASE_URL}/`).then(res => res.json()),
  getAgentStatus: () => Promise.resolve({ online: true, name: "Manus Agent" }),
  callAgentSkill: (data) => fetch(`${API_BASE_URL}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: data.parameters,
      skillId: data.skillId
    })
  }).then(res => res.json()),
  getMultiAgentList: () => Promise.resolve([
    { id: "manus-1", name: "Manus Agent", status: "online", skills: ["BrowserUse", "PythonExecute"] }
  ])
};

export const skillApi = {
  getSkillList: async () => {
    const res = await fetch(`${API_BASE_URL}/`);
    const data = await res.json();
    return (data.skills || []).map(s => ({
      id: s.id,
      name: s.name,
      description: s.description,
      tags: s.tags || [],
      enabled: true
    }));
  },
  toggleSkillStatus: () => Promise.resolve({})
};

export const toolApi = {
  getToolList: () => Promise.resolve([
    { id: "BrowserUse", name: "浏览器使用", description: "访问网页", tags: ["工具"] },
    { id: "PythonExecute", name: "Python代码执行", description: "执行Python", tags: ["工具"] },
    { id: "AskHuman", name: "询问人类", description: "人工交互", tags: ["工具"] }
  ])
};