import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';
import { useAuth } from '../contexts/AuthContext';

export function useSyllabus() {
  const { user } = useAuth();
  const [checkedItems, setCheckedItems] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;

    const fetchSyllabus = async () => {
      const { data, error } = await supabase
        .from('syllabus_progress')
        .select('item_id');
      
      if (error) console.error('Error fetching syllabus:', error);
      else {
        const items = {};
        data.forEach(row => items[row.item_id] = true);
        setCheckedItems(items);
      }
      setLoading(false);
    };

    fetchSyllabus();
  }, [user]);

  const toggleItem = async (itemId) => {
    const isChecked = !!checkedItems[itemId];
    const newChecked = { ...checkedItems, [itemId]: !isChecked };
    setCheckedItems(newChecked); // Optimistic update

    if (isChecked) {
      // Remove
      const { error } = await supabase
        .from('syllabus_progress')
        .delete()
        .eq('user_id', user.id)
        .eq('item_id', itemId);
      if (error) console.error('Error removing item:', error);
    } else {
      // Add
      const { error } = await supabase
        .from('syllabus_progress')
        .insert({ user_id: user.id, item_id: itemId });
      if (error) console.error('Error adding item:', error);
    }
  };

  return { checkedItems, toggleItem, loading };
}

export function useBooks() {
  const { user } = useAuth();
  const [bookStatus, setBookStatus] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;

    const fetchBooks = async () => {
      const { data, error } = await supabase
        .from('books_progress')
        .select('book_id, status');
      
      if (error) console.error('Error fetching books:', error);
      else {
        const status = {};
        data.forEach(row => status[row.book_id] = row.status);
        setBookStatus(status);
      }
      setLoading(false);
    };

    fetchBooks();
  }, [user]);

  const updateStatus = async (bookId, newStatus) => {
    setBookStatus(prev => ({ ...prev, [bookId]: newStatus }));

    const { error } = await supabase
      .from('books_progress')
      .upsert({ user_id: user.id, book_id: bookId, status: newStatus }, { onConflict: 'user_id, book_id' });
    
    if (error) console.error('Error updating book:', error);
  };

  return { bookStatus, updateStatus, loading };
}

export function useSimulados() {
  const { user } = useAuth();
  const [simulados, setSimulados] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;

    const fetchSimulados = async () => {
      const { data, error } = await supabase
        .from('simulados')
        .select('*')
        .order('date', { ascending: true });
      
      if (error) console.error('Error fetching simulados:', error);
      else setSimulados(data);
      setLoading(false);
    };

    fetchSimulados();
  }, [user]);

  const addSimulado = async (simulado) => {
    const { data, error } = await supabase
      .from('simulados')
      .insert({ user_id: user.id, ...simulado })
      .select();
    
    if (error) console.error('Error adding simulado:', error);
    else setSimulados([...simulados, data[0]].sort((a, b) => new Date(a.date) - new Date(b.date)));
  };

  const deleteSimulado = async (id) => {
    setSimulados(simulados.filter(s => s.id !== id));
    const { error } = await supabase
      .from('simulados')
      .delete()
      .eq('id', id);
    if (error) console.error('Error deleting simulado:', error);
  };

  return { simulados, addSimulado, deleteSimulado, loading };
}

export function useNotes() {
  const { user } = useAuth();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;

    const fetchNotes = async () => {
      const { data, error } = await supabase
        .from('notes')
        .select('*')
        .order('created_at', { ascending: false });
      
      if (error) console.error('Error fetching notes:', error);
      else setNotes(data);
      setLoading(false);
    };

    fetchNotes();
  }, [user]);

  const addNote = async (text) => {
    const { data, error } = await supabase
      .from('notes')
      .insert({ user_id: user.id, content: text })
      .select();
    
    if (error) console.error('Error adding note:', error);
    else setNotes([data[0], ...notes]);
  };

  const deleteNote = async (id) => {
    setNotes(notes.filter(n => n.id !== id));
    const { error } = await supabase
      .from('notes')
      .delete()
      .eq('id', id);
    if (error) console.error('Error deleting note:', error);
  };

  return { notes, addNote, deleteNote, loading };
}
