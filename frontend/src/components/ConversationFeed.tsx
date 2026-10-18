import React, { useState, useRef, useEffect } from 'react';
import type { LLMMessage } from '../services/api';
import { api } from '../services/api';

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
}

export const ConversationFeed: React.FC<ConversationFeedProps> = ({
  messages,
  onSendMessage,
  isLoading,
  onAudioStart,
  onAudioEnd,
}) => {
  const [inputText, setInputText] = useState('');
  const [playingId, setPlayingId] = useState<string | null>(null);
  const feedEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;
    const text = inputText;
    setInputText('');
    onSendMessage(text);
  };

  const handleSpeak = async (msg: DisplayMessage) => {
    try {
      setPlayingId(msg.id);
      onAudioStart?.();
      const res = await api.synthesizeSpeech(msg.content);
      const audioUrl = `data:${res.content_type};base64,${res.audio_base64}`;
      const audio = new Audio(audioUrl);
      audio.onended = () => {
        setPlayingId(null);
        onAudioEnd?.();
      };
      audio.onerror = () => {
        setPlayingId(null);
        onAudioEnd?.();
      };
      await audio.play();
    } catch (err) {
      console.error('Audio playback error:', err);
      setPlayingId(null);
      onAudioEnd?.();
    }
  };

  const quickPrompts = [
    'Diagnostics & Core Status',
    'Fasting Routine Status',
    'Pending Tasks & Schedule',
    'Architecture Review',
  ];

  return (
    <div
      className="glass-panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        maxHeight: '620px',
        position: 'relative',
      }}
    >
      <div className="hud-corner-tl" />
      <div className="hud-corner-tr" />
      <div className="hud-corner-bl" />
      <div className="hud-corner-br" />

      {/* Header */}
      <div
        style={{
          padding: '12px 18px',
          borderBottom: '1px solid rgba(0, 240, 255, 0.2)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: '#00ffd5',
              boxShadow: '0 0 8px #00ffd5',
            }}
          />
          <h2
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '0.9rem',
              letterSpacing: '0.08em',
              color: 'var(--cyan-primary)',
              textTransform: 'uppercase',
            }}
          >
            Neural Dialogue Feed
          </h2>
        </div>
        <span className="holo-badge">ENCRYPTED // CHAT STREAM</span>
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
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  justifyContent: isUser ? 'flex-end' : 'flex-start',
                  fontSize: '0.7rem',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                }}
              >
                <span>{isUser ? 'COMMANDER' : 'J.A.R.V.I.S.'}</span>
                <span>•</span>
                <span>{msg.timestamp}</span>
              </div>

              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: isUser ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                  background: isUser ? 'rgba(0, 112, 243, 0.25)' : 'rgba(6, 22, 45, 0.75)',
                  border: isUser ? '1px solid rgba(0, 112, 243, 0.5)' : '1px solid rgba(0, 240, 255, 0.3)',
                  boxShadow: isUser
                    ? '0 0 15px rgba(0, 112, 243, 0.2)'
                    : '0 0 15px rgba(0, 240, 255, 0.1)',
                  color: 'var(--text-main)',
                  fontSize: '0.9rem',
                  lineHeight: '1.5',
                  wordBreak: 'break-word',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {msg.content}
              </div>

              {!isUser && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    fontSize: '0.7rem',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-cyan)',
                    marginTop: '2px',
                  }}
                >
                  {msg.model && <span>{msg.model}</span>}
                  {msg.tokens && <span>{msg.tokens} tokens</span>}
                  {msg.latency_ms && <span>{msg.latency_ms}ms</span>}
                  <button
                    onClick={() => handleSpeak(msg)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: playingId === msg.id ? '#00ffd5' : 'var(--cyan-primary)',
                      cursor: 'pointer',
                      fontSize: '0.72rem',
                      fontFamily: 'var(--font-display)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                    title="Play voice audio"
                  >
                    {playingId === msg.id ? '🔊 SPEAKING...' : '▶ AUDIO'}
                  </button>
                </div>
              )}
            </div>
          );
        })}

        {isLoading && (
          <div
            style={{
              alignSelf: 'flex-start',
              padding: '10px 16px',
              borderRadius: '12px',
              background: 'rgba(6, 22, 45, 0.75)',
              border: '1px solid rgba(0, 240, 255, 0.3)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8rem',
              color: 'var(--cyan-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span style={{ animation: 'spinClockwise 1s linear infinite' }}>⚙</span>
            <span>J.A.R.V.I.S. is synthesizing response...</span>
          </div>
        )}

        <div ref={feedEndRef} />
      </div>

      {/* Quick Prompts */}
      <div
        style={{
          padding: '6px 14px',
          display: 'flex',
          gap: '8px',
          overflowX: 'auto',
          borderTop: '1px solid rgba(0, 240, 255, 0.1)',
        }}
      >
        {quickPrompts.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSendMessage(prompt)}
            disabled={isLoading}
            style={{
              whiteSpace: 'nowrap',
              background: 'rgba(0, 240, 255, 0.05)',
              border: '1px solid rgba(0, 240, 255, 0.25)',
              color: 'var(--text-dim)',
              fontSize: '0.72rem',
              padding: '4px 10px',
              borderRadius: '14px',
              cursor: 'pointer',
              transition: 'var(--transition-fast)',
            }}
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Input Form */}
      <form
        onSubmit={handleSubmit}
        style={{
          padding: '12px 16px',
          borderTop: '1px solid rgba(0, 240, 255, 0.2)',
          display: 'flex',
          gap: '10px',
        }}
      >
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Command J.A.R.V.I.S. (e.g., 'What is scheduled tomorrow?')"
          disabled={isLoading}
          style={{
            flex: 1,
            background: 'var(--bg-input)',
            border: '1px solid rgba(0, 240, 255, 0.3)',
            borderRadius: '4px',
            padding: '10px 14px',
            color: 'var(--text-main)',
            fontSize: '0.9rem',
            outline: 'none',
          }}
        />
        <button type="submit" className="holo-btn" disabled={isLoading || !inputText.trim()}>
          EXECUTE
        </button>
      </form>
    </div>
  );
};
