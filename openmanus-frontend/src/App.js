import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import MainLayout from './layout/MainLayout';
import Dashboard from './pages/Dashboard';
import Skills from './pages/Skills';
import Tools from './pages/Tools';
import MultiAgent from './pages/MultiAgent';
import Chat from './pages/Chat';
import ApiTest from './pages/ApiTest';
import ScheduledTasks from './pages/ScheduledTasks';
import MemoryManager from './pages/MemoryManager';
import './App.css';

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <Router>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Chat />} />
            <Route path="chat" element={<Chat />} />
            <Route path="multi-agent" element={<MultiAgent />} />
            <Route path="scheduled-tasks" element={<ScheduledTasks />} />
            <Route path="memory" element={<MemoryManager />} />
            <Route path="api-test" element={<ApiTest />} />
            <Route path="skills" element={<Skills />} />
            <Route path="tools" element={<Tools />} />
            <Route path="dashboard" element={<Dashboard />} />
          </Route>
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;