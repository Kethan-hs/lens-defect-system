import React, { useEffect, useState } from 'react';
import { getInspections } from '../api/client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const PassFailTrend = () => {
  const [data, setData] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const logs = await getInspections(0, 50);
        
        // Reverse to get chronological order
        const chronological = [...logs].reverse();
        
        let passCount = 0;
        const trendData = chronological.map((log, index) => {
          if (log.pass_fail === 'Pass') passCount++;
          return {
            id: log.id,
            time: new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
            passRate: ((passCount / (index + 1)) * 100).toFixed(1)
          };
        });
        
        setData(trendData);
      } catch (error) {
        console.error("Error fetching trend data:", error);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-slate-800 p-4 rounded-xl shadow-lg border border-slate-700">
      <h2 className="text-xl font-bold text-slate-100 mb-4">Yield Trend (Last 50 Scans)</h2>
      <ResponsiveContainer width="100%" height={200} minWidth={0}>
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
          <YAxis stroke="#94a3b8" fontSize={12} domain={[0, 100]} tickFormatter={(val) => `${val}%`} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }}
            itemStyle={{ color: '#34d399' }}
          />
          <Line type="monotone" dataKey="passRate" stroke="#34d399" strokeWidth={3} dot={false} name="Pass Rate %" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PassFailTrend;
