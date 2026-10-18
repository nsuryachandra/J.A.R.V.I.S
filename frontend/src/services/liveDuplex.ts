/**
 * Real-Time Live Duplex Voice Conversation Manager for J.A.R.V.I.S.
 * Provides continuous hands-free bidirectional audio communication with barge-in interruption.
 */

import { soundFx } from './sound';

export type LiveIntercomState = 'OFF' | 'LISTENING' | 'THINKING' | 'SPEAKING' | 'INTERRUPTED';

export interface LiveDuplexCallbacks {
  onStateChange: (state: LiveIntercomState) => void;
  onTranscriptUpdate: (interim: string, isFinal: boolean) => void;
  onMessageComplete: (finalText: string) => Promise<string | void>; // Returns assistant response
  onVolumeChange?: (volume: number) => void; // 0.0 to 1.0 for real-time waveform
}

class LiveDuplexManager {
  private active: boolean = false;
  private recognition: any = null;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private mediaStream: MediaStream | null = null;
  private animFrameId: number | null = null;

  private state: LiveIntercomState = 'OFF';
  private callbacks: LiveDuplexCallbacks | null = null;
  private silenceTimer: any = null;
  public currentUtterance: SpeechSynthesisUtterance | null = null;
  private currentAudioElement: HTMLAudioElement | null = null;

  public isRunning(): boolean {
    return this.active;
  }

  public getState(): LiveIntercomState {
    return this.state;
  }

