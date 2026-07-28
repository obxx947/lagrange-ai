/**
 * 拉格朗日AI - 主入口 (React SPA)
 * 当前版本使用 static/index.html 作为一体化前端
 * 此文件为 webpack 构建预留入口点
 */
import React from 'react';
import { createRoot } from 'react-dom/client';

const App: React.FC = () => {
  // 重定向到 static/index.html 一体化前端
  React.useEffect(() => {
    window.location.href = '/static/index.html';
  }, []);

  return (
    <div style={{ 
      background: '#0a0e1a', color: '#e8f4ff', minHeight: '100vh',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Microsoft YaHei, sans-serif'
    }}>
      <div style={{ textAlign: 'center' }}>
        <h1>🚀 拉格朗日AI 战术推演中心</h1>
        <p>正在跳转到一体化前端...</p>
        <a href="/static/index.html" style={{ color: '#4a9eff' }}>点击此处直接访问</a>
      </div>
    </div>
  );
};

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<App />);
}
