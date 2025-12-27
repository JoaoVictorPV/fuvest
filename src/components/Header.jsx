import React, { useState, useEffect } from 'react';
import { Clock, Calendar, Menu } from 'lucide-react';
import { differenceInDays, differenceInHours, differenceInMinutes } from 'date-fns';

export function Header({ onOpenMenu }) {
  const [timeLeft, setTimeLeft] = useState({ days: 0, hours: 0, minutes: 0 });
  const targetDate = new Date('2026-11-15T13:00:00'); // Estimated date

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      if (now > targetDate) {
        clearInterval(timer);
        return;
      }
      
      const days = differenceInDays(targetDate, now);
      const hours = differenceInHours(targetDate, now) % 24;
      const minutes = differenceInMinutes(targetDate, now) % 60;

      setTimeLeft({ days, hours, minutes });
    }, 1000 * 60); // Update every minute is enough

    // Initial call
    const now = new Date();
    const days = differenceInDays(targetDate, now);
    const hours = differenceInHours(targetDate, now) % 24;
    const minutes = differenceInMinutes(targetDate, now) % 60;
    setTimeLeft({ days, hours, minutes });

    return () => clearInterval(timer);
  }, []);

  return (
    <header className="fixed top-0 left-0 md:left-64 right-0 h-16 glass shadow-soft flex items-center justify-between px-4 md:px-8 z-10">
      <div className="flex items-center space-x-3 text-slate-600">
        <button
          type="button"
          onClick={onOpenMenu}
          className="md:hidden p-2 rounded-xl hover:bg-white/70 border border-white/40"
          aria-label="Abrir menu"
        >
          <Menu size={18} />
        </button>
        <div className="hidden sm:flex items-center space-x-2">
          <Calendar size={18} />
          <span className="text-sm font-medium">{new Date().toLocaleDateString('pt-BR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</span>
        </div>
      </div>

      <div className="flex items-center bg-white/70 px-4 py-2 rounded-full border border-white/40">
        <Clock size={18} className="text-crimson-600 mr-2" />
        <div className="flex space-x-2 text-sm font-bold text-crimson-800">
          <span>{timeLeft.days} dias</span>
          <span className="text-crimson-300">|</span>
          <span>{timeLeft.hours}h</span>
          <span className="text-crimson-300">|</span>
          <span>{timeLeft.minutes}min</span>
          <span className="font-normal text-crimson-600 ml-1">para a Fuvest 2026</span>
        </div>
      </div>
    </header>
  );
}
