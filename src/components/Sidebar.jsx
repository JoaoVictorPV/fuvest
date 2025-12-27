import React from 'react';
import { LayoutDashboard, BookOpen, Library, GraduationCap, FileQuestion } from 'lucide-react';

export function Sidebar({ activeTab, setActiveTab }) {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'conteudo', label: 'Conteúdo', icon: BookOpen },
    { id: 'leituras', label: 'Leituras', icon: Library },
    { id: 'simulados', label: 'Simulados', icon: GraduationCap },
    { id: 'questoes', label: 'Questões', icon: FileQuestion },
  ];

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-slate-900 text-white flex flex-col shadow-xl z-20">
      <div className="p-6 border-b border-slate-800">
        <h1 className="font-serif text-xl font-bold text-crimson-400">Projeto de Estudo</h1>
        <p className="text-xs text-slate-400 mt-1">Foco: Direito USP</p>
      </div>

      <nav className="flex-1 p-4 space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                activeTab === item.id
                  ? 'bg-crimson-700 text-white shadow-md shadow-crimson-900/20'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <Icon size={20} />
              <span className="font-medium">{item.label}</span>
            </button>
          );
        })}
      </nav>

    </aside>
  );
}
