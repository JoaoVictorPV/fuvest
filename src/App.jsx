import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { ContentSyllabus } from './components/ContentSyllabus';
import { Readings } from './components/Readings';
import { Simulados } from './components/Simulados';
import { Questoes } from './components/Questoes';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  
  return (
    <div className="bg-slate-100 min-h-screen font-sans text-slate-800">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      <Header />
      
      <main className="ml-64 pt-16 min-h-screen">
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
