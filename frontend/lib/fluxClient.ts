'use client';

export type FluxEvent =
  | 'StartOfTurn'
  | 'Update'
  | 'EagerEndOfTurn'
  | 'TurnResumed'
  | 'EndOfTurn';

export type FluxMessage = {
  type: 'TurnInfo';
  event: FluxEvent;
  turn_index?: number;
  transcript?: string;
  end_of_turn_confidence?: number;
  audio_window_start?: number;
  audio_window_end?: number;
};

type FluxClientHandlers = {
  onMessage?: (message: unknown) => void;
  onTurnInfo?: (turn: FluxMessage) => void;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (event: Event) => void;
};

type FluxClientOptions = {
  baseUrl: string;
  model?: string;
  sampleRate?: number;
  encoding?: string;
  eotThreshold?: number;
  eagerEotThreshold?: number;
} & FluxClientHandlers;

export class FluxClient {
  private ws: WebSocket | null = null;
  private audioContext: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private mediaStream: MediaStream | null = null;

  constructor(private readonly options: FluxClientOptions) {}

  async connect(): Promise<void> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return;
    }

    const {
      baseUrl,
      model = 'flux-general-en',
      sampleRate = 16_000,
      encoding = 'linear16',
      eotThreshold = 0.7,
      eagerEotThreshold,
    } = this.options;

    const params = new URLSearchParams({
      model,
      sample_rate: sampleRate.toString(),
      encoding,
      eot_threshold: eotThreshold.toString(),
    });

    if (
      typeof eagerEotThreshold === 'number' &&
      !Number.isNaN(eagerEotThreshold)
    ) {
      params.append('eager_eot_threshold', eagerEotThreshold.toString());
    }

    const ws = new WebSocket(`${baseUrl}?${params.toString()}`);
    ws.binaryType = 'arraybuffer';

    this.ws = ws;

    await new Promise<void>((resolve, reject) => {
      const cleanup = () => {
        ws.removeEventListener('open', handleOpen);
        ws.removeEventListener('close', handleClose);
        ws.removeEventListener('error', handleError);
        ws.removeEventListener('message', handleMessage);
      };

      const handleOpen = () => {
        this.options.onOpen?.();
        resolve();
      };

      const handleClose = (event: CloseEvent) => {
        cleanup();
        this.options.onClose?.(event);
        if (ws !== this.ws) {
          return;
        }

        if (event.code !== 1000) {
          reject(new Error(`WebSocket closed: ${event.code} ${event.reason}`));
        }
      };

      const handleError = (event: Event) => {
        cleanup();
        this.options.onError?.(event);
        if (ws === this.ws) {
          this.ws = null;
        }
        reject(new Error('WebSocket connection error'));
      };

      const handleMessage = (event: MessageEvent<string | ArrayBuffer>) => {
        if (typeof event.data !== 'string') {
          return;
        }
        try {
          const parsed = JSON.parse(event.data);
          this.options.onMessage?.(parsed);
          if (parsed?.type === 'TurnInfo') {
            this.options.onTurnInfo?.(parsed as FluxMessage);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.addEventListener('open', handleOpen, { once: true });
      ws.addEventListener('close', handleClose);
      ws.addEventListener('error', handleError, { once: true });
      ws.addEventListener('message', handleMessage);
    });
  }

  async startMicrophone(): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not connected');
    }
    if (this.mediaStream) {
      return;
    }

    const sampleRate = this.options.sampleRate ?? 16_000;

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate,
        // Enable echo cancellation and related processing so speaker output
        // is less likely to be picked up by the microphone.
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    this.mediaStream = stream;

    const AudioContextCtor = (window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext) as typeof AudioContext | undefined;

    if (!AudioContextCtor) {
      throw new Error('AudioContext is not supported in this browser');
    }

    this.audioContext = new AudioContextCtor({ sampleRate });

    const source = this.audioContext.createMediaStreamSource(stream);
    const bufferSize = 1024;
    this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

    this.processor.onaudioprocess = (event) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        return;
      }
      const input = event.inputBuffer.getChannelData(0);
      const int16 = new Int16Array(input.length);
      for (let i = 0; i < input.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, input[i]));
        int16[i] = Math.round(sample * 32767);
      }
      this.ws.send(int16.buffer);
    };

    source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);
  }

  stopMicrophone(): void {
    if (this.processor) {
      this.processor.disconnect();
      this.processor.onaudioprocess = null;
      this.processor = null;
    }

    if (this.audioContext && this.audioContext.state !== 'closed') {
      this.audioContext.close();
    }
    this.audioContext = null;

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
    }
    this.mediaStream = null;
  }

  disconnect(): void {
    this.stopMicrophone();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

