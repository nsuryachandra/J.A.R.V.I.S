import React, { useState, useRef, useEffect } from 'react';
import type { LLMMessage } from '../services/api';
import { api } from '../services/api';
import { soundFx } from '../services/sound';

export interface DisplayMessage extends LLMMessage {
  id: string;
  timestamp: string;
  model?: string;
  provider?: string;
  tokens?: number;
  latency_ms?: number;
}

interface ConversationFeedProps {
  messages: DisplayMessage[];
  onSendMessage: (text: string) => Promise<void>;
  isLoading: boolean;
  onAudioStart?: () => void;
  onAudioEnd?: () => void;
  selectedProfileId?: string;
  onToggleLiveCall?: () => void;
  isLiveCallActive?: boolean;
}

export const ConversationFeed: React.FC<ConversationFeedProps> = ({
  messages,
  onSendMessage,
  isLoading,
  onAudioStart,
  onAudioEnd,
  selectedProfileId: _selectedProfileId = 'indian_english_male',
  onToggleLiveCall,
  isLiveCallActive = false,
}) => {
  const [inputText, setInputText] = useState('');
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [autoSpeak, setAutoSpeak] = useState<boolean>(true);
  const [isListening, setIsListening] = useState<boolean>(false);
  const recognitionRef = useRef<any>(null);
  const feedEndRef = useRef<HTMLDivElement | null>(null);
  const prevMessagesCountRef = useRef<number>(messages.length);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Auto-speak new assistant messages when autoSpeak is enabled
  useEffect(() => {
    if (messages.length > prevMessagesCountRef.current) {
      const latest = messages[messages.length - 1];
      if (latest.role === 'assistant' && autoSpeak && !isLoading) {
        soundFx.playResponse();
        handleSpeak(latest);
      }
    }
    prevMessagesCountRef.current = messages.length;
  }, [messages, autoSpeak, isLoading]);

  const handleCaptureScreen = async () => {
    try {
      soundFx.playClick();
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const video = document.createElement('video');
      video.srcObject = stream;
      await video.play();

      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 1280;
      canvas.height = video.videoHeight || 720;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      }
      const b64 = canvas.toDataURL('image/jpeg', 0.85);

      // Cleanly stop capture stream
      stream.getTracks().forEach((track) => track.stop());

      onSendMessage('Sir, I have captured my workspace screen display. Please inspect what is on my screen and assist me.');
      api.inspectScreenImage(b64).catch(() => {});
    } catch (err: any) {
      console.warn('Screen capture cancelled or unavailable:', err);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;
    soundFx.playClick();
    const text = inputText;
    setInputText('');
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    }
    onSendMessage(text);
  };

  /**
   * Browser Speech Synthesis calibrated for authentic British J.A.R.V.I.S. persona
   */
  const playBrowserSpeech = (text: string) => {
    if (!('speechSynthesis' in window)) {
      setPlayingId(null);
      onAudioEnd?.();
      return;
    }
    window.speechSynthesis.cancel();
    const cleanText = text
      .replace(/```[\s\S]*?```/g, 'Code block omitted for voice, sir.')
      .replace(/[*#`_\[\]]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.04;
    utterance.pitch = 0.88; // Deep, masculine, authoritative J.A.R.V.I.S. cadence

    let voices = window.speechSynthesis.getVoices();
    const isFemale = (v: SpeechSynthesisVoice) =>
      /zira|heera|veena|jenny|female|woman|girl|catherine|hazel|susan|aria|sonia|neerja|swara|kalpana|ananya|aditi|sangeeta|samantha|victoria|karen|tessa|fiona|moira|google us english|google uk english female/i.test(
        v.name
      );

    const maleVoices = (voices || []).filter((v) => !isFemale(v));

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
      setPlayingId(null);
      onAudioEnd?.();
    };
    utterance.onerror = () => {
      setPlayingId(null);
      onAudioEnd?.();
    };

    window.speechSynthesis.speak(utterance);
  };

  const handleSpeak = async (msg: DisplayMessage) => {
    try {
      setPlayingId(msg.id);
      onAudioStart?.();
      playBrowserSpeech(msg.content);
    } catch (err) {
      console.error('Audio playback error:', err);
      setPlayingId(null);
      onAudioEnd?.();
    }
  };

  const toggleListen = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech Recognition is not supported by your browser. Please use Chrome or Edge.');
      return;
    }

    soundFx.playClick();

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((res: any) => res[0].transcript)
          .join('');
        setInputText(transcript);
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  return (
    <div
      className="glass-panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: '480px',
        position: 'relative',
      }}
    >
      <div className="hud-corner-tl" />
      <div className="hud-corner-tr" />
      <div className="hud-corner-bl" />
      <div className="hud-corner-br" />

      {/* Feed Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 16px',
          borderBottom: '1px solid rgba(0, 240, 255, 0.2)',
          background: 'rgba(4, 13, 29, 0.65)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: '#00ffd5',
              boxShadow: '0 0 8px #00ffd5',
              display: 'inline-block',
            }}
          />
          <span
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '0.85rem',
              color: 'var(--cyan-primary)',
              letterSpacing: '0.12em',
            }}
          >
            NEURAL DIALOGUE FEED
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => {
              soundFx.playClick();
              setAutoSpeak(!autoSpeak);
            }}
            style={{
              background: autoSpeak ? 'rgba(0, 255, 213, 0.15)' : 'rgba(255, 255, 255, 0.05)',
              border: autoSpeak ? '1px solid #00ffd5' : '1px solid rgba(255, 255, 255, 0.2)',
              color: autoSpeak ? '#00ffd5' : 'var(--text-muted)',
              borderRadius: '4px',
              padding: '4px 10px',
              fontSize: '0.72rem',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}
            title="Toggle automatic speech readout of J.A.R.V.I.S. responses"
          >
            {autoSpeak ? '🔊 VOICE: ON' : '🔈 VOICE: OFF'}
          </button>
          <span
            style={{
              fontSize: '0.68rem',
              fontFamily: 'var(--font-mono)',
              color: '#38bdf8',
              letterSpacing: '0.08em',
            }}
          >
            AI ROUTED // LIVE
          </span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          const isPlaying = playingId === msg.id;

          return (
            <div
              key={msg.id}
              style={{
                alignSelf: isUser ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}
            >
              {/* Speaker Metadata */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.68rem',
                  fontFamily: 'var(--font-mono)',
                  color: isUser ? '#ffb700' : 'var(--cyan-primary)',
                  justifyContent: isUser ? 'flex-end' : 'flex-start',
                  letterSpacing: '0.06em',
                }}
              >
                <span>{isUser ? 'USER // COMMANDER' : '◈ J.A.R.V.I.S. // CORE'}</span>
                <span style={{ color: 'var(--text-muted)' }}>• {msg.timestamp}</span>
                {msg.model && (
                  <span
                    style={{
                      background: 'rgba(0, 240, 255, 0.12)',
                      padding: '1px 6px',
                      borderRadius: '3px',
                      color: '#00ffd5',
                    }}
                  >
                    ⚡ {msg.model.split('/').pop()}
                  </span>
                )}
              </div>

              {/* Message Bubble Card */}
              <div
                style={{
                  background: isUser ? 'rgba(15, 23, 42, 0.85)' : 'rgba(4, 18, 42, 0.88)',
                  border: isUser ? '1px solid rgba(255, 183, 0, 0.4)' : '1px solid rgba(0, 240, 255, 0.4)',
                  borderLeft: !isUser ? '3px solid var(--cyan-primary)' : undefined,
                  borderRight: isUser ? '3px solid #ffb700' : undefined,
                  borderRadius: isUser ? '8px 2px 8px 8px' : '2px 8px 8px 8px',
                  padding: '12px 14px',
                  color: 'var(--text-main)',
                  fontSize: '0.88rem',
                  lineHeight: '1.5',
                  boxShadow: isUser
                    ? '0 2px 12px rgba(255, 183, 0, 0.1)'
                    : '0 2px 14px rgba(0, 240, 255, 0.15)',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {msg.content}
              </div>

              {/* Action Toolbar for Assistant */}
              {!isUser && (
                <div style={{ display: 'flex', gap: '8px', marginTop: '2px' }}>
                  <button
                    onClick={() => {
                      soundFx.playClick();
                      handleSpeak(msg);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: isPlaying ? '#00ffd5' : 'var(--text-dim)',
                      fontSize: '0.72rem',
                      fontFamily: 'var(--font-mono)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: 0,
                    }}
                  >
                    {isPlaying ? '◼ STOP SPEAKING' : '▶ SPEAK'}
                  </button>
                  {msg.latency_ms && (
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      {msg.latency_ms}ms
                    </span>
                  )}
                  {msg.tokens && (
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      {msg.tokens} tokens
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {isLoading && (
          <div
            style={{
              alignSelf: 'flex-start',
              background: 'rgba(4, 18, 42, 0.75)',
              border: '1px solid rgba(0, 240, 255, 0.3)',
              borderRadius: '4px',
              padding: '10px 14px',
              color: 'var(--cyan-primary)',
              fontSize: '0.8rem',
              fontFamily: 'var(--font-mono)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: 'var(--cyan-primary)',
                animation: 'holoPulse 0.8s infinite',
              }}
            />
            NEURAL REASONING IN PROGRESS...
          </div>
        )}

        <div ref={feedEndRef} />
      </div>

      {/* Suggested Quick Prompt Chips */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          padding: '6px 16px',
          overflowX: 'auto',
          borderTop: '1px solid rgba(0, 240, 255, 0.1)',
          background: 'rgba(3, 7, 18, 0.5)',
        }}
      >
        {[
          'Hi sir, ela unnaru?',
          'Check CPU & RAM',
          'Open Chrome',
          'Open VS Code',
          'Write a production Python script',
          'Diagnostics & Core Status',
        ].map((prompt) => (
          <button
            key={prompt}
            onClick={() => {
              soundFx.playClick();
              onSendMessage(prompt);
            }}
            disabled={isLoading}
            style={{
              background: 'rgba(0, 240, 255, 0.06)',
              border: '1px solid rgba(0, 240, 255, 0.2)',
              borderRadius: '12px',
              color: 'var(--text-dim)',
              fontSize: '0.72rem',
              fontFamily: 'var(--font-mono)',
              padding: '4px 10px',
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#00ffd5';
              e.currentTarget.style.borderColor = '#00ffd5';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--text-dim)';
              e.currentTarget.style.borderColor = 'rgba(0, 240, 255, 0.2)';
            }}
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Input Box & Voice Controls */}
      <form
        onSubmit={handleSubmit}
        style={{
          display: 'flex',
          gap: '8px',
          padding: '12px 16px',
          borderTop: '1px solid rgba(0, 240, 255, 0.2)',
          background: 'rgba(4, 13, 29, 0.8)',
        }}
      >
        {/* Microphone Button */}
        <button
          type="button"
          onClick={toggleListen}
          style={{
            background: isListening ? '#ff0055' : 'rgba(0, 240, 255, 0.12)',
            border: isListening ? '1px solid #ff0055' : '1px solid rgba(0, 240, 255, 0.4)',
            color: isListening ? '#ffffff' : 'var(--cyan-primary)',
            borderRadius: '4px',
            padding: '8px 12px',
            cursor: 'pointer',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.78rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            transition: 'all 0.2s ease',
            boxShadow: isListening ? '0 0 12px #ff0055' : 'none',
          }}
          title="Click to speak hands-free via microphone"
        >
          {isListening ? '🔴 LISTENING' : '🎙️ MIC'}
        </button>

        {/* Screen Capture & Inspection Button */}
        <button
          type="button"
          onClick={handleCaptureScreen}
          disabled={isLoading}
          style={{
            background: 'rgba(0, 255, 213, 0.12)',
            border: '1px solid rgba(0, 255, 213, 0.4)',
            color: '#00ffd5',
            borderRadius: '4px',
            padding: '8px 12px',
            cursor: 'pointer',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.78rem',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            transition: 'all 0.2s ease',
          }}
          title="Capture current desktop/workspace display for J.A.R.V.I.S. inspection"
        >
          📸 SCREEN
        </button>

        {/* Live Continuous Duplex Call Toggle Button */}
        {onToggleLiveCall && (
          <button
            type="button"
            onClick={onToggleLiveCall}
            style={{
              background: isLiveCallActive
                ? 'rgba(0, 255, 213, 0.25)'
                : 'rgba(0, 240, 255, 0.12)',
              border: isLiveCallActive
                ? '1px solid #00ffd5'
                : '1px solid rgba(0, 240, 255, 0.4)',
              color: isLiveCallActive ? '#00ffd5' : 'var(--cyan-primary)',
              borderRadius: '4px',
              padding: '8px 12px',
              cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.78rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s ease',
              boxShadow: isLiveCallActive ? '0 0 12px rgba(0, 255, 213, 0.6)' : 'none',
              animation: isLiveCallActive ? 'holoPulse 1.2s infinite' : 'none',
            }}
            title="Toggle Live Hands-Free Duplex Voice Call (No typing, speak continuously)"
          >
            {isLiveCallActive ? '🟢 LIVE CALL ON' : '⚡ LIVE CALL'}
          </button>
        )}

        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={
            isLiveCallActive
              ? '🟢 Live call active: listening continuously, speak freely...'
              : isListening
              ? 'Listening to voice input...'
              : 'Command J.A.R.V.I.S. (speak or type)...'
          }
          disabled={isLoading}
          style={{
            flex: 1,
            background: 'var(--bg-input)',
            border: isLiveCallActive
              ? '1px solid #00ffd5'
              : isListening
              ? '1px solid #ff0055'
              : '1px solid rgba(0, 240, 255, 0.3)',
            borderRadius: '4px',
            padding: '10px 14px',
            color: 'var(--text-main)',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.85rem',
            outline: 'none',
            boxShadow: isLiveCallActive ? '0 0 8px rgba(0, 255, 213, 0.25)' : 'none',
          }}
        />

        <button
          type="submit"
          className="holo-btn"
          disabled={isLoading || !inputText.trim()}
          style={{
            padding: '8px 20px',
            fontSize: '0.78rem',
          }}
        >
          EXECUTE
        </button>
      </form>
    </div>
  );
};
