import React, { useState } from 'react';
import { editalData } from '../data/edital';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { CheckCircle2, Circle, AlertCircle, Info, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

const THEMES = {
  rose: {
    title: 'text-rose-700',
    borderLeft: 'border-l-rose-500',
    bar: 'bg-rose-500',
    icon: 'text-rose-600',
    groupBorder: 'border-rose-200',
    checkedBg: 'bg-rose-50',
    checkedBorder: 'border-rose-100',
    checkedText: 'text-rose-900',
    uncheckedHover: 'hover:border-rose-200',
  },
  amber: {
    title: 'text-amber-800',
    borderLeft: 'border-l-amber-500',
    bar: 'bg-amber-500',
    icon: 'text-amber-600',
    groupBorder: 'border-amber-200',
    checkedBg: 'bg-amber-50',
    checkedBorder: 'border-amber-100',
    checkedText: 'text-amber-900',
    uncheckedHover: 'hover:border-amber-200',
  },
  violet: {
    title: 'text-violet-700',
    borderLeft: 'border-l-violet-500',
    bar: 'bg-violet-500',
    icon: 'text-violet-600',
    groupBorder: 'border-violet-200',
    checkedBg: 'bg-violet-50',
    checkedBorder: 'border-violet-100',
    checkedText: 'text-violet-900',
    uncheckedHover: 'hover:border-violet-200',
  },
  sky: {
    title: 'text-sky-700',
    borderLeft: 'border-l-sky-500',
    bar: 'bg-sky-500',
    icon: 'text-sky-600',
    groupBorder: 'border-sky-200',
    checkedBg: 'bg-sky-50',
    checkedBorder: 'border-sky-100',
    checkedText: 'text-sky-900',
    uncheckedHover: 'hover:border-sky-200',
  },
  indigo: {
    title: 'text-indigo-700',
    borderLeft: 'border-l-indigo-500',
    bar: 'bg-indigo-500',
    icon: 'text-indigo-600',
    groupBorder: 'border-indigo-200',
    checkedBg: 'bg-indigo-50',
    checkedBorder: 'border-indigo-100',
    checkedText: 'text-indigo-900',
    uncheckedHover: 'hover:border-indigo-200',
  },
  cyan: {
    title: 'text-cyan-700',
    borderLeft: 'border-l-cyan-500',
    bar: 'bg-cyan-500',
    icon: 'text-cyan-600',
    groupBorder: 'border-cyan-200',
    checkedBg: 'bg-cyan-50',
    checkedBorder: 'border-cyan-100',
    checkedText: 'text-cyan-900',
    uncheckedHover: 'hover:border-cyan-200',
  },
  emerald: {
    title: 'text-emerald-700',
    borderLeft: 'border-l-emerald-500',
    bar: 'bg-emerald-500',
    icon: 'text-emerald-600',
    groupBorder: 'border-emerald-200',
    checkedBg: 'bg-emerald-50',
    checkedBorder: 'border-emerald-100',
    checkedText: 'text-emerald-900',
    uncheckedHover: 'hover:border-emerald-200',
  },
  lime: {
    title: 'text-lime-800',
    borderLeft: 'border-l-lime-500',
    bar: 'bg-lime-500',
    icon: 'text-lime-700',
    groupBorder: 'border-lime-200',
    checkedBg: 'bg-lime-50',
    checkedBorder: 'border-lime-100',
    checkedText: 'text-lime-900',
    uncheckedHover: 'hover:border-lime-200',
  },
};

function getTheme(themeKey) {
  return THEMES[themeKey] || THEMES.violet;
}

function ProgressBar({ progress, colorClass = 'bg-crimson-600' }) {
  return (
    <div className="w-full bg-slate-200 rounded-full h-2.5 mb-4">
      <div 
        className={`h-2.5 rounded-full transition-all duration-500 ${colorClass}`} 
        style={{ width: `${progress}%` }}
      ></div>
    </div>
  );
}

function SubjectMeta({ meta }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mb-6 border border-slate-200 rounded-lg overflow-hidden">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 bg-slate-50 hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center space-x-2 text-slate-700">
          <Info size={20} className="text-crimson-600" />
          <span className="font-semibold">Competências e Habilidades Exigidas</span>
        </div>
        {isOpen ? <ChevronUp size={20} className="text-slate-500" /> : <ChevronDown size={20} className="text-slate-500" />}
      </button>
      
      {isOpen && (
        <div className="p-4 bg-white space-y-4 text-sm text-slate-600">
          <div>
            <h5 className="font-bold text-slate-800 mb-2">Área: {meta.description}</h5>
            <ul className="list-disc list-inside space-y-1">
              {meta.competencies.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
          <div>
            <h5 className="font-bold text-slate-800 mb-2">Principais Habilidades:</h5>
            <ul className="list-disc list-inside space-y-1 text-slate-500">
              {meta.skills.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function SubjectGroup({ group, checkedItems, onToggle }) {
  const theme = getTheme(group.themeKey);
  return (
    <div className="mb-6 last:mb-0">
      <h4 className={clsx(
        "font-serif text-lg font-bold text-slate-700 mb-3 pl-2 border-l-2",
        theme.groupBorder
      )}>
        {group.title}
      </h4>
      <div className="space-y-3">
        {group.items.map(item => (
          <div 
            key={item.id} 
            className={clsx(
              "flex items-start p-3 rounded-lg border transition-all cursor-pointer hover:shadow-md",
              checkedItems[item.id]
                ? `${theme.checkedBg} ${theme.checkedBorder}`
                : `bg-white border-slate-200 ${theme.uncheckedHover}`
            )}
            onClick={() => onToggle(item.id)}
          >
            <div className={clsx("mt-0.5 mr-3 flex-shrink-0", theme.icon)}>
              {checkedItems[item.id] ? <CheckCircle2 size={20} /> : <Circle size={20} />}
            </div>
            <div className="flex-1">
              <div className="flex items-center flex-wrap gap-2">
                <span className={clsx(
                  "font-medium",
                  checkedItems[item.id]
                    ? `${theme.checkedText} line-through decoration-slate-300`
                    : "text-slate-700"
                )}>
                  {item.topic}
                </span>
                {item.priority === 'high' && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-rose-100 text-rose-800">
                    <AlertCircle size={12} className="mr-1" /> Alta Prioridade
                  </span>
                )}
                {item.priority === 'medium' && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                    Média
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SubjectSection({ title, groups, meta, checkedItems, onToggle, themeKey = 'violet' }) {
  const [isOpen, setIsOpen] = useState(false);
  const theme = getTheme(themeKey);

  // Flatten items to calculate progress
  const allItems = groups.flatMap(g => g.items);
  const total = allItems.length;
  const completed = allItems.filter(item => checkedItems[item.id]).length;
  const progress = Math.round((completed / total) * 100) || 0;

  return (
    <div className={clsx(
      'ui-card rounded-2xl p-6 mb-6 transition-all border-l-4',
      theme.borderLeft
    )}>
      <div 
        className="flex justify-between items-center mb-4 cursor-pointer"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center space-x-3">
          {isOpen ? <ChevronUp className="text-slate-400" /> : <ChevronDown className="text-slate-400" />}
          <h3 className={clsx('font-serif text-2xl font-bold', theme.title)}>{title}</h3>
        </div>
        <span className="text-sm font-medium text-slate-500">{progress}% Concluído</span>
      </div>
      
      <ProgressBar progress={progress} colorClass={theme.bar} />

      {isOpen && (
        <div className="animate-in fade-in slide-in-from-top-2 duration-300">
          <SubjectMeta meta={meta} />

          <div className="space-y-6 mt-6">
            {groups.map((group, idx) => (
              <SubjectGroup 
                key={idx} 
                group={{...group, themeKey}} 
                checkedItems={checkedItems} 
                onToggle={onToggle} 
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function ContentSyllabus() {
  const [checkedItems, setCheckedItems] = useLocalStorage('sanfran-syllabus-check', {});

  const handleToggle = (id) => {
    setCheckedItems(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
    window.localStorage.setItem('sanfran-last-activity', new Date().toISOString());
  };

  return (
    <div className="p-8 max-w-5xl mx-auto pb-20">
      <h2 className="font-serif text-3xl font-bold text-slate-800 mb-6 border-l-4 border-crimson-600 pl-4">
        Edital Verticalizado Interativo
      </h2>
      <p className="text-slate-600 mb-8">
        Conteúdo programático baseado no Anexo II do Edital da Fuvest 2026. 
        Organize seus estudos por grandes temas.
      </p>

      <div className="grid gap-8">
        <SubjectSection 
          title="Português" 
          groups={editalData.portugues.groups} 
          meta={editalData.portugues.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          themeKey="rose"
        />
        <SubjectSection 
          title="Literatura" 
          groups={editalData.literatura.groups} 
          meta={editalData.literatura.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          themeKey="amber"
        />
        <SubjectSection 
          title="Física" 
          groups={editalData.fisica.groups} 
          meta={editalData.fisica.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          themeKey="indigo"
        />
        <SubjectSection 
          title="Química" 
          groups={editalData.quimica.groups} 
          meta={editalData.quimica.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          themeKey="cyan"
        />
        <SubjectSection 
          title="Biologia" 
          groups={editalData.biologia.groups} 
          meta={editalData.biologia.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          themeKey="lime"
        />
        <SubjectSection 
          title="Redação" 
          groups={editalData.redacao.groups} 
          meta={editalData.redacao.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          themeKey="violet"
        />
        <SubjectSection 
          title="História" 
          groups={editalData.historia.groups} 
          meta={editalData.historia.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          themeKey="amber"
        />
        <SubjectSection 
          title="Geografia" 
          groups={editalData.geografia.groups} 
          meta={editalData.geografia.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          themeKey="emerald"
        />
        <SubjectSection 
          title="Matemática" 
          groups={editalData.matematica.groups} 
          meta={editalData.matematica.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          themeKey="sky"
        />
      </div>
    </div>
  );
}