  /**
   * Start hands-free continuous live conversation mode
   */
  public async start(callbacks: LiveDuplexCallbacks): Promise<boolean> {
    this.callbacks = callbacks;
    this.active = true;

    soundFx.playReactorHum();
    this.setState('LISTENING');

    // 1. Initialize Microphone Audio Visualizer Analyser
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaStream = stream;

      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) {
        this.audioContext = new AudioCtx();
        const source = this.audioContext.createMediaStreamSource(stream);
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        source.connect(this.analyser);
        this.startAudioMetricsLoop();
      }
    } catch (err) {
      console.warn('Microphone stream error for analyser:', err);
    }

    // 2. Initialize Continuous Speech Recognition
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Live Voice requires Chrome, Edge, or a browser with SpeechRecognition support.');
      this.stop();
      return false;
    }

    this.initRecognition();
    return true;
  }

  /**
   * Stop live conversation mode
   */
  public stop() {
    this.active = false;
    this.interruptSpeech();

    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }

    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch {}
      this.recognition = null;
    }

    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    if (this.audioContext) {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }

    this.setState('OFF');
    soundFx.playClick();
  }

  /**
   * Immediately cut off assistant speech when user starts talking (Barge-In)
   */
  public interruptSpeech() {
    if (this.state === 'SPEAKING') {
      this.setState('INTERRUPTED');
      setTimeout(() => {
        if (this.active) this.setState('LISTENING');
      }, 200);
    }

    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }

    if (this.currentAudioElement) {
      try {
        this.currentAudioElement.pause();
        this.currentAudioElement = null;
      } catch {}
    }
  }

  private setState(newState: LiveIntercomState) {
    this.state = newState;
    this.callbacks?.onStateChange(newState);
  }

  private initRecognition() {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recog = new SpeechRecognition();
    recog.continuous = true;
    recog.interimResults = true;
    recog.lang = 'en-US';

    let finalAccumulated = '';

    recog.onresult = (event: any) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalAccumulated += ' ' + event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }

      // If user starts talking while JARVIS is speaking, execute Barge-In
      if (interim.trim() || finalAccumulated.trim()) {
        if (this.state === 'SPEAKING') {
          this.interruptSpeech();
        }
      }

      const currentLive = (finalAccumulated + ' ' + interim).trim();
      this.callbacks?.onTranscriptUpdate(currentLive, false);

      // Debounce silence detection (550ms after user stops vocalizing)
      if (this.silenceTimer) {
        clearTimeout(this.silenceTimer);
      }

      if (currentLive) {
        this.silenceTimer = setTimeout(async () => {
          if (!this.active) return;
          const phraseToSend = currentLive;
          finalAccumulated = '';

          this.callbacks?.onTranscriptUpdate(phraseToSend, true);
          this.setState('THINKING');
          soundFx.playClick();

          try {
            // Dispatch to J.A.R.V.I.S. LLM and speak response back
            const responseText = await this.callbacks?.onMessageComplete(phraseToSend);
            if (responseText && this.active) {
              await this.speak(responseText);
            } else {
              if (this.active) this.setState('LISTENING');
            }
          } catch (err) {
            console.error('Live voice processing error:', err);
            if (this.active) this.setState('LISTENING');
          }
        }, 650);
      }
    };

    recog.onerror = (event: any) => {
      if (event.error === 'no-speech') return;
      console.warn('SpeechRecognition warning:', event.error);
    };

    recog.onend = () => {
      // Auto-restart continuous listening if live mode is still enabled
      if (this.active) {
        try {
          recog.start();
        } catch {
          setTimeout(() => {
            if (this.active) this.initRecognition();
          }, 400);
        }
      }
    };

    try {
      recog.start();
      this.recognition = recog;
    } catch (err) {
      console.warn('Recognition start exception:', err);
    }
  }

  /**
   * Real-time audio frequency/energy monitor for pulsing the Arc Reactor
   */
  private startAudioMetricsLoop() {
    if (!this.analyser) return;

    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);

    const update = () => {
      if (!this.active || !this.analyser) return;

      this.analyser.getByteFrequencyData(dataArray);

      // Compute Root Mean Square (RMS) energy
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i] * dataArray[i];
      }
      const rms = Math.sqrt(sum / dataArray.length);
      const normalized = Math.min(1.0, Math.max(0.05, rms / 128.0));

      this.callbacks?.onVolumeChange?.(normalized);

      this.animFrameId = requestAnimationFrame(update);
    };

    this.animFrameId = requestAnimationFrame(update);
  }

  /**
   * Speak response back with natural J.A.R.V.I.S. voice
   */
  public async speak(text: string): Promise<void> {
    if (!this.active) return;
    this.setState('SPEAKING');

    // Clean text: strip markdown syntax, code blocks, emojis
    const clean = text
      .replace(/```[\s\S]*?```/g, 'Code block omitted for brevity, sir.')
      .replace(/[*#`_\[\]]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    return new Promise(async (resolve) => {
      if (!('speechSynthesis' in window)) {
        this.setState('LISTENING');
        resolve();
        return;
      }

      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.rate = 1.04;
      utterance.pitch = 0.88; // Deep, masculine, authoritative J.A.R.V.I.S. cadence

      let voices = window.speechSynthesis.getVoices();
      if (!voices || voices.length === 0) {
        await new Promise<void>((r) => {
          const onVoices = () => {
            window.speechSynthesis.removeEventListener('voiceschanged', onVoices);
            r();
          };
          window.speechSynthesis.addEventListener('voiceschanged', onVoices);
          setTimeout(() => {
            window.speechSynthesis.removeEventListener('voiceschanged', onVoices);
            r();
          }, 350);
        });
        voices = window.speechSynthesis.getVoices();
      }

      // Strict exclusion of all female voices across all engines
      const isFemale = (v: SpeechSynthesisVoice) =>
        /zira|heera|veena|jenny|female|woman|girl|catherine|hazel|susan|aria|sonia|neerja|swara|kalpana|ananya|aditi|sangeeta|samantha|victoria|karen|tessa|fiona|moira|google us english|google uk english female/i.test(
          v.name
        );

      const maleVoices = (voices || []).filter((v) => !isFemale(v));

      // Prioritize confirmed native Windows male (Microsoft David), UK British Male (George / UK English Male)
      let chosenVoice: SpeechSynthesisVoice | undefined =
        maleVoices.find((v) => /david/i.test(v.name)) ||
        maleVoices.find((v) => /george/i.test(v.name)) ||
        maleVoices.find((v) => /uk english male/i.test(v.name)) ||
        maleVoices.find((v) => /mark|richard|stefan|steffan|daniel|oliver|guy|brian/i.test(v.name)) ||
        maleVoices.find((v) => /ravi|prabhat|mohan|ayush/i.test(v.name)) ||
        maleVoices.find((v) => /male/i.test(v.name)) ||
        maleVoices.find((v) => !isFemale(v) && !/google us english/i.test(v.name));

      if (chosenVoice) {
        utterance.voice = chosenVoice;
      }

      utterance.onend = () => {
        if (this.active) {
          this.setState('LISTENING');
        }
        resolve();
      };

      utterance.onerror = () => {
        if (this.active) {
          this.setState('LISTENING');
        }
        resolve();
      };

      this.currentUtterance = utterance;
      window.speechSynthesis.speak(utterance);
    });
  }
}

export const liveDuplex = new LiveDuplexManager();
