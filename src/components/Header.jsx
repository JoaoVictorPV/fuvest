import React, { useState, useEffect } from 'react';
import { Clock, Calendar } from 'lucide-react';
import { differenceInDays, differenceInHours, differenceInMinutes } from 'date-fns';

export function Header() {
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
    <header className="fixed top-0 left-64 right-0 h-16 bg-white shadow-sm flex items-center justify-between px-8 z-10">
      <div className="flex items-center space-x-2 text-slate-500">
        <Calendar size={18} />
        <span className="text-sm font-medium">{new Date().toLocaleDateString('pt-BR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</span>
      </div>

      <div className="flex items-center bg-crimson-50 px-4 py-2 rounded-full border border-crimson-100">
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
