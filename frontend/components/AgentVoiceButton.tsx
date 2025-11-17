'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

type UICommand = {
  type: string;
  view_mode?: string;
  target_date?: string;
  sort_by?: string;
  sort_order?: string;
  filter_status?: string;
  filter_priority?: string;
  search_results?: number[];
  search_query?: string;
};

type AgentVoiceButtonProps = {
  onTasksUpdated?: () => void;
  onUICommand?: (command: UICommand) => void;
};

export function AgentVoiceButton({ onTasksUpdated, onUICommand }: AgentVoiceButtonProps) {
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const isSpeakingRef = useRef(false);

  const [isActive, setIsActive] = useState(false);
  const [currentTranscript, setCurrentTranscript] = useState('');
  const [agentResponse, setAgentResponse] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [toolActivity, setToolActivity] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);

  const baseUrl = process.env.NEXT_PUBLIC_AGENT_WS_URL ?? 'ws://localhost:8000/api/agent';

  // Text-to-Speech
  const speak = useCallback((text: string) => {
    if (!window.speechSynthesis || !text.trim()) return;
    
    window.speechSynthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.1;
    utterance.pitch = 1.0;
    
    const voices = window.speechSynthesis.getVoices();
    
    // Voice selection priority:
    // 1. Female voices (prefer "female" in name)
    // 2. US/UK/AU English (avoid Indian accent)
    // 3. Local/offline voices (faster, more reliable)
    
    const preferredVoice = 
      // Try female US/UK voices first
      voices.find(v => 
        (v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-AU') && 
        (v.name.toLowerCase().includes('female') || 
         v.name.toLowerCase().includes('samantha') ||
         v.name.toLowerCase().includes('karen') ||
         v.name.toLowerCase().includes('victoria'))
      ) ||
      // Any female English voice
      voices.find(v => 
        v.lang.startsWith('en-') && 
        (v.name.toLowerCase().includes('female') || 
         v.name.toLowerCase().includes('woman'))
      ) ||
      // Any US/UK/AU voice (no Indian accent)
      voices.find(v => 
        (v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-AU') &&
        !v.name.toLowerCase().includes('india')
      ) ||
      // Fallback to any English voice
      voices.find(v => v.lang.startsWith('en-')) ||
      voices[0];
    
    if (preferredVoice) {
      utterance.voice = preferredVoice;
      console.log(`🔊 Using voice: ${preferredVoice.name} (${preferredVoice.lang})`);
    }
    
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    
    window.speechSynthesis.speak(utterance);
  }, []);

  // Stop speech
  const stopSpeaking = useCallback(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  }, []);

  // Cleanup
  const cleanup = useCallback(() => {
    stopSpeaking();
    
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    
    if (audioContextRef.current?.state !== 'closed') {
      audioContextRef.current?.close();
    }
    audioContextRef.current = null;
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop());
      mediaStreamRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, [stopSpeaking]);

  // Load TTS voices on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }
    
    return cleanup;
  }, [cleanup]);

  // Keep speaking ref in sync
  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
  }, [isSpeaking]);

  // Start agent
  const handleStart = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        model: 'flux-general-en',
        sample_rate: '16000',
        encoding: 'linear16',
        eot_threshold: '0.9',
      });

      const ws = new WebSocket(`${baseUrl}?${params.toString()}`);
      wsRef.current = ws;

      ws.onopen = () => console.log('✅ WebSocket connected');
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // FLUX transcription
          if (data.type === 'flux_event' && data.data?.type === 'TurnInfo') {
            const transcript = data.data.transcript;
            if (transcript) {
              setCurrentTranscript(transcript);
              
              // User interrupt - stop agent and TTS
              if (transcript.length > 5 && (isProcessing || isSpeaking)) {
                console.log('🛑 User interrupt');
                stopSpeaking();
                setAgentResponse('');
                setToolActivity('');
                setIsProcessing(false);
              }
            }
            
            if (data.data.event === 'EndOfTurn') {
              setIsProcessing(true);
              setAgentResponse('');
              setToolActivity('');
            }
          }

          // Agent start
          else if (data.type === 'agent_start') {
            stopSpeaking();
            setIsProcessing(true);
            setAgentResponse('');
            setToolActivity('Processing...');
          }

          // Agent events
          else if (data.type === 'agent_event') {
            const event = data.data;

            if (event.type === 'thinking') {
              setToolActivity(event.content || 'Thinking...');
            }
            
            else if (event.type === 'text') {
              const text = event.content || '';
              setAgentResponse(prev => {
                const updated = prev + text;
                
                // Speak early if we have enough content (better perceived speed)
                // Check for sentence endings or if response is getting long
                if (!isSpeaking && updated.length > 5) {
                  const hasEnding = updated.match(/[.!?]\s*$/);
                  const isLongEnough = updated.length > 15;
                  
                  if (hasEnding || isLongEnough) {
                    speak(updated);
                  }
                }
                
                return updated;
              });
            }
            
            else if (event.type === 'tool_use_start') {
              setToolActivity(`Using: ${event.tool}`);
            }
            
            else if (event.type === 'tool_result') {
              setToolActivity(`Done: ${event.tool}`);
              
              // UI command
              if (event.result?.ui_command) {
                onUICommand?.(event.result.ui_command);
              }
              
              // Refresh UI only for write operations
              if (['create_task', 'update_task', 'delete_task'].includes(event.tool)) {
                onTasksUpdated?.();
              }
            }
            
            else if (event.type === 'done') {
              setIsProcessing(false);
              setToolActivity('');
              
              // Speak the complete response if we have one
              setAgentResponse(currentResponse => {
                if (currentResponse && currentResponse.trim() && !isSpeaking) {
                  speak(currentResponse);
                }
                return currentResponse;
              });
              
              setTimeout(() => {
                setCurrentTranscript('');
                setAgentResponse('');
              }, 3000);
            }
            
            else if (event.type === 'error') {
              setIsProcessing(false);
              setToolActivity('');
              stopSpeaking();
              setAgentResponse('');
            }
          }

          // Agent error
          else if (data.type === 'agent_error') {
            console.error('❌ Agent error:', data.error);
            setIsProcessing(false);
            setToolActivity('');
            stopSpeaking();
            setAgentResponse('');
            setCurrentTranscript('');
          }
          
        } catch (err) {
          console.error('❌ Message parse error:', err);
        }
      };

      ws.onclose = () => {
        console.log('❌ WebSocket closed');
        setIsActive(false);
        setIsProcessing(false);
      };

      ws.onerror = (err) => console.error('❌ WebSocket error:', err);

      // Start microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      const AudioContextCtor = (window.AudioContext || (window as Window & typeof globalThis & { webkitAudioContext: typeof AudioContext }).webkitAudioContext) as typeof AudioContext;
      const audioContext = new AudioContextCtor({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(1024, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        // Mute mic during TTS
        if (isSpeakingRef.current) return;
        
        if (ws.readyState === WebSocket.OPEN) {
          const input = event.inputBuffer.getChannelData(0);
          const int16 = new Int16Array(input.length);
          for (let i = 0; i < input.length; i++) {
            const s = Math.max(-1, Math.min(1, input[i]));
            int16[i] = Math.round(s * 32767);
          }
          ws.send(int16.buffer);
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      setIsActive(true);
      setCurrentTranscript('');
      setAgentResponse('');
      
    } catch (err) {
      console.error('❌ Start failed:', err);
      cleanup();
    }
  }, [baseUrl, speak, stopSpeaking, onTasksUpdated, onUICommand, isProcessing, isSpeaking, cleanup]);

  // Stop agent
  const handleStop = useCallback(() => {
    cleanup();
    setIsActive(false);
    setIsProcessing(false);
    setCurrentTranscript('');
    setAgentResponse('');
    setToolActivity('');
  }, [cleanup]);

  return (
    <div className="fixed bottom-8 left-1/2 z-50 flex -translate-x-1/2 flex-col items-center gap-3">
      {/* Agent response */}
      {agentResponse && (
        <div className="max-w-lg rounded-2xl bg-emerald-500 px-6 py-3 text-center text-sm font-medium text-white shadow-2xl flex items-center gap-2 justify-center">
          {isSpeaking && (
            <svg className="w-4 h-4 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
              <path d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" />
            </svg>
          )}
          <span>{agentResponse}</span>
        </div>
      )}

      {/* Tool activity */}
      {isProcessing && toolActivity && !agentResponse && (
        <div className="max-w-md rounded-2xl bg-blue-500 px-6 py-3 text-center text-sm font-medium text-white shadow-2xl">
          {toolActivity}
        </div>
      )}

      {/* Transcript */}
      {isActive && currentTranscript && !isProcessing && (
        <div className="max-w-md rounded-2xl bg-white px-6 py-3 text-center text-sm text-zinc-800 shadow-2xl dark:bg-zinc-800 dark:text-zinc-100">
          {currentTranscript}
        </div>
      )}

      {/* Voice button */}
      <button
        type="button"
        onClick={isActive ? handleStop : handleStart}
        disabled={isProcessing}
        className={`flex h-16 w-16 items-center justify-center rounded-full shadow-2xl transition-all hover:scale-105 ${
          isActive ? 'bg-red-500 hover:bg-red-400' : 'bg-emerald-500 hover:bg-emerald-400'
        } ${isProcessing ? 'opacity-70 cursor-not-allowed' : ''}`}
      >
        {isActive ? (
          <svg className="h-8 w-8 text-white" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg className="h-8 w-8 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        )}
      </button>
    </div>
  );
}
