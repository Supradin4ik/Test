import { useEffect, useMemo, useState } from 'react';
import {
  fetchProjects,
  getProjectStats,
  toggleProjectStatus,
  uploadExcel,
} from './api';
import UploadModal from './components/UploadModal';

function ProgressBar({ value }) {
  return (
    <div className="w-56">
      <div className="mb-1 text-right text-sm font-medium text-slate-600">{value}%</div>
      <div className="h-4 overflow-hidden rounded-full bg-slate-200">
        <div className="h-4 rounded-full bg-emerald-500" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

export default function App() {
  const [projects, setProjects] = useState([]);
  const [statsByProject, setStatsByProject] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const loadProjects = async () => {
    try {
      setError('');
      setIsLoading(true);
      const response = await fetchProjects();
      const list = Array.isArray(response) ? response : response.projects || [];
      setProjects(list);

      const statsEntries = await Promise.all(
        list.map(async (project) => {
          try {
            const stats = await getProjectStats(project.id);
            return [project.id, stats.overall_progress_percent || 0];
          } catch {
            return [project.id, 0];
          }
        }),
      );

      setStatsByProject(Object.fromEntries(statsEntries));
    } catch {
      setError('Не удалось загрузить проекты. Проверьте доступность API.');
      setProjects([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleUpload = async (file, projectName) => {
    try {
      setIsUploading(true);
      await uploadExcel(file, projectName);
      setUploadOpen(false);
      await loadProjects();
    } finally {
      setIsUploading(false);
    }
  };

  const handleToggleStatus = async (project) => {
    await toggleProjectStatus(project.id, project.status);
    await loadProjects();
  };

  const rows = useMemo(
    () =>
      projects.map((project) => ({
        ...project,
        progress: statsByProject[project.id] ?? 0,
      })),
    [projects, statsByProject],
  );

  return (
    <div className="min-h-screen bg-slate-100 p-8 text-slate-900">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-3xl font-bold">Dashboard заказов</h1>
          <button
            onClick={() => setUploadOpen(true)}
            className="rounded-lg bg-blue-600 px-6 py-3 text-lg font-semibold text-white hover:bg-blue-700"
          >
            + Загрузить Excel
          </button>
        </div>

        {error && <div className="mb-4 rounded-lg bg-red-100 px-4 py-3 text-red-700">{error}</div>}

        <div className="overflow-x-auto rounded-xl bg-white shadow">
          <table className="min-w-full text-left">
            <thead className="bg-slate-50 text-sm uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-6 py-4">Название</th>
                <th className="px-6 py-4">Статус</th>
                <th className="px-6 py-4">Готовность</th>
                <th className="px-6 py-4">Действия</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td className="px-6 py-8 text-lg text-slate-500" colSpan={4}>
                    Загрузка...
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td className="px-6 py-8 text-lg text-slate-500" colSpan={4}>
                    Проекты пока не найдены
                  </td>
                </tr>
              ) : (
                rows.map((project) => {
                  const isPaused = String(project.status).toLowerCase() === 'paused';
                  return (
                    <tr key={project.id} className="border-t border-slate-100">
                      <td className="px-6 py-4 text-lg font-semibold">{project.name}</td>
                      <td className="px-6 py-4">
                        <span
                          className={`rounded-full px-3 py-1 text-sm font-semibold ${
                            isPaused ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'
                          }`}
                        >
                          {project.status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <ProgressBar value={project.progress} />
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={() => handleToggleStatus(project)}
                            className="rounded-lg bg-amber-500 px-4 py-2 text-base font-semibold text-white hover:bg-amber-600"
                          >
                            {isPaused ? 'Разморозить' : 'Заморозить'}
                          </button>
                          <button
                            onClick={() => window.alert('Удаление будет подключено в следующем шаге API')}
                            className="rounded-lg bg-red-600 px-4 py-2 text-base font-semibold text-white hover:bg-red-700"
                          >
                            Удалить
                          </button>
                          <button
                            onClick={() => window.alert(`Проект #${project.id}`)}
                            className="rounded-lg bg-slate-600 px-4 py-2 text-base font-semibold text-white hover:bg-slate-700"
                          >
                            Детали
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <UploadModal
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSubmit={handleUpload}
        isLoading={isUploading}
      />
    </div>
  );
}
