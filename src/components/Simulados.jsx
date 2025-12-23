import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useSimulados } from '../hooks/useSupabaseData';
import { Plus, Trash2 } from 'lucide-react';

export function Simulados() {
  const { simulados, addSimulado, deleteSimulado } = useSimulados();
  const [formData, setFormData] = useState({ date: '', score: '' });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.date || !formData.score) return;

    addSimulado({
      date: formData.date,
      score: Number(formData.score)
    });

    setFormData({ date: '', score: '' });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto pb-20">
      <h2 className="font-serif text-3xl font-bold text-slate-800 mb-6 border-l-4 border-crimson-600 pl-4">
        Evolução nos Simulados
      </h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-slate-100">
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

        <div className="space-y-6">
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-100">
            <h3 className="text-lg font-bold text-slate-700 mb-4">Novo Resultado</h3>
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
                className="w-full bg-crimson-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-crimson-700 transition-colors flex items-center justify-center"
              >
                <Plus size={18} className="mr-2" /> Adicionar
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
                    onClick={() => deleteSimulado(sim.id)}
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
  );
}
