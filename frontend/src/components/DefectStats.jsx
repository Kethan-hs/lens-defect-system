import React, { useState, useEffect } from 'react';
import { getStats } from '../api/client';

const DefectStats = () => {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await getStats();
        setStats(data);
      } catch (error) {
        console.error("Error fetching stats:", error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return <div className="animate-pulse bg-slate-800 h-40 rounded-xl"></div>;

  const defectColors = {
    bubble: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
    crack: 'text-rose-400 bg-rose-400/10 border-rose-400/20',
    dots: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
    scratch: 'text-orange-400 bg-orange-400/10 border-orange-400/20'
  };

  return (
    <div className="bg-slate-800 p-3 sm:p-4 rounded-xl shadow-lg border border-slate-700">
      <h2 className="text-lg sm:text-xl font-bold text-slate-100 mb-3 sm:mb-4">Defect Distribution</h2>
      <div className="grid grid-cols-2 gap-2 sm:gap-3">
        {Object.entries(stats.defect_counts).map(([cls, count]) => (
          <div key={cls} className={`p-2.5 sm:p-3 rounded-lg border flex flex-col items-center justify-center ${defectColors[cls] || 'text-slate-400 bg-slate-700 border-slate-600'}`}>
            <span className="text-xs font-medium uppercase tracking-wider mb-1">{cls}</span>
            <span className="text-xl sm:text-2xl font-bold">{count}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 sm:mt-4 flex justify-between text-xs sm:text-sm text-slate-400 border-t border-slate-700 pt-3">
        <span>Total: {stats.total}</span>
        <span className="text-emerald-400">Yield: {stats.total ? ((stats.pass / stats.total) * 100).toFixed(1) : 0}%</span>
      </div>
    </div>
  );
};

export default DefectStats;
