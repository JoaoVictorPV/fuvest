import React, { useState, useEffect, useMemo } from 'react';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { CheckCircle2, ChevronRight, RotateCcw, HelpCircle, Trophy, X, ChevronLeft, FileText } from 'lucide-react';

function ImageModal({ src, title, onClose }) {
  if (!src) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full h-full max-w-6xl max-h-[90vh] bg-white rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50">
          <p className="text-sm font-bold text-slate-700 truncate pr-4">{title || 'Imagem da questão'}</p>
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white hover:bg-slate-100 border border-slate-200 text-slate-600"
            title="Fechar"
          >
            <X size={18} />
          </button>
        </div>
        <div className="w-full h-[calc(90vh-52px)] bg-white flex items-center justify-center p-4">
          <img
            src={src}
            alt={title || 'Imagem da questão'}
            className="max-w-full max-h-full object-contain"
          />
        </div>
      </div>
    </div>
  );
}

function PageModal({ year, page, onClose }) {
  const [currentPage, setCurrentPage] = useState(page);
  const [imgSrc, setImgSrc] = useState(null);

  useEffect(() => {
    // Garante formato 2 dígitos: "05", "12"
    const pStr = String(currentPage).padStart(2, '0');
    setImgSrc(`/assets/pages/${year}/page_${pStr}.png`);
  }, [year, currentPage]);

  if (!year || !page) return null;

  const handlePrev = () => setCurrentPage(p => Math.max(1, p - 1));
  const handleNext = () => setCurrentPage(p => p + 1); // sem limite hard, se falhar o img mostra erro/vazio

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full h-full max-w-5xl max-h-[95vh] bg-white rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50 shrink-0">
          <div className="flex items-center gap-4">
            <p className="text-sm font-bold text-slate-700">
              Prova {year} - Página {currentPage}
            </p>
            <div className="flex gap-2">
              <button 
                onClick={handlePrev} 
                disabled={currentPage <= 1}
                className="p-1.5 rounded-lg border bg-white hover:bg-slate-50 disabled:opacity-50"
                title="Página Anterior"
              >
                <ChevronLeft size={16} />
              </button>
              <button 
                onClick={handleNext}
                className="p-1.5 rounded-lg border bg-white hover:bg-slate-50"
                title="Próxima Página"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white hover:bg-slate-100 border border-slate-200 text-slate-600"
            title="Fechar"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 bg-slate-100 overflow-auto flex items-center justify-center p-4">
          <img
            src={imgSrc}
            alt={`Página ${currentPage}`}
            className="max-w-full max-h-full object-contain shadow-lg bg-white"
            onError={(e) => {
              e.target.onerror = null; 
              // e.target.src = '/assets/questions/holder.png'; // opcional
            }}
          />
        </div>
      </div>
    </div>
  );
}

