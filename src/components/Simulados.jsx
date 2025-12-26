import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { Plus, Trash2, Clock, CheckCircle2, X, Play, Save } from 'lucide-react';

// Anos disponíveis para simulados (sem 2021)
const AVAILABLE_YEARS = [2015, 2017, 2019, 2020, 2022, 2023, 2024, 2025, 2026];

// Função para gerar questões aleatórias
function generateRandomQuestions(totalQuestions) {
  // Distribuição aleatória entre anos
  const yearDistribution = {};
  const selectedYears = [];
  
  // Seleciona de 3 a 6 anos aleatoriamente
  const numYears = Math.floor(Math.random() * 4) + 3; // 3 a 6 anos
  const shuffledYears = [...AVAILABLE_YEARS].sort(() => Math.random() - 0.5);
  
  for (let i = 0; i < numYears && i < shuffledYears.length; i++) {
    selectedYears.push(shuffledYears[i]);
    yearDistribution[shuffledYears[i]] = 0;
  }
  
  // Distribui questões aleatoriamente entre os anos selecionados
  for (let i = 0; i < totalQuestions; i++) {
    const randomYear = selectedYears[Math.floor(Math.random() * selectedYears.length)];
    yearDistribution[randomYear]++;
  }
  
  return { yearDistribution, selectedYears };
}

// Modal de configuração
function ConfigModal({ onClose, onStart }) {
  const [numQuestions, setNumQuestions] = useState(30);
  const [timeMinutes, setTimeMinutes] = useState(90);
  
  const handleStart = () => {
    onStart({ numQuestions, timeMinutes });
  };
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl p-8">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full hover:bg-slate-100 text-slate-400"
        >
          <X size={20} />
        </button>
        
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-crimson-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Play size={32} className="text-crimson-600" />
          </div>
          <h2 className="text-2xl font-black text-slate-800">Criar Simulado</h2>
          <p className="text-sm text-slate-500 mt-2">Configure seu simulado personalizado</p>
        </div>
        
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-3">
              Número de Questões
            </label>
            <input
              type="number"
              min="1"
              max="90"
              value={numQuestions}
              onChange={(e) => setNumQuestions(Number(e.target.value))}
              placeholder="Ex: 30"
              className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:ring-2 focus:ring-crimson-500 focus:border-crimson-500 outline-none font-medium"
            />
            <p className="text-xs text-slate-500 mt-1">Escolha livremente de 1 a 90 questões</p>
          </div>
          
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-3">
              Tempo Limite
            </label>
            <input
              type="number"
              min="1"
              max="999"
              value={timeMinutes}
              onChange={(e) => setTimeMinutes(Number(e.target.value))}
              placeholder="Ex: 90"
              className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:ring-2 focus:ring-crimson-500 focus:border-crimson-500 outline-none font-medium"
            />
            <p className="text-xs text-slate-500 mt-1">Escolha livremente o tempo em minutos (1-999)</p>
          </div>
        </div>
        
        <button
          onClick={handleStart}
          className="w-full mt-8 bg-crimson-600 text-white py-4 rounded-2xl font-black text-lg hover:bg-crimson-700 transition-all shadow-lg hover:shadow-xl hover:-translate-y-1"
        >
          Iniciar Simulado
        </button>
      </div>
    </div>
  );
}

// Componente de Timer
function Timer({ startTime, durationMinutes }) {
  const [timeLeft, setTimeLeft] = useState(durationMinutes * 60);
  
  useEffect(() => {
    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const remaining = Math.max(0, durationMinutes * 60 - elapsed);
      setTimeLeft(remaining);
    }, 1000);
    
    return () => clearInterval(interval);
  }, [startTime, durationMinutes]);
  
  const hours = Math.floor(timeLeft / 3600);
  const minutes = Math.floor((timeLeft % 3600) / 60);
  const seconds = timeLeft % 60;
  
  const percentage = (timeLeft / (durationMinutes * 60)) * 100;
  let colorClass = 'text-emerald-600';
  if (percentage < 25) colorClass = 'text-red-600';
  else if (percentage < 50) colorClass = 'text-amber-600';
  
  return (
    <div className="flex items-center gap-3 bg-white px-4 py-3 rounded-2xl border-2 border-slate-200 shadow-sm">
      <Clock size={20} className={colorClass} />
      <div className="font-mono text-lg font-black ${colorClass} tabular-nums">
        {hours > 0 && `${hours}:`}{String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
      </div>
    </div>
  );
}

