import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { ContentSyllabus } from './components/ContentSyllabus';
import { Readings } from './components/Readings';
import { Simulados } from './components/Simulados';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Auth } from './components/Auth';

function AppContent() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const { session } = useAuth();

  if (!session) {
    return <Auth />;
  }

  return (
    <div className="bg-slate-100 min-h-screen font-sans text-slate-800">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      <Header />
      
      <main className="ml-64 pt-16 min-h-screen">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'conteudo' && <ContentSyllabus />}
        {activeTab === 'leituras' && <Readings />}
        {activeTab === 'simulados' && <Simulados />}
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
