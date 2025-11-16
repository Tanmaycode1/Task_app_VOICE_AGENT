'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { FluxClient } from '@/lib/fluxClient';

type VoiceButtonProps = {
  onTranscript?: (text: string) => void;
};

export function VoiceButton({ onTranscript }: VoiceButtonProps) {
  const fluxRef = useRef<FluxClient | null>(null);
  const [isActive, setIsActive] = useState(false);
  const [currentTranscript, setCurrentTranscript] = useState('');

  const baseUrl =
    typeof window !== 'undefined'
      ? process.env.NEXT_PUBLIC_FLUX_WS_URL ?? 'ws://localhost:8000/api/flux'
      : '';

  useEffect(() => {
    return () => {
      fluxRef.current?.disconnect();
    };
  }, []);

  const handleStart = useCallback(async () => {
    const flux = new FluxClient({
      baseUrl,
      eotThreshold: 0.7,
      eagerEotThreshold: 0.6,
      onTurnInfo: (info) => {
        if (info.transcript) {
          setCurrentTranscript(info.transcript);
        }
        if (info.event === 'EndOfTurn' && info.transcript) {
          onTranscript?.(info.transcript);
        }
      },
    });

    fluxRef.current?.disconnect();
    fluxRef.current = flux;

    try {
      await flux.connect();
      await flux.startMicrophone();
      setIsActive(true);
      setCurrentTranscript('');
    } catch (err) {
      console.error('Failed to start voice:', err);
      flux.disconnect();
      fluxRef.current = null;
    }
  }, [baseUrl, onTranscript]);

  const handleStop = useCallback(() => {
    fluxRef.current?.disconnect();
    fluxRef.current = null;
    setIsActive(false);
    setCurrentTranscript('');
  }, []);

  return (
    <div className="fixed bottom-8 left-1/2 z-50 flex -translate-x-1/2 flex-col items-center gap-3">
      {isActive && currentTranscript && (
        <div className="max-w-md rounded-2xl bg-white px-6 py-3 text-center text-sm text-zinc-800 shadow-2xl dark:bg-zinc-800 dark:text-zinc-100">
          {currentTranscript}
        </div>
      )}
      <button
        type="button"
        onClick={isActive ? handleStop : handleStart}
        className={`flex h-16 w-16 items-center justify-center rounded-full shadow-2xl transition-all hover:scale-105 ${
          isActive
            ? 'bg-red-500 hover:bg-red-400'
            : 'bg-emerald-500 hover:bg-emerald-400'
        }`}
        aria-label={isActive ? 'Stop listening' : 'Start listening'}
      >
        {isActive ? (
          <svg
            className="h-8 w-8 text-white"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg
            className="h-8 w-8 text-white"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        )}
      </button>
    </div>
  );
}

