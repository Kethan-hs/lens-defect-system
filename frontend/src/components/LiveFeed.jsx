import React, { useEffect, useState, useRef } from 'react';
import { createStreamSocket } from '../api/client';

const LiveFeed = () => {
  const [frameSrc, setFrameSrc]           = useState(null);
  const [metadata, setMetadata]           = useState(null);
  const [debugLog, setDebugLog]           = useState(['Initializing...']);
  const [connectionState, setConnectionState] = useState('connecting');
  const [cameraReady, setCameraReady] = useState(false);
  const [fallbackImage, setFallbackImage] = useState(null);

  const socketRef  = useRef(null);
  const videoRef   = useRef(null);
  const canvasRef  = useRef(null);
  const requestRef = useRef(null);
  const waitingForResponse = useRef(false);

  const addLog = (msg) => setDebugLog(prev => [...prev.slice(-4), msg]);

  // ── Socket + camera setup ───────────────────────────────────────────────────
  useEffect(() => {
    addLog('Connecting socket...');
    socketRef.current = createStreamSocket(
      (url) => {
        setFrameSrc(prev => {
          if (prev) URL.revokeObjectURL(prev);
          return url;
        });
      },
      (meta) => {
        addLog(`Meta: ${meta.pass_fail} | lens=${meta.lens_detected}`);
        setMetadata(meta);
      }
    );

    socketRef.current.onopen  = () => { addLog('Socket OPEN');   setConnectionState('open'); };
    socketRef.current.onerror = () => { addLog('Socket ERROR');  setConnectionState('error'); };
    socketRef.current.onclose = () => { addLog('Socket CLOSED'); setConnectionState('closed'); };

    // Camera
    const setupCamera = async () => {
      try {
        addLog('Requesting camera...');
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        addLog('Camera granted!');
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.onloadedmetadata = () => setCameraReady(true);
        }
      } catch (err) {
        addLog('Camera error — using fallback image');
        console.warn('Webcam unavailable:', err);
        const img = new Image();
        img.src = '/test.jpg';
        img.onload = () => setFallbackImage(img);
      }
    };
    setupCamera();

    return () => {
      socketRef.current?.close();
      if (videoRef.current?.srcObject) {
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
      }
      if (requestRef.current) clearTimeout(requestRef.current);
    };
  }, []);

  // Reset backpressure flag when we get a new frame or metadata
  useEffect(() => {
    if (metadata !== null || frameSrc !== null) {
      waitingForResponse.current = false;
    }
  }, [metadata, frameSrc]);

  useEffect(() => {
  const interval = setInterval(() => {
    waitingForResponse.current = false;
  }, 3000);
  return () => clearInterval(interval);
  }, []);
  // ── Frame send loop ─────────────────────────────────────────────────────────
  useEffect(() => {
    const sendFrame = () => {
      if (
        socketRef.current?.readyState === WebSocket.OPEN &&
        canvasRef.current &&
        !waitingForResponse.current &&
        (cameraReady || fallbackImage)
      ) {
        const video  = videoRef.current;
        const canvas = canvasRef.current;
        const ctx    = canvas.getContext('2d');
        let shouldSend = false;

        if (video && video.videoWidth > 0 && video.videoHeight > 0) {
          canvas.width  = video.videoWidth;
          canvas.height = video.videoHeight;
          ctx.drawImage(video, 0, 0);
          shouldSend = true;
        } else if (fallbackImage) {
          canvas.width  = fallbackImage.width;
          canvas.height = fallbackImage.height;
          // Slight wobble so backend sees a different frame each time
          const offset = Math.sin(Date.now() / 500) * 3;
          ctx.drawImage(fallbackImage, offset, offset, canvas.width, canvas.height);
          shouldSend = true;
        }

        if (shouldSend) {
          canvas.toBlob((blob) => {
            if (blob && socketRef.current?.readyState === WebSocket.OPEN) {
              waitingForResponse.current = true;
              socketRef.current.send(blob);
            }
          }, 'image/jpeg', 0.8);
        }
      }
      requestRef.current = setTimeout(() => requestAnimationFrame(sendFrame), 33);
    };

    requestRef.current = setTimeout(() => requestAnimationFrame(sendFrame), 500);
    return () => clearTimeout(requestRef.current);
  }, [fallbackImage, cameraReady]);

  // ── Derived state ────────────────────────────────────────────────────────────
  const isPass   = metadata?.pass_fail === 'Pass';
  const hasLens  = metadata?.lens_detected || metadata?.is_lens_found;
  const segAge   = metadata?.seg_age_s;

  const dotColor = {
    connecting: 'bg-yellow-400',
    open:       'bg-emerald-400',
    closed:     'bg-slate-500',
    error:      'bg-rose-400',
  }[connectionState];

  return (
    <div className="bg-slate-800 p-3 sm:p-4 rounded-xl shadow-lg border border-slate-700 h-full flex flex-col">

      {/* Header */}
      <div className="flex justify-between items-center mb-2 sm:mb-3 shrink-0">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`}
            style={{ boxShadow: connectionState === 'open' ? '0 0 6px #34d399' : 'none' }}
          />
          <h2 className="text-base sm:text-lg font-bold text-slate-100">Live Camera Feed</h2>
        </div>

        <div className="flex items-center gap-2">
          {/* Seg-refresh badge */}
          {hasLens && segAge !== undefined && (
            <span className="text-[10px] text-slate-500 hidden sm:block">
              seg {segAge}s ago
            </span>
          )}
          {/* Pass / Fail badge */}
          {metadata && (
            <span className={`px-2 sm:px-3 py-1 rounded-full text-xs sm:text-sm font-bold transition-colors ${
              !hasLens
                ? 'bg-slate-600 text-slate-300'
                : isPass
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                : 'bg-rose-500/20 text-rose-400 border border-rose-500/50'
            }`}>
              {!hasLens ? 'Scanning...' : metadata.pass_fail}
            </span>
          )}
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 flex flex-col lg:flex-row gap-3 min-h-0">

        {/* Video container */}
        <div className="flex-1 min-h-0 min-w-0">
          <div
            className="relative w-full bg-black rounded-lg overflow-hidden"
            style={{ aspectRatio: '16/9', minHeight: '200px' }}
          >
            {/* Hidden capture elements */}
            <video ref={videoRef} autoPlay playsInline muted className="hidden" />
            <canvas ref={canvasRef} className="hidden" />

            {frameSrc ? (
              <img
                src={frameSrc}
                alt="Live annotated feed"
                className="absolute inset-0 w-full h-full object-contain"
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 px-4">
                <div
                  className="w-10 h-10 sm:w-12 sm:h-12 border-2 border-slate-600 border-t-indigo-400 rounded-full mb-3"
                  style={{ animation: 'spin 1s linear infinite' }}
                />
                <span className="text-xs sm:text-sm mb-2">Connecting to stream...</span>
                <div className="text-xs text-slate-600 space-y-0.5 text-center max-w-xs hidden sm:block">
                  {debugLog.map((l, i) => <div key={i}>{l}</div>)}
                </div>
              </div>
            )}

            {/* LIVE badge */}
            {frameSrc && connectionState === 'open' && (
              <div className="absolute top-2 left-2 sm:top-3 sm:left-3 flex items-center gap-1.5 bg-black/60 rounded-full px-2 py-0.5 sm:px-2.5 sm:py-1 backdrop-blur-sm">
                <div
                  className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-rose-500"
                  style={{ animation: 'pulse-dot 1.5s ease-in-out infinite' }}
                />
                <span className="text-[10px] sm:text-xs font-medium text-white tracking-wide">LIVE</span>
              </div>
            )}

            {/* Seg model indicator */}
            {hasLens && frameSrc && (
              <div className="absolute bottom-2 right-2 bg-black/60 rounded px-1.5 py-0.5 backdrop-blur-sm hidden sm:block">
                <span className="text-[10px] text-teal-400 font-mono">SEG ✓</span>
              </div>
            )}
          </div>
        </div>

        {/* Detections sidebar */}
        <div className="lg:w-44 shrink-0 bg-slate-900 rounded-lg p-2 sm:p-3 overflow-y-auto max-h-32 sm:max-h-40 lg:max-h-none">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1.5 sm:mb-2">
            Detections
          </h3>

          {metadata?.detections?.length > 0 ? (
            <div className="flex lg:flex-col gap-1.5 overflow-x-auto lg:overflow-x-visible pb-1 lg:pb-0">
              {metadata.detections.map((det, i) => (
                <div
                  key={i}
                  className="bg-slate-800 p-2 rounded text-sm border border-slate-700 shrink-0 min-w-[120px] lg:min-w-0"
                >
                  <div className="flex justify-between items-center gap-2">
                    <span className="font-medium text-amber-400 text-xs">{det.label || det.class}</span>
                    <span className="text-slate-400 text-xs">{(det.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="mt-1.5 h-1 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${(det.confidence * 100).toFixed(0)}%`,
                        background: det.confidence > 0.7
                          ? 'linear-gradient(90deg, #f59e0b, #ef4444)'
                          : 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-500 text-center mt-2 sm:mt-3">
              {hasLens ? '✓ No defects' : 'No lens detected'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LiveFeed;
