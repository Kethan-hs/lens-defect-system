import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_URL,
});

export const getInspections = async (skip = 0, limit = 50) => {
  const response = await apiClient.get(`/inspections/?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const getStats = async () => {
  const response = await apiClient.get('/inspections/stats');
  return response.data;
};

export const exportCSV = () => {
  window.open(`${API_URL}/export/csv`, '_blank');
};

export const exportPDF = () => {
  window.open(`${API_URL}/export/pdf`, '_blank');
};

export const createStreamSocket = (onFrame, onMetadata) => {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // Proper protocol conversion
  const WS_URL = API_URL
    .replace(/^https:/, 'wss:')
    .replace(/^http:/, 'ws:');

  const socket = new WebSocket(`${WS_URL}/ws/stream`);

  socket.binaryType = 'blob';

  socket.onmessage = async (event) => {
    if (typeof event.data === 'string') {
      try {
        const metadata = JSON.parse(event.data);
        onMetadata(metadata);
      } catch (e) {
        console.error("Error parsing metadata", e);
      }
    } else {
      try {
        const blob =
          event.data instanceof Blob
            ? event.data
            : new Blob([event.data], { type: 'image/jpeg' });

        const url = URL.createObjectURL(blob);
        onFrame(url);
      } catch (e) {
        console.error("Error creating object URL from frame data", e);
      }
    }
  };

  return socket;
};
