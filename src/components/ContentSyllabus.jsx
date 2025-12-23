import React, { useState } from 'react';
import { editalData } from '../data/edital';
import { useSyllabus } from '../hooks/useSupabaseData';
import { CheckCircle2, Circle, AlertCircle, Info, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

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
  return (
    <div className="mb-6 last:mb-0">
      <h4 className="font-serif text-lg font-bold text-slate-700 mb-3 pl-2 border-l-2 border-crimson-300">
        {group.title}
      </h4>
      <div className="space-y-3">
        {group.items.map(item => (
          <div 
            key={item.id} 
            className={clsx(
              "flex items-start p-3 rounded-lg border transition-all cursor-pointer hover:shadow-md",
              checkedItems[item.id] ? "bg-crimson-50 border-crimson-100" : "bg-white border-slate-200 hover:border-crimson-200"
            )}
            onClick={() => onToggle(item.id)}
          >
            <div className="mt-0.5 mr-3 flex-shrink-0 text-crimson-600">
              {checkedItems[item.id] ? <CheckCircle2 size={20} /> : <Circle size={20} />}
            </div>
            <div className="flex-1">
              <div className="flex items-center flex-wrap gap-2">
                <span className={clsx("font-medium", checkedItems[item.id] ? "text-crimson-800 line-through decoration-crimson-300" : "text-slate-700")}>
                  {item.topic}
                </span>
                {item.priority === 'high' && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
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

function SubjectSection({ title, groups, meta, checkedItems, onToggle, colorTheme = 'crimson' }) {
  const [isOpen, setIsOpen] = useState(false);

  // Flatten items to calculate progress
  const allItems = groups.flatMap(g => g.items);
  const total = allItems.length;
  const completed = allItems.filter(item => checkedItems[item.id]).length;
  const progress = Math.round((completed / total) * 100) || 0;

  const colorMap = {
    crimson: 'text-red-700',
    emerald: 'text-emerald-700',
    indigo: 'text-indigo-700'
  };

  const barColorMap = {
    crimson: 'bg-red-600',
    emerald: 'bg-emerald-600',
    indigo: 'bg-indigo-600'
  };

  return (
    <div className={`bg-white rounded-xl shadow-sm border border-slate-100 p-6 mb-6 transition-all border-l-4 ${
      colorTheme === 'crimson' ? 'border-l-red-600' : 
      colorTheme === 'emerald' ? 'border-l-emerald-600' : 'border-l-indigo-600'
    }`}>
      <div 
        className="flex justify-between items-center mb-4 cursor-pointer"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center space-x-3">
          {isOpen ? <ChevronUp className="text-slate-400" /> : <ChevronDown className="text-slate-400" />}
          <h3 className={`font-serif text-2xl font-bold ${colorMap[colorTheme]}`}>{title}</h3>
        </div>
        <span className="text-sm font-medium text-slate-500">{progress}% Concluído</span>
      </div>
      
      <ProgressBar progress={progress} colorClass={barColorMap[colorTheme]} />

      {isOpen && (
        <div className="animate-in fade-in slide-in-from-top-2 duration-300">
          <SubjectMeta meta={meta} />

          <div className="space-y-6 mt-6">
            {groups.map((group, idx) => (
              <SubjectGroup 
                key={idx} 
                group={group} 
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
          title="História" 
          groups={editalData.historia.groups} 
          meta={editalData.historia.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          colorTheme="crimson"
        />
        <SubjectSection 
          title="Geografia" 
          groups={editalData.geografia.groups} 
          meta={editalData.geografia.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          colorTheme="emerald"
        />
        <SubjectSection 
          title="Matemática" 
          groups={editalData.matematica.groups} 
          meta={editalData.matematica.meta}
          checkedItems={checkedItems} 
          onToggle={handleToggle} 
          colorTheme="indigo"
        />
      </div>
    </div>
  );
}
