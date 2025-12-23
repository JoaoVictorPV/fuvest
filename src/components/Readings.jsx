import React, { useState } from 'react';
import { booksData } from '../data/books';
import { useBooks } from '../hooks/useSupabaseData';
import { Book, Check, X, BookOpen, FileText } from 'lucide-react';
import clsx from 'clsx';

function BookModal({ book, onClose, status, onStatusChange }) {
  const [activeTab, setActiveTab] = useState('summary');

  if (!book) return null;

  const tabs = [
    { id: 'summary', label: 'Resumo' },
    { id: 'context', label: 'Contexto Histórico' },
    { id: 'analysis', label: 'Análise Crítica' }
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden max-h-[90vh] flex flex-col">
        <div className={`p-6 ${book.color} flex justify-between items-start`}>
          <div>
            <h3 className="font-serif text-2xl font-bold text-slate-800">{book.title}</h3>
            <p className="text-slate-700 font-medium">{book.author}</p>
            <span className="text-sm text-slate-600 bg-white/50 px-2 py-0.5 rounded mt-2 inline-block">
              {book.year}
            </span>
          </div>
          <button onClick={onClose} className="p-2 bg-white/50 hover:bg-white rounded-full transition-colors text-slate-700">
            <X size={20} />
          </button>
        </div>

        <div className="p-6 border-b border-slate-100 bg-slate-50 flex items-center space-x-4 overflow-x-auto">
          <select 
            value={status} 
            onChange={(e) => onStatusChange(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-crimson-500"
          >
            <option value="unread">Não Lido</option>
            <option value="reading">Lendo</option>
            <option value="read">Lido</option>
            <option value="summarized">Resumido</option>
          </select>
          <div className="flex space-x-1">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id 
                    ? 'bg-crimson-600 text-white shadow-sm' 
                    : 'text-slate-600 hover:bg-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-8 overflow-y-auto flex-1 text-slate-700 leading-relaxed">
          {activeTab === 'summary' && <p>{book.summary}</p>}
          {activeTab === 'context' && <p>{book.context}</p>}
          {activeTab === 'analysis' && <p>{book.analysis}</p>}
        </div>
      </div>
    </div>
  );
}

export function Readings() {
  const { bookStatus, updateStatus, loading } = useBooks();
  const [selectedBook, setSelectedBook] = useState(null);

  const getStatus = (id) => bookStatus[id] || 'unread';

  const handleStatusChange = (id, newStatus) => {
    updateStatus(id, newStatus);
  };

  const readCount = booksData.filter(b => {
    const s = getStatus(b.id);
    return s === 'read' || s === 'summarized';
  }).length;

  const progress = Math.round((readCount / booksData.length) * 100);

  return (
    <div className="p-8 max-w-6xl mx-auto pb-20">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <h2 className="font-serif text-3xl font-bold text-slate-800 mb-2 border-l-4 border-crimson-600 pl-4">
            Leituras Obrigatórias 2026
          </h2>
          <p className="text-slate-600">Fuvest - Lista Oficial</p>
        </div>
        
        <div className="bg-white px-6 py-3 rounded-xl shadow-sm border border-slate-100 flex items-center gap-4">
          <div className="text-right">
            <p className="text-sm text-slate-500 font-medium">Progresso de Leitura</p>
            <p className="text-lg font-bold text-crimson-700">{readCount} de {booksData.length} obras</p>
          </div>
          <div className="w-12 h-12 rounded-full border-4 border-slate-100 flex items-center justify-center relative">
             <span className="text-xs font-bold text-slate-700">{progress}%</span>
             <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 36 36">
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#f1f5f9" strokeWidth="4" />
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#990000" strokeWidth="4" strokeDasharray={`${progress}, 100`} />
             </svg>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {booksData.map(book => {
          const status = getStatus(book.id);
          return (
            <div 
              key={book.id}
              onClick={() => setSelectedBook(book)}
              className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden hover:shadow-md transition-all cursor-pointer group"
            >
              <div className={`h-32 ${book.color} p-6 relative`}>
                <div className="absolute top-4 right-4 bg-white/90 backdrop-blur px-2 py-1 rounded text-xs font-bold uppercase tracking-wider text-slate-600 shadow-sm">
                  {status === 'unread' && 'Não Lido'}
                  {status === 'reading' && 'Lendo'}
                  {status === 'read' && 'Lido'}
                  {status === 'summarized' && 'Resumido'}
                </div>
              </div>
              <div className="p-6">
                <h3 className="font-serif text-lg font-bold text-slate-800 mb-1 group-hover:text-crimson-700 transition-colors">
                  {book.title}
                </h3>
                <p className="text-sm text-slate-500 font-medium mb-4">{book.author}</p>
                
                <div className="flex items-center text-xs text-slate-400 space-x-4">
                  <span className="flex items-center">
                    <BookOpen size={14} className="mr-1" /> Detalhes
                  </span>
                  {status === 'summarized' && (
                    <span className="flex items-center text-green-600">
                      <Check size={14} className="mr-1" /> Completo
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {selectedBook && (
        <BookModal 
          book={selectedBook} 
          onClose={() => setSelectedBook(null)} 
          status={getStatus(selectedBook.id)}
          onStatusChange={(newStatus) => handleStatusChange(selectedBook.id, newStatus)}
        />
      )}
    </div>
  );
}
