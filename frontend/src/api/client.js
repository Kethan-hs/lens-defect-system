import axios from 'axios';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_URL = (() => {
  const url = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
  if (!url) {
    console.error('[client] VITE_API_URL is not set! WebSocket will fail.');
    return 'http://localhost:8000';
  }
  return url;
})();

const apiClient = axios.create({ baseURL: API_URL });

export const getInspections = (skip = 0, limit = 50) =>
  apiClient.get(`/inspections/?skip=${skip}&limit=${limit}`).then(r => r.data);

export const getStats = () =>
  apiClient.get('/inspections/stats').then(r => r.data);

export const exportCSV = () =>
  window.open(`${API_URL}/export/csv`, '_blank');

export const exportPDF = () =>
  window.open(`${API_URL}/export/pdf`, '_blank');

export const createStreamSocket = (onFrame, onMetadata) => {
  const wsBase = API_URL
    .replace(/^https:/, 'wss:')
    .replace(/^http:/,  'ws:');

  const socket = new WebSocket(`${wsBase}/ws/stream`);
  socket.binaryType = 'blob';

  socket.onmessage = async (event) => {
    if (typeof event.data === 'string') {
      try {
        const parsed = JSON.parse(event.data);
        // Ignore server-side ping frames
        if (parsed?.type === 'ping') return;
        onMetadata(parsed);
      } catch { /* ignore malformed text */ }
    } else {
      try {
        const blob = event.data instanceof Blob
          ? event.data
          : new Blob([event.data], { type: 'image/jpeg' });
        onFrame(URL.createObjectURL(blob));
      } catch { /* ignore bad binary */ }
    }
  };

  return socket;
};
