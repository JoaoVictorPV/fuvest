import React, { useState } from 'react';
import { supabase } from '../lib/supabaseClient';
import { Mail, Loader2, Send } from 'lucide-react';

export function Auth() {
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('info'); // 'info', 'success', 'error'

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: window.location.origin, // Redirect back to the app after login
        },
      });

      if (error) throw error;
      
      setMessageType('success');
      setMessage('Link de acesso enviado! Verifique seu email.');
      
    } catch (error) {
      setMessageType('error');
      setMessage(error.error_description || error.message);
    } finally {
      setLoading(false);
    }
  };

  const messageStyles = {
    success: 'bg-green-50 text-green-700',
    error: 'bg-red-50 text-red-700',
    info: 'bg-blue-50 text-blue-700',
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-100">
      <div className="w-full max-w-md p-8 bg-white rounded-xl shadow-lg">
        <h1 className="text-3xl font-serif font-bold text-crimson-700 mb-2 text-center">Projeto Sanfran 2027</h1>
        <p className="text-slate-500 text-center mb-8">Acesse com seu email para sincronizar o progresso.</p>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 text-slate-400" size={20} />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-crimson-500 outline-none"
                placeholder="seu@email.com"
              />
            </div>
          </div>

          {message && (
            <div className={`p-3 rounded-lg text-sm ${messageStyles[messageType]}`}>
              {message}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-crimson-600 text-white py-2.5 rounded-lg font-bold hover:bg-crimson-700 transition-colors flex justify-center items-center"
          >
            {loading ? <Loader2 className="animate-spin" /> : <> <Send size={16} className="mr-2"/> Enviar Link Mágico</>}
          </button>
        </form>
        
        <div className="mt-6 text-center">
            <p className="text-xs text-slate-400">
                Você receberá um link no seu email. Basta clicar nele para acessar o painel. Não é necessário senha.
            </p>
        </div>
      </div>
    </div>
  );
}
