import React from 'react';
import LiveFeed from './components/LiveFeed';
import DefectStats from './components/DefectStats';
import PassFailTrend from './components/PassFailTrend';
import InspectionTable from './components/InspectionTable';
import ExportPanel from './components/ExportPanel';

function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-200 font-sans">
      {/* Top bar */}
      <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-md border-b border-slate-700/60">
        <div className="max-w-screen-2xl mx-auto px-3 sm:px-6 lg:px-8 py-2.5 sm:py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 sm:gap-3">
              <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-indigo-500 flex items-center justify-center text-white font-bold text-base sm:text-lg shadow-lg shadow-indigo-500/20">
                L
              </div>
              <div>
                <h1 className="text-base sm:text-xl font-bold text-slate-100 tracking-tight leading-tight">Optical Lens QA</h1>
                <p className="text-[10px] sm:text-xs text-slate-400 hidden sm:block">Real-time Defect Detection System</p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400" style={{ boxShadow: '0 0 6px #34d399' }} />
              <span className="text-[10px] sm:text-xs text-slate-400">Active</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main content — single column on mobile, grid on desktop */}
      <main className="max-w-screen-2xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-6">
        {/* Row 1: Live Feed + Stats/Export */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6">
          {/* Live Feed — full width on mobile */}
          <div className="lg:col-span-8 min-h-[300px] sm:min-h-[420px] lg:min-h-[480px]">
            <LiveFeed />
          </div>

          {/* Stats & Export — stacks below feed on mobile */}
          <div className="lg:col-span-4 grid grid-cols-2 lg:grid-cols-1 gap-4 sm:gap-6">
            <DefectStats />
            <ExportPanel />
          </div>
        </div>

        {/* Row 2: Yield Trend */}
        <PassFailTrend />

        {/* Row 3: Inspection History */}
        <InspectionTable />
      </main>
    </div>
  );
}

export default App;
