import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';

const AuthContext = createContext({});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const signInAndSetSession = async () => {
      try {
        // Attempt to get the current session
        const { data: { session: currentSession } } = await supabase.auth.getSession();

        if (currentSession) {
          setSession(currentSession);
        } else {
          // If no session, sign in with the hardcoded credentials
          const { data, error } = await supabase.auth.signInWithPassword({
            email: 'joaovictorpv@hotmail.com',
            password: '123456',
          });

          if (error) {
            console.error('!!!! SUPABASE AUTO-LOGIN FAILED !!!!', error);
          } else {
            console.log('%%%%%% SUPABASE AUTO-LOGIN SUCCESS %%%%%%', data);
          }
          setSession(data?.session ?? null);
        }
      } catch (e) {
        console.error('Error during auth process:', e);
      } finally {
        setLoading(false);
      }
    };

    signInAndSetSession();

    // The onAuthStateChange is still useful if the session is refreshed or user signs out (though sign out is removed from UI)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const value = {
    session,
    user: session?.user,
    signOut: () => supabase.auth.signOut(), // Keeping this for potential future use or debugging
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
}
