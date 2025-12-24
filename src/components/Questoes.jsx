import React, { useState, useEffect } from 'react';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { CheckCircle2, XCircle, ChevronRight, RotateCcw, HelpCircle, Trophy, Flame, BarChart3 } from 'lucide-react';

export function Questoes() {
  const [selectedYear, setSelectedYear] = useState(2019);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Progresso do Usuário (Stats e SRS)
  const [stats, setStats] = useLocalStorage('sanfran-questoes-stats', {
    xp: 0,
    streak: 0,
    lastDate: null,
    totalAnswered: 0,
    correctCount: 0,
    wrongQuestions: [] // Lógica de SRS simples: guarda IDs das que errou
  });

  // Carrega as questões quando o ano muda
  useEffect(() => {
    async function loadQuestions() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/data/questions/fuvest-${selectedYear}.json`);
        if (!response.ok) throw new Error('Falha ao carregar as questões.');
        const data = await response.json();
        
        // Filtra e prioriza as questões que o usuário ainda não acertou ou que errou recentemente
        const enrichedOnly = data.questions.filter(q => q.explanation && q.explanation.theory !== "Pendente");
        
        // Sorteia as questões para não ser sempre na mesma ordem
        const shuffled = [...enrichedOnly].sort(() => Math.random() - 0.5);
        
        setQuestions(shuffled);
        setCurrentIndex(0);
        resetState();
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadQuestions();
  }, [selectedYear]);

  const resetState = () => {
    setSelectedOption(null);
    setIsSubmitted(false);
  };

  const handleOptionSelect = (key) => {
    if (isSubmitted) return;
    setSelectedOption(key);
  };

  const handleSubmit = () => {
    if (!selectedOption || isSubmitted) return;
    
    setIsSubmitted(true);
    const currentQ = questions[currentIndex];
    const isCorrect = selectedOption === currentQ.answer.correct;

    // Atualiza Stats (Gamificação e SRS)
    const today = new Date().toISOString().split('T')[0];
    let newStreak = stats.streak;
    
    if (stats.lastDate !== today) {
        if (stats.lastDate === new Date(Date.now() - 86400000).toISOString().split('T')[0]) {
            newStreak += 1;
        } else {
            newStreak = 1;
        }
    }

    const updatedWrongQuestions = isCorrect 
        ? stats.wrongQuestions.filter(id => id !== currentQ.id) 
        : [...new Set([...stats.wrongQuestions, currentQ.id])];

    setStats({
      ...stats,
      xp: stats.xp + (isCorrect ? 10 : 2),
      streak: newStreak,
      lastDate: today,
      totalAnswered: stats.totalAnswered + 1,
      correctCount: stats.correctCount + (isCorrect ? 1 : 0),
      wrongQuestions: updatedWrongQuestions
    });
  };

  const nextQuestion = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
      resetState();
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Carregando banco de questões...</div>;
  
  if (error) return (
    <div className="p-8 text-center">
      <p className="text-red-500 mb-4">{error}</p>
      <button onClick={() => setSelectedYear(2019)} className="text-crimson-600 font-bold underline">Voltar para 2019</button>
    </div>
  );

  if (questions.length === 0) return <div className="p-8 text-center text-slate-500">Nenhuma questão encontrada para este ano.</div>;

  const currentQ = questions[currentIndex];
  const isCorrect = selectedOption === currentQ.answer.correct;
  const accuracy = stats.totalAnswered > 0 ? Math.round((stats.correctCount / stats.totalAnswered) * 100) : 0;

  return (
    <div className="p-8 max-w-5xl mx-auto pb-20 animate-in fade-in duration-500">
      
      {/* Header com Stats Avançados */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 flex items-center space-x-4">
          <div className="bg-amber-100 p-3 rounded-xl text-amber-600"><Trophy size={24} /></div>
          <div>
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Pontuação</p>
            <p className="text-xl font-black text-slate-800">{stats.xp} XP</p>
          </div>
        </div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 flex items-center space-x-4">
          <div className="bg-orange-100 p-3 rounded-xl text-orange-600"><Flame size={24} /></div>
          <div>
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Sequência</p>
            <p className="text-xl font-black text-slate-800">{stats.streak} dias</p>
          </div>
        </div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 flex items-center space-x-4">
          <div className="bg-emerald-100 p-3 rounded-xl text-emerald-600"><BarChart3 size={24} /></div>
          <div>
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Precisão</p>
            <p className="text-xl font-black text-slate-800">{accuracy}%</p>
          </div>
        </div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Ano da Prova</p>
          <select 
            value={selectedYear}
            onChange={(e) => setSelectedYear(Number(e.target.value))}
            className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1 text-sm font-bold focus:ring-2 focus:ring-crimson-500 outline-none cursor-pointer"
          >
            <option value={2019}>Fuvest 2019</option>
            <option value={2020}>Fuvest 2020</option>
            <option value={2021}>Fuvest 2021</option>
          </select>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Lado Esquerdo: Questão */}
        <div className="flex-1">
          <div className="bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden ring-1 ring-slate-200/50">
            {/* Barra de Progresso */}
            <div className="h-2 w-full bg-slate-100">
              <div 
                className="h-full bg-gradient-to-r from-crimson-600 to-crimson-400 transition-all duration-700 ease-out" 
                style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
              ></div>
            </div>

            <div className="p-8">
              <div className="flex justify-between items-center mb-8">
                <div className="flex items-center space-x-3">
                  <span className="bg-crimson-600 text-white text-[10px] font-black px-2.5 py-1 rounded-md uppercase tracking-tighter">
                    Fuvest {selectedYear}
                  </span>
                  <span className="bg-slate-100 text-slate-600 text-[10px] font-bold px-2.5 py-1 rounded-md uppercase">
                    Questão {currentQ.number}
                  </span>
                </div>
                <span className="text-slate-400 text-xs font-bold tabular-nums">{currentIndex + 1} / {questions.length}</span>
              </div>

              {/* Enunciado */}
              <div className="mb-10">
                <p className="text-xl text-slate-800 leading-relaxed font-medium">
                  {currentQ.stem}
                </p>
              </div>

              {/* Imagem da Questão */}
              {currentQ.assets && currentQ.assets.questionImage && (
                <div className="mb-10 p-6 bg-slate-50 rounded-3xl border-2 border-dashed border-slate-200 flex justify-center group hover:bg-white transition-colors duration-300">
                  <img 
                    src={currentQ.assets.questionImage} 
                    alt={`Questão ${currentQ.number}`}
                    className="max-h-[500px] object-contain rounded-lg shadow-sm group-hover:scale-[1.01] transition-transform duration-500"
                  />
                </div>
              )}

              {/* Alternativas */}
              <div className="grid grid-cols-1 gap-4">
                {currentQ.options.map((opt) => {
                  let style = "border-slate-100 bg-slate-50/50 hover:border-slate-300 hover:bg-white hover:shadow-md";
                  if (selectedOption === opt.key) {
                    style = "border-crimson-600 bg-crimson-50 shadow-md ring-1 ring-crimson-600";
                  }
                  if (isSubmitted) {
                    if (opt.key === currentQ.answer.correct) {
                      style = "border-emerald-500 bg-emerald-50 ring-2 ring-emerald-500 text-emerald-900 shadow-lg shadow-emerald-900/10";
                    } else if (selectedOption === opt.key) {
                      style = "border-red-500 bg-red-50 ring-2 ring-red-500 text-red-900 opacity-90";
                    } else {
                      style = "border-slate-50 opacity-40 grayscale-[0.5]";
                    }
                  }

                  return (
                    <button
                      key={opt.key}
                      onClick={() => handleOptionSelect(opt.key)}
                      disabled={isSubmitted}
                      className={`w-full text-left p-5 rounded-2xl border-2 transition-all duration-300 flex items-center group relative ${style}`}
                    >
                      <span className={`w-10 h-10 rounded-xl flex items-center justify-center mr-5 text-base font-black border-2 transition-all duration-300 ${
                        selectedOption === opt.key ? 'bg-crimson-600 border-crimson-600 text-white rotate-3' : 'border-slate-200 text-slate-400 group-hover:border-slate-400 group-hover:text-slate-600'
                      }`}>
                        {opt.key}
                      </span>
                      <span className="flex-1 font-semibold text-slate-700 leading-snug">{opt.text || "(Analise a imagem acima)"}</span>
                      
                      {isSubmitted && opt.key === currentQ.answer.correct && (
                        <CheckCircle2 size={24} className="text-emerald-500 absolute right-5 animate-in zoom-in duration-500" />
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Botão de Ação */}
              <div className="mt-12 flex justify-end">
                {!isSubmitted ? (
                  <button
                    onClick={handleSubmit}
                    disabled={!selectedOption}
                    className="w-full md:w-auto bg-slate-900 text-white px-12 py-4 rounded-2xl font-black text-lg hover:bg-black disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-300 shadow-xl hover:shadow-2xl hover:-translate-y-1 active:translate-y-0"
                  >
                    Confirmar Resposta
                  </button>
                ) : (
                  <button
                    onClick={nextQuestion}
                    className="w-full md:w-auto bg-crimson-600 text-white px-12 py-4 rounded-2xl font-black text-lg hover:bg-crimson-700 transition-all duration-300 shadow-xl shadow-crimson-900/20 flex items-center justify-center hover:-translate-y-1"
                  >
                    {currentIndex === questions.length - 1 ? 'Concluir Prova' : 'Próxima Questão'} <ChevronRight size={24} className="ml-2" />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Lado Direito: Explicação (Apenas após submit) */}
        {isSubmitted && (
          <div className="lg:w-96 shrink-0 space-y-6 animate-in slide-in-from-right duration-700">
            <div className="bg-white rounded-3xl p-6 shadow-xl border border-slate-100">
              <h3 className="font-serif text-xl font-bold text-slate-800 mb-6 flex items-center border-l-4 border-amber-500 pl-4">
                Explicação
              </h3>
              
              <div className="space-y-6">
                <div>
                  <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 flex items-center">
                    <HelpCircle size={14} className="mr-2" /> Conceito Chave
                  </h4>
                  <p className="text-sm text-slate-600 leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-100 italic">
                    {currentQ.explanation.theory}
                  </p>
                </div>

                <div>
                  <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">Passo a Passo</h4>
                  <div className="space-y-3">
                    {currentQ.explanation.steps.map((step, idx) => (
                      <div key={idx} className="flex items-start text-sm">
                        <span className="bg-slate-900 text-white w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-black mr-3 shrink-0 mt-0.5">{idx + 1}</span>
                        <span className="text-slate-600 leading-tight">{step}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">Distratores</h4>
                  <div className="space-y-2">
                    {['A', 'B', 'C', 'D', 'E'].map(key => (
                      <div key={key} className={`p-3 rounded-xl border text-xs leading-snug ${key === currentQ.answer.correct ? 'bg-emerald-50 border-emerald-100 text-emerald-800 font-bold' : 'bg-white border-slate-100 text-slate-500'}`}>
                        <span className="mr-1">{key})</span> {currentQ.explanation.distractors[key]}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Card de Feedback Rápido */}
            <div className={`p-6 rounded-3xl shadow-xl border flex flex-col items-center text-center ${isCorrect ? 'bg-emerald-600 border-emerald-500 text-white' : 'bg-slate-900 border-slate-800 text-white'}`}>
                {isCorrect ? (
                    <>
                        <Trophy size={48} className="mb-4 text-emerald-200" />
                        <p className="text-lg font-black uppercase tracking-tight">Excelente!</p>
                        <p className="text-sm text-emerald-100">Sua lógica foi perfeita nesta questão.</p>
                    </>
                ) : (
                    <>
                        <RotateCcw size={48} className="mb-4 text-slate-400" />
                        <p className="text-lg font-black uppercase tracking-tight">Aprendizado!</p>
                        <p className="text-sm text-slate-400">Erros são degraus para o sucesso. Analise a explicação.</p>
                    </>
                )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
