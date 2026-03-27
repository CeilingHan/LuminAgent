import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import MainLayout from './layout/MainLayout';
import Dashboard from './pages/Dashboard';
import Skills from './pages/Skills';
import Tools from './pages/Tools'; // 可参考Skills页面实现
import MultiAgent from './pages/MultiAgent'; // 可参考Dashboard页面实现
import Chat from './pages/Chat';
import ApiTest from './pages/ApiTest';
import './App.css';

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <Router>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="skills" element={<Skills />} />
            <Route path="tools" element={<Tools />} />
            <Route path="multi-agent" element={<MultiAgent />} />
            <Route path="chat" element={<Chat />} />
            <Route path="api-test" element={<ApiTest />} />
          </Route>
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;