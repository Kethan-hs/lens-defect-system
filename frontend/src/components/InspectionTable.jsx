import React, { useEffect, useState, useCallback } from 'react';
import { getInspections } from '../api/client';

/* ─── Collapsible JSON Viewer ──────────────────────────────────────────── */
const JsonNode = ({ data, depth = 0 }) => {
  const [collapsed, setCollapsed] = useState(depth > 1);

  if (data === null || data === undefined) {
    return <span className="text-slate-500 italic">null</span>;
  }

  if (typeof data === 'boolean') {
    return <span className="text-purple-400">{data.toString()}</span>;
  }

  if (typeof data === 'number') {
    return <span className="text-cyan-400">{data}</span>;
  }

  if (typeof data === 'string') {
    return <span className="text-amber-400">"{data}"</span>;
  }

  if (Array.isArray(data)) {
    if (data.length === 0) return <span className="text-slate-500">[]</span>;
    return (
      <div style={{ paddingLeft: depth > 0 ? 16 : 0 }}>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-slate-400 hover:text-slate-200 text-xs mr-1 select-none focus:outline-none min-w-[24px] min-h-[24px]"
        >
          {collapsed ? '▶' : '▼'}
        </button>
        <span className="text-slate-500">Array({data.length})</span>
        {!collapsed && (
          <div className="border-l border-slate-700 ml-1 pl-3">
            {data.map((item, i) => (
              <div key={i} className="py-0.5">
                <span className="text-slate-600 text-xs mr-2">{i}:</span>
                <JsonNode data={item} depth={depth + 1} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (typeof data === 'object') {
    const keys = Object.keys(data);
    if (keys.length === 0) return <span className="text-slate-500">{'{}'}</span>;
    return (
      <div style={{ paddingLeft: depth > 0 ? 16 : 0 }}>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-slate-400 hover:text-slate-200 text-xs mr-1 select-none focus:outline-none min-w-[24px] min-h-[24px]"
        >
          {collapsed ? '▶' : '▼'}
        </button>
        <span className="text-slate-500">Object({keys.length})</span>
        {!collapsed && (
          <div className="border-l border-slate-700 ml-1 pl-3">
            {keys.map((key) => (
              <div key={key} className="py-0.5">
                <span className="text-indigo-400 text-sm">{key}</span>
                <span className="text-slate-600 mx-1">:</span>
                <JsonNode data={data[key]} depth={depth + 1} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return <span className="text-slate-400">{String(data)}</span>;
};

/* ─── Detail Modal (full-screen on mobile) ─────────────────────────────── */
const DetailModal = ({ log, onClose }) => {
  const defects = log.defects_json ? JSON.parse(log.defects_json) : [];
  const isPass = log.pass_fail === 'Pass';
  const [viewMode, setViewMode] = useState('tree');

  // Close on ESC
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // Close on backdrop click
  const handleBackdropClick = useCallback((e) => {
    if (e.target === e.currentTarget) onClose();
  }, [onClose]);

  // Block body scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  return (
    <div
      id="inspection-modal-backdrop"
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-6"
      onClick={handleBackdropClick}
      style={{ backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
    >
      <div
        className="bg-slate-800 w-full sm:max-w-lg sm:rounded-2xl rounded-t-2xl max-h-[95vh] sm:max-h-[85vh] border-t sm:border border-slate-600/50 shadow-2xl flex flex-col overflow-hidden"
        style={{ animation: 'modalIn 0.25s ease-out' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-slate-700 shrink-0">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full shrink-0 ${isPass ? 'bg-emerald-400' : 'bg-rose-400'}`}
                 style={{ boxShadow: isPass ? '0 0 8px #34d399' : '0 0 8px #fb7185' }} />
            <h3 className="text-base sm:text-lg font-bold text-slate-100">Inspection #{log.id}</h3>
          </div>
          <button
            id="modal-close-btn"
            onClick={onClose}
            className="w-10 h-10 sm:w-8 sm:h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-700 active:bg-slate-600 transition-colors text-lg"
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 overscroll-contain">
          {/* Info grid */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-900/60 rounded-lg p-3">
              <span className="text-xs text-slate-500 uppercase tracking-wider block mb-1">Time</span>
              <span className="text-sm text-slate-200">{new Date(log.timestamp).toLocaleString()}</span>
            </div>
            <div className="bg-slate-900/60 rounded-lg p-3">
              <span className="text-xs text-slate-500 uppercase tracking-wider block mb-1">Result</span>
              <span className={`text-sm font-bold ${isPass ? 'text-emerald-400' : 'text-rose-400'}`}>
                {log.pass_fail}
              </span>
            </div>
          </div>

          {/* Defect summary chips */}
          {defects.length > 0 && (
            <div>
              <span className="text-xs text-slate-500 uppercase tracking-wider block mb-2">
                Defects Found ({defects.length})
              </span>
              <div className="flex flex-wrap gap-2">
                {defects.map((d, i) => (
                  <span key={i} className="inline-flex items-center gap-1.5 text-xs bg-slate-700/80 text-slate-200 px-2.5 py-1.5 rounded-lg border border-slate-600/50">
                    <span className="font-medium text-amber-400">{d.class || d.label}</span>
                    <span className="text-slate-400">{(d.confidence * 100).toFixed(0)}%</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* JSON view */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-slate-500 uppercase tracking-wider">Defects Data</span>
              <div className="flex bg-slate-900/60 rounded-lg p-0.5">
                <button
                  onClick={() => setViewMode('tree')}
                  className={`px-3 py-1.5 text-xs rounded-md transition-colors min-h-[32px] ${
                    viewMode === 'tree'
                      ? 'bg-indigo-500/20 text-indigo-400'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  Tree
                </button>
                <button
                  onClick={() => setViewMode('raw')}
                  className={`px-3 py-1.5 text-xs rounded-md transition-colors min-h-[32px] ${
                    viewMode === 'raw'
                      ? 'bg-indigo-500/20 text-indigo-400'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  Raw
                </button>
              </div>
            </div>
            <div className="bg-slate-900 rounded-lg p-3 max-h-[200px] overflow-y-auto overflow-x-auto text-sm font-mono border border-slate-700/50">
              {viewMode === 'tree' ? (
                <JsonNode data={defects} />
              ) : (
                <pre className="text-amber-400 whitespace-pre-wrap break-words text-xs sm:text-sm">
                  {JSON.stringify(defects, null, 2)}
                </pre>
              )}
            </div>
          </div>
        </div>

        {/* Footer — larger touch target */}
        <div className="p-4 border-t border-slate-700 shrink-0">
          <button
            onClick={onClose}
            className="w-full py-3 sm:py-2.5 bg-slate-700 hover:bg-slate-600 active:bg-slate-500 rounded-lg text-slate-100 font-medium transition-colors text-base"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

/* ─── Mobile Inspection Card ───────────────────────────────────────────── */
const InspectionCard = ({ log, onDetails }) => {
  const defects = log.defects_json ? JSON.parse(log.defects_json) : [];
  const isPass = log.pass_fail === 'Pass';

  return (
    <div className="bg-slate-900/40 rounded-lg p-4 border border-slate-700/50 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-slate-400 text-sm font-mono">#{log.id}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${
            isPass ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
          }`}>
            {log.pass_fail}
          </span>
        </div>
        <button
          onClick={() => onDetails(log)}
          className="text-indigo-400 hover:text-indigo-300 active:text-indigo-200 text-sm font-medium px-3 py-1.5 rounded-lg hover:bg-indigo-500/10 transition-colors min-h-[36px]"
        >
          Details →
        </button>
      </div>
      <div className="text-xs text-slate-500">
        {new Date(log.timestamp).toLocaleString()}
      </div>
      {defects.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {defects.map((d, i) => (
            <span key={i} className="text-xs bg-slate-700/80 px-2 py-1 rounded border border-slate-600/50 text-slate-300">
              {d.class}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

/* ─── Inspection Table / Card List ─────────────────────────────────────── */
const InspectionTable = () => {
  const [logs, setLogs] = useState([]);
  const [selectedLog, setSelectedLog] = useState(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const data = await getInspections(0, 10);
        setLogs(data);
      } catch (error) {
        console.error("Error fetching logs:", error);
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-slate-800 rounded-xl shadow-lg border border-slate-700 overflow-hidden">
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg sm:text-xl font-bold text-slate-100">Recent Inspections</h2>
      </div>

      {/* Desktop: Table layout */}
      <div className="hidden sm:block overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-900/50 text-slate-400 text-sm uppercase tracking-wider">
              <th className="p-4 font-medium">ID</th>
              <th className="p-4 font-medium">Time</th>
              <th className="p-4 font-medium">Result</th>
              <th className="p-4 font-medium">Defects</th>
              <th className="p-4 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {logs.map((log) => {
              const defects = log.defects_json ? JSON.parse(log.defects_json) : [];
              const isPass = log.pass_fail === 'Pass';

              return (
                <tr key={log.id} className="hover:bg-slate-700/30 transition-colors">
                  <td className="p-4 text-slate-300">#{log.id}</td>
                  <td className="p-4 text-slate-400">{new Date(log.timestamp).toLocaleString()}</td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      isPass ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                    }`}>
                      {log.pass_fail}
                    </span>
                  </td>
                  <td className="p-4 text-slate-300">
                    {defects.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {defects.map((d, i) => (
                          <span key={i} className="text-xs bg-slate-700 px-2 py-1 rounded border border-slate-600">
                            {d.class}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-slate-500">-</span>
                    )}
                  </td>
                  <td className="p-4 text-right">
                    <button
                      onClick={() => setSelectedLog(log)}
                      className="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors px-2 py-1 rounded hover:bg-indigo-500/10 min-h-[36px]"
                    >
                      Details
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile: Card layout */}
      <div className="sm:hidden p-3 space-y-2">
        {logs.length > 0 ? (
          logs.map((log) => (
            <InspectionCard key={log.id} log={log} onDetails={setSelectedLog} />
          ))
        ) : (
          <div className="text-center text-slate-500 py-8 text-sm">No inspections yet</div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedLog && (
        <DetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />
      )}
    </div>
  );
};

export default InspectionTable;