export function Questoes() {
  const [selectedYear, setSelectedYear] = useState(2019);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [imageModalSrc, setImageModalSrc] = useState(null);
  const [pageModalOpen, setPageModalOpen] = useState(false);
  const [goToNumber, setGoToNumber] = useState('');

  const questionNumbers = useMemo(() => {
    const nums = (questions || [])
      .map(q => Number(q?.number))
      .filter(n => Number.isFinite(n) && n > 0)
      .sort((a, b) => a - b);
    return Array.from(new Set(nums));
  }, [questions]);

  // Progresso do Usuário (simples, por ano)
  const [stats, setStats] = useLocalStorage('sanfran-questoes-stats', {
    perYear: {
      "2019": { correct: 0, wrong: 0, answered: 0 },
      "2020": { correct: 0, wrong: 0, answered: 0 },
      "2021": { correct: 0, wrong: 0, answered: 0 },
      "2022": { correct: 0, wrong: 0, answered: 0 },
      "2023": { correct: 0, wrong: 0, answered: 0 },
      "2024": { correct: 0, wrong: 0, answered: 0 },
      "2025": { correct: 0, wrong: 0, answered: 0 },
      "2026": { correct: 0, wrong: 0, answered: 0 }
    }
  });

  // Migração leve (caso exista stats antigo com xp/streak/etc)
  useEffect(() => {
    if (stats && stats.perYear) return;

    setStats({
      perYear: {
        "2019": { correct: 0, wrong: 0, answered: 0 },
        "2020": { correct: 0, wrong: 0, answered: 0 },
        "2021": { correct: 0, wrong: 0, answered: 0 },
        "2022": { correct: 0, wrong: 0, answered: 0 },
        "2023": { correct: 0, wrong: 0, answered: 0 },
        "2024": { correct: 0, wrong: 0, answered: 0 },
        "2025": { correct: 0, wrong: 0, answered: 0 },
        "2026": { correct: 0, wrong: 0, answered: 0 }
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Carrega as questões quando o ano muda
  useEffect(() => {
    async function loadQuestions() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/data/questions/fuvest-${selectedYear}.json`);
        if (!response.ok) throw new Error('Falha ao carregar as questões.');
        const data = await response.json();

        // Importante: em produção o JSON pode estar parcialmente enriquecido.
        // Se não houver explicação, ainda assim a questão deve aparecer (o aluno lê pela imagem).
        const all = Array.isArray(data.questions) ? data.questions : [];

        // Ordena as questões por número para navegação sequencial
        const sorted = [...all].sort((a, b) => a.number - b.number);
        
        setQuestions(sorted);
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

  const goToQuestionByNumber = (n) => {
    const target = Number(n);
    if (!Number.isFinite(target) || target <= 0) return;

    // procura pelo número da questão dentro da lista atual (já embaralhada)
    const idx = questions.findIndex(q => Number(q?.number) === target);
    if (idx < 0) {
      // se não encontrar, não faz nada (mantém discreto)
      return;
    }
    setCurrentIndex(idx);
    resetState();
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

    const y = String(selectedYear);
    const current = (stats?.perYear && stats.perYear[y]) || { correct: 0, wrong: 0, answered: 0 };
    const next = {
      ...stats,
      perYear: {
        ...(stats?.perYear || {}),
        [y]: {
          answered: (current.answered || 0) + 1,
          correct: (current.correct || 0) + (isCorrect ? 1 : 0),
          wrong: (current.wrong || 0) + (isCorrect ? 0 : 1),
        }
      }
    };

    setStats(next);
  };

  const handleSkipToAnswer = () => {
    if (isSubmitted) return;

    setIsSubmitted(true);

    // Conta como erro (pulo)
    const y = String(selectedYear);
    const current = (stats?.perYear && stats.perYear[y]) || { correct: 0, wrong: 0, answered: 0 };
    setStats({
      ...stats,
      perYear: {
        ...(stats?.perYear || {}),
        [y]: {
          answered: (current.answered || 0) + 1,
          correct: (current.correct || 0),
          wrong: (current.wrong || 0) + 1,
        }
      }
    });
  };

  const nextQuestion = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
      resetState();
    }
  };

  const prevQuestion = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      resetState();
    }
  };

  const jumpToRandomQuestion = () => {
    if (questions.length === 0) return;
    const randomIdx = Math.floor(Math.random() * questions.length);
    setCurrentIndex(randomIdx);
    resetState();
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
  const explanation = currentQ?.explanation || {};
  const steps = Array.isArray(explanation.steps) ? explanation.steps : [];
  const distractors = explanation.distractors || {};
  const isCorrect = selectedOption === currentQ.answer.correct;

  const yearStats = (stats?.perYear && stats.perYear[String(selectedYear)]) || { correct: 0, wrong: 0, answered: 0 };

  return (
    <div className="p-8 max-w-5xl mx-auto pb-20 animate-in fade-in duration-500">
      <ImageModal
        src={imageModalSrc}
        title={imageModalSrc ? `Fuvest ${selectedYear} - Questão ${currentQ.number}` : ''}
        onClose={() => setImageModalSrc(null)}
      />

      {pageModalOpen && (
        <PageModal 
          year={selectedYear} 
          page={currentQ.page || 1} 
          onClose={() => setPageModalOpen(false)} 
        />
      )}
      
      {/* Header com Stats (simples por ano) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Acertos</p>
          <p className="text-2xl font-black text-emerald-700 tabular-nums">{yearStats.correct}</p>
          <p className="text-xs text-slate-400 mt-1">Fuvest {selectedYear}</p>
        </div>

        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Erros</p>
          <p className="text-2xl font-black text-red-700 tabular-nums">{yearStats.wrong}</p>
          <p className="text-xs text-slate-400 mt-1">Inclui “Ir para Resposta”</p>
        </div>

        <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Respondidas</p>
          <p className="text-2xl font-black text-slate-800 tabular-nums">{yearStats.answered}</p>
          <p className="text-xs text-slate-400 mt-1">Neste ano</p>
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
            <option value={2022}>Fuvest 2022</option>
            <option value={2023}>Fuvest 2023</option>
            <option value={2024}>Fuvest 2024</option>
            <option value={2025}>Fuvest 2025</option>
            <option value={2026}>Fuvest 2026</option>
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
                  
                  {/* Botão Ver Página Inteira */}
                  <button 
                    onClick={() => setPageModalOpen(true)}
                    className="p-1 text-slate-400 hover:text-crimson-600 hover:bg-crimson-50 rounded-md transition-colors"
                    title="Ver página original da prova"
                  >
                    <FileText size={16} />
                  </button>
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
                    className="max-h-[500px] object-contain rounded-lg shadow-sm group-hover:scale-[1.01] transition-transform duration-500 cursor-zoom-in"
                    onClick={() => setImageModalSrc(currentQ.assets.questionImage)}
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
              <div className="mt-12 flex flex-col md:flex-row md:items-center gap-3 justify-end">
                {!isSubmitted ? (
                  <>
                    {/* Navegação direta por número (discreta) */}
                    <div className="w-full md:w-auto md:mr-auto">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={prevQuestion}
                          disabled={currentIndex === 0}
                          className="p-3 rounded-2xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed"
                          title="Questão anterior"
                        >
                          <ChevronLeft size={18} />
                        </button>

                        <select
                          value={goToNumber}
                          onChange={(e) => {
                            setGoToNumber(e.target.value);
                            // muda imediatamente ao selecionar
                            goToQuestionByNumber(e.target.value);
                          }}
                          className="w-28 px-3 py-3 rounded-2xl border border-slate-200 bg-white text-sm font-black text-slate-700 focus:outline-none focus:ring-2 focus:ring-crimson-500"
                          title="Ir para uma questão específica"
                        >
                          <option value="">Ir p/...</option>
                          {questionNumbers.map((n) => (
                            <option key={n} value={String(n)}>
                              {n}
                            </option>
                          ))}
                        </select>

                        <button
                          onClick={nextQuestion}
                          disabled={currentIndex >= questions.length - 1}
                          className="p-3 rounded-2xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed"
                          title="Próxima questão"
                        >
                          <ChevronRight size={18} />
                        </button>
                      </div>
                    </div>

                    <button
                      onClick={handleSkipToAnswer}
                      className="w-full md:w-auto bg-slate-100 text-slate-900 px-8 py-4 rounded-2xl font-black text-lg hover:bg-slate-200 transition-all duration-300 border border-slate-200"
                      title="Pula a questão e mostra a resposta/explicação"
                    >
                      Ir para Resposta
                    </button>

                    <button
                      onClick={handleSubmit}
                      disabled={!selectedOption}
                      className="w-full md:w-auto bg-slate-900 text-white px-12 py-4 rounded-2xl font-black text-lg hover:bg-black disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-300 shadow-xl hover:shadow-2xl hover:-translate-y-1 active:translate-y-0"
                    >
                      Confirmar Resposta
                    </button>
                  </>
                ) : (
                  <button
                    onClick={jumpToRandomQuestion}
                    className="w-full md:w-auto bg-crimson-600 text-white px-12 py-4 rounded-2xl font-black text-lg hover:bg-crimson-700 transition-all duration-300 shadow-xl shadow-crimson-900/20 flex items-center justify-center hover:-translate-y-1"
                  >
                    Próxima Aleatória <ChevronRight size={24} className="ml-2" />
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
                    {explanation.theory || "(Explicação ainda não gerada para esta questão.)"}
                  </p>
                </div>

                <div>
                  <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">Passo a Passo</h4>
                  <div className="space-y-3">
                    {steps.length === 0 ? (
                      <p className="text-sm text-slate-500">(Passo a passo ainda não disponível.)</p>
                    ) : steps.map((step, idx) => (
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
                        <span className="mr-1">{key})</span> {distractors[key] || '(Ainda não disponível)'}
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
