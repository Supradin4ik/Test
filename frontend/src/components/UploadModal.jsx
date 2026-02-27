import { useState } from 'react';

export default function UploadModal({ isOpen, onClose, onSubmit, isLoading }) {
  const [projectName, setProjectName] = useState('');
  const [file, setFile] = useState(null);

  if (!isOpen) return null;

  const submit = async (event) => {
    event.preventDefault();
    if (!projectName.trim() || !file) return;

    await onSubmit(file, projectName.trim());
    setProjectName('');
    setFile(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <form className="w-full max-w-xl rounded-xl bg-white p-6 shadow-2xl" onSubmit={submit}>
        <h2 className="mb-5 text-2xl font-semibold text-slate-900">Загрузка спецификации</h2>

        <label className="mb-3 block text-base font-medium text-slate-700">Название проекта</label>
        <input
          value={projectName}
          onChange={(event) => setProjectName(event.target.value)}
          className="mb-4 w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-blue-500 focus:outline-none"
          placeholder="Например: Заказ #148"
          required
        />

        <label className="mb-3 block text-base font-medium text-slate-700">Excel файл (.xlsx)</label>
        <input
          type="file"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
          className="mb-6 block w-full rounded-lg border border-slate-300 p-3 text-base"
          accept=".xlsx,.xls"
          required
        />

        <div className="flex flex-wrap justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-5 py-3 text-lg font-semibold text-slate-700"
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="rounded-lg bg-blue-600 px-5 py-3 text-lg font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {isLoading ? 'Загрузка...' : 'Загрузить'}
          </button>
        </div>
      </form>
    </div>
  );
}