// Modal de Simulado Ativo
function SimuladoModal({ config, onClose, onFinish }) {
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(true);
  const [startTime] = useState(Date.now());
  
  useEffect(() => {
    async function loadQuestions() {
      setLoading(true);
      try {
        const { yearDistribution, selectedYears } = generateRandomQuestions(config.numQuestions);
        
        const allQuestions = [];
        
        // Carrega questões de cada ano
        for (const year of selectedYears) {
          const response = await fetch(`/data/questions/fuvest-${year}.json`);
          const data = await response.json();
          const yearQuestions = data.questions || [];
          
          // Seleciona aleatoriamente o número necessário de questões deste ano
          const needed = yearDistribution[year];
          const shuffled = [...yearQuestions].sort(() => Math.random() - 0.5);
          const selected = shuffled.slice(0, needed).map(q => ({ ...q, year }));
          
          allQuestions.push(...selected);
        }
        
        // Embaralha todas as questões selecionadas
        const finalQuestions = allQuestions.sort(() => Math.random() - 0.5);
        setQuestions(finalQuestions);
      } catch (err) {
        console.error('Erro ao carregar questões:', err);
      } finally {
        setLoading(false);
      }
    }
    
    loadQuestions();
  }, [config.numQuestions]);
  
  const handleAnswer = (questionId, optionKey) => {
    setAnswers({ ...answers, [questionId]: optionKey });
  };
  
  const handleFinish = () => {
    // Calcula resultado
    let correct = 0;
    questions.forEach(q => {
      if (answers[q.id] === q.answer.correct) {
        correct++;
      }
    });
    
    const result = {
      date: new Date().toISOString().split('T')[0],
      score: correct,
      total: questions.length,
      timeMinutes: config.timeMinutes,
      answers: answers,
      questions: questions.map(q => ({
        id: q.id,
        number: q.number,
        year: q.year,
        userAnswer: answers[q.id],
        correctAnswer: q.answer.correct
      }))
    };
    
    onFinish(result);
  };
  
  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
        <div className="bg-white p-8 rounded-3xl shadow-2xl">
          <p className="text-lg font-bold text-slate-700">Gerando simulado...</p>
        </div>
      </div>
    );
  }
  
  const currentQ = questions[currentIndex];
  const selectedAnswer = answers[currentQ?.id];
  
  return (
    <div className="fixed inset-0 z-50 bg-slate-50 overflow-y-auto">
      {/* Header fixo */}
      <div className="sticky top-0 bg-white border-b-2 border-slate-200 shadow-sm z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-sm font-black text-slate-700">
              Questão {currentIndex + 1} / {questions.length}
            </span>
            <div className="w-32 h-2 bg-slate-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-crimson-600 transition-all duration-300"
                style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
              />
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <Timer startTime={startTime} durationMinutes={config.timeMinutes} />
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl border-2 border-slate-200 hover:bg-slate-100 font-bold text-sm"
            >
              Cancelar
            </button>
            <button
              onClick={handleFinish}
              className="px-4 py-2 rounded-xl bg-crimson-600 text-white hover:bg-crimson-700 font-bold text-sm flex items-center gap-2"
            >
              <Save size={16} /> Finalizar
            </button>
          </div>
        </div>
      </div>
      
      {/* Conteúdo da questão */}
      <div className="max-w-4xl mx-auto p-8">
        <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-8">
          <div className="flex items-center gap-3 mb-6">
            <span className="bg-crimson-600 text-white text-xs font-black px-3 py-1 rounded-lg">
              Fuvest {currentQ.year}
            </span>
            <span className="bg-slate-100 text-slate-600 text-xs font-bold px-3 py-1 rounded-lg">
              Q{currentQ.number}
            </span>
          </div>
          
          <div className="mb-8">
            <p className="text-xl text-slate-800 leading-relaxed font-medium">
              {currentQ.stem}
            </p>
          </div>
          
          {currentQ.assets?.questionImage && (
            <div className="mb-8 p-6 bg-slate-50 rounded-3xl border-2 border-dashed border-slate-200 flex justify-center">
              <img 
                src={currentQ.assets.questionImage} 
                alt={`Questão ${currentQ.number}`}
                className="max-h-[400px] object-contain rounded-lg"
              />
            </div>
          )}
          
          <div className="grid grid-cols-1 gap-4">
            {currentQ.options.map((opt) => {
              const isSelected = selectedAnswer === opt.key;
              const style = isSelected 
                ? "border-crimson-600 bg-crimson-50 shadow-md ring-2 ring-crimson-600"
                : "border-slate-100 bg-slate-50/50 hover:border-slate-300 hover:bg-white hover:shadow-md";
              
              return (
                <button
                  key={opt.key}
                  onClick={() => handleAnswer(currentQ.id, opt.key)}
                  className={`w-full text-left p-5 rounded-2xl border-2 transition-all duration-300 flex items-center ${style}`}
                >
                  <span className={`w-10 h-10 rounded-xl flex items-center justify-center mr-5 text-base font-black border-2 transition-all ${
                    isSelected ? 'bg-crimson-600 border-crimson-600 text-white' : 'border-slate-200 text-slate-400'
                  }`}>
                    {opt.key}
                  </span>
                  <span className="flex-1 font-semibold text-slate-700 leading-snug">
                    {opt.text}
                  </span>
                  {isSelected && (
                    <CheckCircle2 size={24} className="text-crimson-600 ml-4" />
                  )}
                </button>
              );
            })}
          </div>
          
          <div className="mt-8 flex justify-between">
            <button
              onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}
              disabled={currentIndex === 0}
              className="px-6 py-3 rounded-2xl border-2 border-slate-200 hover:bg-slate-50 font-bold disabled:opacity-30"
            >
              ← Anterior
            </button>
            <button
              onClick={() => setCurrentIndex(Math.min(questions.length - 1, currentIndex + 1))}
              disabled={currentIndex === questions.length - 1}
              className="px-6 py-3 rounded-2xl border-2 border-slate-200 hover:bg-slate-50 font-bold disabled:opacity-30"
            >
              Próxima →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Simulados() {
  const [simulados, setSimulados] = useLocalStorage('sanfran-simulados', []);
  const [simuladosCompletos, setSimuladosCompletos] = useLocalStorage('sanfran-simulados-completos', []);
  const [formData, setFormData] = useState({ date: '', score: '' });
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [activeSimulado, setActiveSimulado] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.date || !formData.score) return;

    const newSimulado = {
      id: Date.now(),
      date: formData.date,
      score: Number(formData.score)
    };

    setSimulados([...simulados, newSimulado].sort((a, b) => new Date(a.date) - new Date(b.date)));
    setFormData({ date: '', score: '' });
  };

  const handleDelete = (id) => {
    setSimulados(simulados.filter(s => s.id !== id));
  };
  
  const handleDeleteCompleto = (id) => {
    setSimuladosCompletos(simuladosCompletos.filter(s => s.id !== id));
  };
  
  const handleStartSimulado = (config) => {
    setShowConfigModal(false);
    setActiveSimulado(config);
  };
  
  const handleFinishSimulado = (result) => {
    const simuladoCompleto = {
      ...result,
      id: Date.now(),
      createdAt: new Date().toISOString()
    };
    
    setSimuladosCompletos([simuladoCompleto, ...simuladosCompletos]);
    setActiveSimulado(null);
    
    // Adiciona também ao gráfico
    setSimulados([...simulados, {
      id: simuladoCompleto.id,
      date: result.date,
      score: result.score
    }].sort((a, b) => new Date(a.date) - new Date(b.date)));
  };

  return (
    <>
      {showConfigModal && (
        <ConfigModal 
          onClose={() => setShowConfigModal(false)}
          onStart={handleStartSimulado}
        />
      )}
      
      {activeSimulado && (
        <SimuladoModal
          config={activeSimulado}
          onClose={() => setActiveSimulado(null)}
          onFinish={handleFinishSimulado}
        />
      )}
      
      <div className="p-8 max-w-5xl mx-auto pb-20">
        <h2 className="font-serif text-3xl font-bold text-slate-800 mb-6 border-l-4 border-crimson-600 pl-4">
          Evolução nos Simulados
        </h2>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
              <h3 className="text-lg font-bold text-slate-700 mb-6">Gráfico de Desempenho (1ª Fase)</h3>
              <div className="h-80 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={simulados}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis 
                      dataKey="date" 
                      stroke="#64748b" 
                      tickFormatter={(str) => new Date(str).toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit'})}
                    />
                    <YAxis stroke="#64748b" domain={[0, 90]} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0' }}
                      labelFormatter={(str) => new Date(str).toLocaleDateString('pt-BR')}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="score" 
                      stroke="#990000" 
                      strokeWidth={3}
                      dot={{ fill: '#990000', strokeWidth: 2, r: 4 }}
                      activeDot={{ r: 8 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            {/* Botão Criar Simulado */}
            <button
              onClick={() => setShowConfigModal(true)}
              className="w-full bg-gradient-to-r from-crimson-600 to-crimson-700 text-white py-6 px-8 rounded-2xl font-black text-xl hover:shadow-2xl hover:-translate-y-1 transition-all duration-300 flex items-center justify-center gap-3"
            >
              <Play size={28} className="animate-pulse" /> Criar Novo Simulado
            </button>
            
            {/* Lista de Simulados Completos */}
            {simuladosCompletos.length > 0 && (
              <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
                <h3 className="text-lg font-bold text-slate-700 mb-4">Simulados Realizados</h3>
                <div className="space-y-3">
                  {simuladosCompletos.map(sim => (
                    <div key={sim.id} className="p-4 bg-slate-50 rounded-xl border border-slate-100 group hover:bg-white transition-colors">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <span className="text-sm font-bold text-slate-700">
                              {new Date(sim.date).toLocaleDateString('pt-BR')}
                            </span>
                            <span className="text-xs bg-slate-200 text-slate-600 px-2 py-1 rounded-md font-medium">
                              {sim.total} questões
                            </span>
                            <span className="text-xs bg-slate-200 text-slate-600 px-2 py-1 rounded-md font-medium">
                              {sim.timeMinutes} min
                            </span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-2xl font-black text-crimson-600">
                              {sim.score}/{sim.total}
                            </span>
                            <span className="text-sm text-slate-500">
                              ({Math.round((sim.score / sim.total) * 100)}% de acerto)
                            </span>
                          </div>
                        </div>
                        <button
                          onClick={() => handleDeleteCompleto(sim.id)}
                          className="text-slate-400 hover:text-red-600 transition-colors opacity-0 group-hover:opacity-100"
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="space-y-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
              <h3 className="text-lg font-bold text-slate-700 mb-4">Novo Resultado Manual</h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-600 mb-1">Data</label>
                  <input 
                    type="date" 
                    value={formData.date}
                    onChange={e => setFormData({...formData, date: e.target.value})}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-crimson-500 focus:border-crimson-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-600 mb-1">Acertos (de 90)</label>
                  <input 
                    type="number" 
                    min="0" 
                    max="90"
                    value={formData.score}
                    onChange={e => setFormData({...formData, score: e.target.value})}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-crimson-500 focus:border-crimson-500 outline-none"
                  />
                </div>
                <button 
                  type="submit"
                  className="w-full bg-slate-700 text-white py-2 px-4 rounded-lg font-medium hover:bg-slate-800 transition-colors flex items-center justify-center"
                >
                  <Plus size={18} className="mr-2" /> Adicionar Manual
                </button>
              </form>
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100 max-h-80 overflow-y-auto">
              <h3 className="text-lg font-bold text-slate-700 mb-4">Histórico</h3>
              <div className="space-y-3">
                {[...simulados].reverse().map(sim => (
                  <div key={sim.id} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg group">
                    <div>
                      <span className="block text-sm font-medium text-slate-800">
                        {new Date(sim.date).toLocaleDateString('pt-BR')}
                      </span>
                      <span className="text-xs text-slate-500">{sim.score} acertos</span>
                    </div>
                    <button 
                      onClick={() => handleDelete(sim.id)}
                      className="text-slate-400 hover:text-red-600 transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
