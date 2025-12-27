import React from 'react';
import { LayoutDashboard, BookOpen, Library, GraduationCap, FileQuestion, X } from 'lucide-react';

export function Sidebar({ activeTab, setActiveTab, variant = 'desktop', onClose }) {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'conteudo', label: 'Conteúdo', icon: BookOpen },
    { id: 'leituras', label: 'Leituras', icon: Library },
    { id: 'simulados', label: 'Simulados', icon: GraduationCap },
    { id: 'questoes', label: 'Questões', icon: FileQuestion },
  ];

  const isMobile = variant === 'mobile';

  const SidebarInner = (
    <aside className="h-screen w-72 md:w-64 glass text-slate-900 flex flex-col shadow-soft border-r border-white/40">
      <div className="p-6 border-b border-white/40 flex items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-xl font-bold tracking-tight">
            <span className="text-slate-900">Projeto</span>{' '}
            <span className="text-crimson-700">de Estudo</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">Foco: Direito USP</p>
        </div>

        {isMobile && (
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-white/70 text-slate-600 border border-white/40"
            aria-label="Fechar menu"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <nav className="flex-1 p-4 space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const active = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 border ${
                active
                  ? 'bg-white/80 text-slate-900 border-white/60 shadow-brutal'
                  : 'text-slate-700 border-transparent hover:bg-white/70 hover:text-slate-900'
              }`}
            >
              <span className={`w-2.5 h-2.5 rounded-full ${active ? 'bg-crimson-600' : 'bg-slate-300'}`} />
              <Icon size={18} className={active ? 'text-crimson-700' : 'text-slate-500'} />
              <span className="font-semibold">{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="p-4 text-[11px] text-slate-500 border-t border-white/40">
        <div className="flex items-center justify-between">
          <span className="font-semibold">UI</span>
          <span className="px-2 py-0.5 rounded-full bg-white/70 border border-white/40">Pastel + Brutal</span>
        </div>
      </div>
    </aside>
  );

  if (!isMobile) {
    return (
      <div className="fixed left-0 top-0 z-20">{SidebarInner}</div>
    );
  }

  return (
    <div className="fixed inset-0 z-40">
      <button
        type="button"
        onClick={onClose}
        className="absolute inset-0 bg-black/50"
        aria-label="Fechar menu"
      />
      <div className="absolute left-0 top-0 h-full animate-in slide-in-from-left duration-200">
        {SidebarInner}
      </div>
    </div>
  );
}
