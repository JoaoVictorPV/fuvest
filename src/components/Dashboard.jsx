import React, { useState, useEffect } from 'react';
import { editalData } from '../data/edital';
import { booksData } from '../data/books';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Tooltip } from 'recharts';
import { AlertTriangle, TrendingUp, BookOpen, CheckCircle, Save, Trash2, PenTool } from 'lucide-react';
import { differenceInDays, format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

function Notepad() {
  const [notes, setNotes] = useLocalStorage('sanfran-notes', []);
  const [currentNote, setCurrentNote] = useState('');

  const handleSave = () => {
    if (!currentNote.trim()) return;
    
    const newNote = {
      id: Date.now(),
      text: currentNote,
      date: new Date().toISOString()
    };

    setNotes([newNote, ...notes]);
    setCurrentNote('');
  };

  const handleDelete = (id) => {
    setNotes(notes.filter(n => n.id !== id));
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex flex-col h-full">
      <div className="flex items-center space-x-2 mb-4 text-slate-800">
        <PenTool size={20} className="text-crimson-600" />
        <h3 className="font-serif text-xl font-bold">Bloco de Notas</h3>
      </div>

      <div className="mb-4">
        <textarea
          value={currentNote}
          onChange={(e) => setCurrentNote(e.target.value)}
          placeholder="Digite sua anotação ou link aqui..."
          className="w-full p-3 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-crimson-500 resize-none h-24"
        />
        <button
          onClick={handleSave}
          disabled={!currentNote.trim()}
          className="mt-2 w-full flex items-center justify-center bg-crimson-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-crimson-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Save size={16} className="mr-2" /> Salvar Nota
        </button>
      </div>

      <div className="flex-1 overflow-y-auto max-h-60 space-y-3 pr-1">
        {notes.length === 0 ? (
          <p className="text-center text-slate-400 text-sm py-4">Nenhuma nota salva.</p>
        ) : (
          notes.map(note => (
            <div key={note.id} className="bg-slate-50 p-3 rounded-lg border border-slate-100 relative group">
              <p className="text-slate-700 text-sm whitespace-pre-wrap">{note.text}</p>
              <div className="mt-2 flex justify-between items-center">
                <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">
                  {format(new Date(note.date), "d 'de' MMM. 'às' HH:mm", { locale: ptBR })}
                </span>
                <button 
                  onClick={() => handleDelete(note.id)}
                  className="text-slate-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, colorClass }) {
  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex items-center space-x-4">
      <div className={`p-3 rounded-full ${colorClass} bg-opacity-10`}>
        <Icon size={24} className={colorClass.replace('bg-', 'text-')} />
      </div>
      <div>
        <p className="text-sm text-slate-500 font-medium">{label}</p>
        <p className="text-2xl font-bold text-slate-800">{value}</p>
      </div>
    </div>
  );
}

export function Dashboard() {
  const [checkedItems] = useLocalStorage('sanfran-syllabus-check', {});
  const [bookStatus] = useLocalStorage('sanfran-books-status', {});
  const [lastActivity] = useState(() => window.localStorage.getItem('sanfran-last-activity'));
  const [showAlert, setShowAlert] = useState(false);

  useEffect(() => {
    if (lastActivity) {
      const days = differenceInDays(new Date(), new Date(lastActivity));
      if (days >= 3) {
        setShowAlert(true);
      }
    }
  }, [lastActivity]);

  // Calculate Progress with nested structure
  const flattenItems = (groups) => groups.flatMap(g => g.items);

  const calculateProgress = (groups) => {
    const allItems = flattenItems(groups);
    const total = allItems.length;
    const completed = allItems.filter(item => checkedItems[item.id]).length;
    return Math.round((completed / total) * 100) || 0;
  };

  const histProgress = calculateProgress(editalData.historia.groups);
  const geoProgress = calculateProgress(editalData.geografia.groups);
  const matProgress = calculateProgress(editalData.matematica.groups);
  
  const totalEditalProgress = Math.round(
    ((histProgress + geoProgress + matProgress) / 300) * 100
  );

  const booksRead = booksData.filter(b => {
    const s = bookStatus[b.id];
    return s === 'read' || s === 'summarized';
  }).length;

  const radarData = [
    { subject: 'História', A: histProgress, fullMark: 100 },
    { subject: 'Geografia', A: geoProgress, fullMark: 100 },
    { subject: 'Matemática', A: matProgress, fullMark: 100 },
  ];

  // Subject Colors Configuration
  const subjectColors = {
    'História': {
      bg: 'bg-red-50',
      border: 'border-red-100',
      text: 'text-red-800',
      title: 'text-red-600',
      dot: 'bg-red-500'
    },
    'Geografia': {
      bg: 'bg-emerald-50',
      border: 'border-emerald-100',
      text: 'text-emerald-800',
      title: 'text-emerald-600',
      dot: 'bg-emerald-500'
    },
    'Matemática': {
      bg: 'bg-indigo-50',
      border: 'border-indigo-100',
      text: 'text-indigo-800',
      title: 'text-indigo-600',
      dot: 'bg-indigo-500'
    }
  };

  // Helper to get suggestions
  const getSuggestions = () => {
    const extract = (groups, subjectName) => 
      groups.flatMap(g => g.items.map(i => ({...i, subject: subjectName})));

    const allHist = extract(editalData.historia.groups, 'História');
    const allGeo = extract(editalData.geografia.groups, 'Geografia');
    const allMat = extract(editalData.matematica.groups, 'Matemática');

    const uncheckedHist = allHist.filter(i => !checkedItems[i.id]);
    const uncheckedGeo = allGeo.filter(i => !checkedItems[i.id]);
    const uncheckedMat = allMat.filter(i => !checkedItems[i.id]);

    const pMap = { 'high': 3, 'medium': 2, 'normal': 1 };
    const sortFn = (a, b) => pMap[b.priority] - pMap[a.priority];

    uncheckedHist.sort(sortFn);
    uncheckedGeo.sort(sortFn);
    uncheckedMat.sort(sortFn);

    const suggestions = [];
    const limitPerSubject = 2;

    for (let i = 0; i < limitPerSubject; i++) {
        if (uncheckedHist[i]) suggestions.push(uncheckedHist[i]);
        if (uncheckedGeo[i]) suggestions.push(uncheckedGeo[i]);
        if (uncheckedMat[i]) suggestions.push(uncheckedMat[i]);
    }

    return suggestions;
  };

  const suggestions = getSuggestions();

  return (
    <div className="p-8 max-w-6xl mx-auto pb-20">
      <div className="mb-8">
        <h2 className="font-serif text-3xl font-bold text-slate-800 mb-2">Painel de Controle</h2>
        <p className="text-slate-600">Bem-vindo, futuro sanfraniano.</p>
      </div>

      {showAlert && (
        <div className="bg-red-50 border-l-4 border-red-600 p-6 mb-8 rounded-r-lg shadow-sm animate-pulse">
          <div className="flex items-start">
            <AlertTriangle className="text-red-600 mr-4 mt-1" size={24} />
            <div>
              <h3 className="text-red-800 font-bold text-lg mb-1">ATENÇÃO, GUERREIRO!</h3>
              <p className="text-red-700 italic">
                "A disciplina é a ponte entre metas e realizações. Você está há mais de 3 dias sem registrar progresso.
                O sucesso não aceita preguiça. Retome o comando agora!"
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard 
          icon={TrendingUp} 
          label="Progresso Geral" 
          value={`${totalEditalProgress}%`} 
          colorClass="bg-blue-500 text-blue-600" 
        />
        <StatCard 
          icon={BookOpen} 
          label="Leituras" 
          value={`${booksRead}/${booksData.length}`} 
          colorClass="bg-emerald-500 text-emerald-600" 
        />
        <StatCard 
          icon={CheckCircle} 
          label="Tópicos Vencidos" 
          value={Object.keys(checkedItems).filter(k => checkedItems[k]).length} 
          colorClass="bg-crimson-500 text-crimson-600" 
        />
         <StatCard 
          icon={CheckCircle} 
          label="Dias Restantes" 
          value={differenceInDays(new Date('2026-11-15'), new Date())} 
          colorClass="bg-amber-500 text-amber-600" 
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 flex flex-col">
          <h3 className="font-serif text-xl font-bold text-slate-800 mb-6">Desempenho por Matéria</h3>
          <div className="flex-1 flex items-center justify-center min-h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                <defs>
                  <linearGradient id="radarFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#990000" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#990000" stopOpacity={0.1}/>
                  </linearGradient>
                </defs>
                <PolarGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                <PolarAngleAxis 
                  dataKey="subject" 
                  tick={{ fill: '#334155', fontSize: 14, fontWeight: 600 }} 
                />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                <Radar
                  name="Progresso"
                  dataKey="A"
                  stroke="#990000"
                  strokeWidth={3}
                  fill="url(#radarFill)"
                  fillOpacity={0.6}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  itemStyle={{ color: '#990000', fontWeight: 'bold' }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
          <h3 className="font-serif text-xl font-bold text-slate-800 mb-6">Próximos Passos Sugeridos</h3>
          <div className="space-y-4">
             {suggestions.length > 0 ? (
               suggestions.map(item => {
                 const colors = subjectColors[item.subject] || subjectColors['História']; // Fallback
                 return (
                   <div key={item.id} className={`p-4 rounded-lg border flex items-start ${colors.bg} ${colors.border}`}>
                     <div className={`mt-1 mr-3 w-2 h-2 rounded-full ${colors.dot}`}></div>
                     <div>
                       <div className="flex items-center gap-2 mb-1">
                         <span className={`text-xs font-bold uppercase ${colors.title}`}>
                           {item.subject}
                         </span>
                         {item.priority === 'high' && (
                           <span className="text-[10px] bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-bold">
                             ALTA
                           </span>
                         )}
                       </div>
                       <p className={`font-medium ${colors.text}`}>{item.topic}</p>
                     </div>
                   </div>
                 );
               })
             ) : (
               <p className="text-center text-green-600 font-bold">Parabéns! Você está em dia com os tópicos de alta prioridade.</p>
             )}
          </div>
        </div>
      </div>

      <div className="mt-8 h-96">
        <Notepad />
      </div>
    </div>
  );
}
