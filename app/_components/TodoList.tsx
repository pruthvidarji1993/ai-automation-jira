'use client';

import { useState } from 'react';

interface Todo {
  id: string;
  text: string;
}

export default function TodoList() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [input, setInput] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');

  function handleAdd() {
    if (input.trim() === '') return;
    setTodos([...todos, { id: crypto.randomUUID(), text: input.trim() }]);
    setInput('');
  }

  function handleDelete(id: string) {
    setTodos(todos.filter((t) => t.id !== id));
  }

  function handleEditStart(todo: Todo) {
    setEditingId(todo.id);
    setEditText(todo.text);
  }

  function handleEditSave(id: string) {
    if (editText.trim() === '') return;
    setTodos(todos.map((t) => (t.id === id ? { ...t, text: editText.trim() } : t)));
    setEditingId(null);
    setEditText('');
  }

  function handleEditCancel() {
    setEditingId(null);
    setEditText('');
  }

  return (
    <div>
      <h2 className="text-xl font-semibold tracking-tight text-black dark:text-zinc-50">
        Todo List
      </h2>

      <div className="mt-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="Add a new todo…"
          className="flex-1 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-black placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-300 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50 dark:placeholder:text-zinc-500 dark:focus:ring-zinc-600"
        />
        <button
          type="button"
          onClick={handleAdd}
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 dark:bg-zinc-50 dark:text-black dark:hover:bg-zinc-200"
        >
          Add
        </button>
      </div>

      {todos.length > 0 && (
        <ul className="mt-4 space-y-2">
          {todos.map((todo) => (
            <li
              key={todo.id}
              className="flex items-center gap-2 rounded-md border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            >
              {editingId === todo.id ? (
                <>
                  <input
                    type="text"
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleEditSave(todo.id);
                      if (e.key === 'Escape') handleEditCancel();
                    }}
                    className="flex-1 rounded border border-zinc-200 bg-zinc-50 px-2 py-1 text-sm text-black focus:outline-none focus:ring-2 focus:ring-zinc-300 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-50 dark:focus:ring-zinc-600"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => handleEditSave(todo.id)}
                    className="text-sm font-medium text-black hover:underline dark:text-zinc-50"
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    onClick={handleEditCancel}
                    className="text-sm text-zinc-500 hover:underline dark:text-zinc-400"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm text-black dark:text-zinc-50">{todo.text}</span>
                  <button
                    type="button"
                    onClick={() => handleEditStart(todo)}
                    className="text-sm font-medium text-black hover:underline dark:text-zinc-50"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(todo.id)}
                    className="text-sm text-zinc-500 hover:underline dark:text-zinc-400"
                  >
                    Delete
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
