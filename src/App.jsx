import React, { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { ContentSyllabus } from './components/ContentSyllabus';
import { Readings } from './components/Readings';
import { Simulados } from './components/Simulados';
import { Questoes } from './components/Questoes';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // fecha sidebar mobile ao trocar de aba
  useEffect(() => {
    setMobileSidebarOpen(false);
  }, [activeTab]);
  
  return (
    <div className="min-h-screen font-sans text-slate-800">
      {/* Sidebar desktop */}
      <div className="hidden md:block">
        <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      </div>

      {/* Sidebar mobile (drawer) */}
      {mobileSidebarOpen && (
        <Sidebar
          variant="mobile"
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          onClose={() => setMobileSidebarOpen(false)}
        />
      )}

      <Header onOpenMenu={() => setMobileSidebarOpen(true)} />

      <main className="ml-0 md:ml-64 pt-16 min-h-screen">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'conteudo' && <ContentSyllabus />}
        {activeTab === 'leituras' && <Readings />}
        {activeTab === 'simulados' && <Simulados />}
        {activeTab === 'questoes' && <Questoes />}
      </main>
    </div>
  );
}

export default App;
