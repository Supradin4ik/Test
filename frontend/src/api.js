import axios from 'axios';

const baseURL = "http://127.0.0.1:8000";

const api = axios.create({
  baseURL,
  timeout: 10000,
});

export const fetchProjects = async () => {
  const { data } = await api.get('/api/projects');
  return data;
};

export const uploadExcel = async (file, projectName) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('project_name', projectName);

  const { data } = await api.post('/api/projects/upload-spec', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

  return data;
};

export const toggleProjectStatus = async (projectId, currentStatus) => {
  const { data } = await api.patch(`/api/projects/${projectId}/status`, {
    current_status: currentStatus,
  });
  return data;
};

export const getProjectStats = async (projectId) => {
  const { data } = await api.get(`/api/projects/${projectId}/stats`);
  return data;
};

export default api;
