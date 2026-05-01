import React, { useEffect, useState } from 'react';
import { getInspections } from '../api/client';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';

const PassFailTrend = () => {
  const [data, setData]   = useState([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      try {
        const logs = await getInspections(0, 50);
        const chrono = [...logs].reverse();

        let passCount = 0;
        const trend = chrono.map((log, i) => {
          if (log.pass_fail === 'Pass') passCount++;

          // FIX: append 'Z' if the timestamp has no timezone — backend returns UTC
          const raw = log.timestamp;
          const ts  = raw && !raw.endsWith('Z') && !raw.includes('+') ? raw + 'Z' : raw;
          const d   = new Date(ts);
          const time = isNaN(d) ? `#${log.id}` :
            d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

          return {
            id:       log.id,
            time,
            passRate: parseFloat(((passCount / (i + 1)) * 100).toFixed(1)),
          };
        });

        setData(trend);
        setError(false);
      } catch {
        setError(true);
      }
    };

    fetch();
    const id = setInterval(fetch, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="bg-slate-800 p-4 rounded-xl shadow-lg border border-slate-700">
      <h2 className="text-lg sm:text-xl font-bold text-slate-100 mb-4">
        Yield Trend
        <span className="text-sm font-normal text-slate-500 ml-2">(last 50 scans)</span>
      </h2>

      {error ? (
        <div className="flex items-center justify-center h-[160px] text-slate-500 text-sm">
          Could not load trend data
        </div>
      ) : data.length === 0 ? (
        <div className="flex items-center justify-center h-[160px] text-slate-500 text-sm">
          No inspections yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200} minWidth={0}>
          <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis
              dataKey="time"
              stroke="#94a3b8"
              fontSize={11}
              tick={{ fill: '#94a3b8' }}
              interval="preserveStartEnd"
            />
            <YAxis
              stroke="#94a3b8"
              fontSize={11}
              domain={[0, 100]}
              tick={{ fill: '#94a3b8' }}
              tickFormatter={v => `${v}%`}
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc', borderRadius: 8 }}
              itemStyle={{ color: '#34d399' }}
              formatter={v => [`${v}%`, 'Pass Rate']}
            />
            <ReferenceLine y={80} stroke="#f59e0b" strokeDasharray="4 4" strokeWidth={1} />
            <Line
              type="monotone"
              dataKey="passRate"
              stroke="#34d399"
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 5, fill: '#34d399' }}
              name="Pass Rate"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
};

export default PassFailTrend;
