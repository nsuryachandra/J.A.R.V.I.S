import React, { useState, useEffect } from 'react';
import { HolographicCore } from './components/HolographicCore';
import { WaveformMonitor } from './components/WaveformMonitor';
import { ConversationFeed } from './components/ConversationFeed';
import type { DisplayMessage } from './components/ConversationFeed';
import { TelemetryPanel } from './components/TelemetryPanel';
import { ApprovalModal } from './components/ApprovalModal';
import { SettingsDrawer } from './components/SettingsDrawer';
import { api } from './services/api';
import type { ModelUsage, PendingApproval, VoicePreferences, SystemStatus } from './services/api';
import { wsClient } from './services/websocket';
import { soundFx } from './services/sound';
import { liveDuplex } from './services/liveDuplex';
import type { LiveIntercomState } from './services/liveDuplex';

export const App: React.FC = () => {
  const [coreStatus, setCoreStatus] = useState<'IDLE' | 'PROCESSING' | 'SPEAKING' | 'ALERT'>('IDLE');
  const [wsStatus, setWsStatus] = useState<string>('OFFLINE');
  const [currentTime, setCurrentTime] = useState<string>('');
  const [activeModelRole, setActiveModelRole] = useState<string>('auto');

  // Live Duplex Hands-Free Conversation Mode
  const [isLiveCallActive, setIsLiveCallActive] = useState<boolean>(false);
  const [liveIntercomState, setLiveIntercomState] = useState<LiveIntercomState>('OFF');
  const [liveTranscript, setLiveTranscript] = useState<string>('');
  const [liveMicVolume, setLiveMicVolume] = useState<number>(0.2);

  const [messages, setMessages] = useState<DisplayMessage[]>([
    {
      id: 'init-1',
      role: 'assistant',
      content: 'Good day, sir. All core systems are operational. Policy broker is active, neural model router is ready, and speech synthesis is calibrated.',
      timestamp: new Date().toLocaleTimeString(),
      model: 'qwen/qwen3.8-27b',
      tokens: 42,
      latency_ms: 15,
    },
  ]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isAudioActive, setIsAudioActive] = useState<boolean>(false);

  const [usage, setUsage] = useState<ModelUsage | null>(null);
  const [voicePreferences, setVoicePreferences] = useState<VoicePreferences | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isApprovalModalOpen, setIsApprovalModalOpen] = useState<boolean>(false);

  // Live Screen Vision Stream
  const [screenStream, setScreenStream] = useState<MediaStream | null>(null);
  const screenVideoRef = React.useRef<HTMLVideoElement | null>(null);

  const toggleLiveScreenStream = async () => {
    if (screenStream) {
      screenStream.getTracks().forEach((track) => track.stop());
      setScreenStream(null);
      soundFx.playClick();
    } else {
      try {
        soundFx.playReactorHum();
        const stream = await navigator.mediaDevices.getDisplayMedia({
          video: { frameRate: { ideal: 30 } },
        });
        setScreenStream(stream);

        stream.getVideoTracks()[0].onended = () => {
          setScreenStream(null);
        };

        handleSendMessage(
          'Sir, I have activated the continuous live workspace screen stream. I can now observe and inspect your screen in real time.'
        );
      } catch (err) {
        console.warn('Screen share cancelled:', err);
      }
    }
  };

  useEffect(() => {
    if (screenStream && screenVideoRef.current) {
      screenVideoRef.current.srcObject = screenStream;
    }
  }, [screenStream]);

  // Initialize clock, WebSocket, and data
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString('en-US', { hour12: false }) + ' UTC+5:30');
    }, 1000);

    wsClient.connect();
    const unsub = wsClient.subscribe((event) => {
      if (event.type === 'STATUS_CHANGE') {
        setWsStatus(event.status || 'OFFLINE');
      } else if (event.type === 'CORE_CONNECTED') {
        setWsStatus('ONLINE');
      }
    });

    loadInitialData();

    return () => {
      clearInterval(timer);
      unsub();
    };
  }, []);

  const loadInitialData = async () => {
    try {
      const [usageData, prefsData, approvalsData, statusData] = await Promise.all([
        api.getModelUsage().catch(() => null),
        api.getVoicePreferences().catch(() => null),
        api.getPendingApprovals().catch(() => []),
        api.getSystemStatus().catch(() => null),
      ]);
      if (usageData) setUsage(usageData);
      if (prefsData) setVoicePreferences(prefsData);
      if (approvalsData) setPendingApprovals(approvalsData);
      if (statusData) setSystemStatus(statusData);
    } catch (err) {
      console.warn('Initial data load error:', err);
    }
  };

  const handleSendMessage = async (text: string): Promise<string> => {
    const userMsg: DisplayMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setCoreStatus('PROCESSING');

    try {
      const chatHistory = messages
        .slice(-6)
        .concat(userMsg)
        .map((m) => ({ role: m.role, content: m.content }));

      const res = await api.sendChat(chatHistory, activeModelRole);

      const botMsg: DisplayMessage = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: res.content,
        timestamp: new Date().toLocaleTimeString(),
        model: res.model,
        provider: res.provider,
        tokens: res.total_tokens,
        latency_ms: res.latency_ms,
      };

      setMessages((prev) => [...prev, botMsg]);

      // Refresh telemetry usage
      api.getModelUsage().then((u) => setUsage(u)).catch(() => {});
      api.getSystemStatus().then((s) => setSystemStatus(s)).catch(() => {});

      return res.content;
    } catch (err: any) {
      const errorMsg: DisplayMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Subsystem Alert: Unable to complete inference command (${err.message || 'Network exception'}).`,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
      setCoreStatus('ALERT');
      setTimeout(() => setCoreStatus('IDLE'), 3000);
      return '';
    } finally {
      setIsLoading(false);
      if (coreStatus !== 'ALERT' && !isLiveCallActive) {
        setCoreStatus('IDLE');
      }
    }
  };

  const toggleLiveDuplex = async () => {
    if (isLiveCallActive) {
      liveDuplex.stop();
      setIsLiveCallActive(false);
      setLiveIntercomState('OFF');
      setLiveTranscript('');
      setCoreStatus('IDLE');
      setIsAudioActive(false);
    } else {
      const ok = await liveDuplex.start({
        onStateChange: (state) => {
          setLiveIntercomState(state);
          if (state === 'SPEAKING') {
            setCoreStatus('SPEAKING');
            setIsAudioActive(true);
          } else if (state === 'THINKING') {
            setCoreStatus('PROCESSING');
            setIsAudioActive(false);
          } else if (state === 'INTERRUPTED') {
            setCoreStatus('ALERT');
            setIsAudioActive(false);
          } else {
            setCoreStatus('IDLE');
            setIsAudioActive(false);
          }
        },
        onTranscriptUpdate: (text) => {
          setLiveTranscript(text);
        },
        onMessageComplete: async (finalText) => {
          setLiveTranscript('');
          return await handleSendMessage(finalText);
        },
        onVolumeChange: (vol) => {
          setLiveMicVolume(vol);
        },
      });

      if (ok) {
        setIsLiveCallActive(true);
      }
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        padding: '14px 20px',
        gap: '14px',
        boxSizing: 'border-box',
        overflow: 'hidden',
      }}
    >
      {/* Top Holographic Command Bar */}
      <header
        className="glass-panel"
        style={{
          padding: '10px 18px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <div className="hud-corner-tl" />
        <div className="hud-corner-tr" />

        {/* System Title & Arc Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '16px',
              height: '16px',
              borderRadius: '50%',
              backgroundColor: '#00f0ff',
              boxShadow: '0 0 10px #00f0ff',
              animation: 'holoPulse 2s infinite',
            }}
          />
          <div>
            <div
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: '1.05rem',
                fontWeight: 800,
                color: 'var(--cyan-primary)',
                letterSpacing: '0.14em',
                lineHeight: 1.1,
              }}
            >
              J.A.R.V.I.S. — HOLOGRAPHIC COMMAND CONSOLE
            </div>
            <div
              style={{
                fontSize: '0.66rem',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-muted)',
                letterSpacing: '0.08em',
              }}
            >
              STARK INDUSTRIES // MARK VII QUANTUM KERNEL
            </div>
          </div>
        </div>

        {/* Live Provider Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Open-Source Neural Voice Status */}
          <div
            onClick={() => {
              soundFx.playClick();
              setIsSettingsOpen(true);
            }}
            style={{
              background: 'rgba(0, 255, 136, 0.12)',
              border: '1px solid rgba(0, 255, 136, 0.5)',
              color: '#00ff88',
              borderRadius: '4px',
              padding: '4px 10px',
              fontSize: '0.7rem',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Click to view/change voice profile"
          >
            <span>●</span>
            <span>VOICE: OPEN-SOURCE HD</span>
          </div>

          {/* AI Core Status */}
          <div
            onClick={() => {
              soundFx.playClick();
              setIsSettingsOpen(true);
            }}
            style={{
              background: systemStatus?.ai_configured
                ? 'rgba(0, 255, 213, 0.12)'
                : 'rgba(0, 240, 255, 0.08)',
              border: systemStatus?.ai_configured
                ? '1px solid rgba(0, 255, 213, 0.5)'
                : '1px solid rgba(0, 240, 255, 0.3)',
              color: systemStatus?.ai_configured ? '#00ffd5' : '#38bdf8',
              borderRadius: '4px',
              padding: '4px 10px',
              fontSize: '0.7rem',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title="Click to view/configure Neural AI Model"
          >
            <span>⚡</span>
            <span>
              {systemStatus?.ai_configured
                ? `AI: ${systemStatus.ai_provider.toUpperCase()}`
                : 'AI: AUTO (LLAMA 3.1)'}
            </span>
          </div>
        </div>

        {/* Global Controls & Telemetry */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Live Duplex Voice Call Toggle Button */}
          <button
            onClick={toggleLiveDuplex}
            style={{
              background: isLiveCallActive
                ? 'rgba(0, 255, 213, 0.22)'
                : 'rgba(0, 240, 255, 0.1)',
              border: isLiveCallActive
                ? '1px solid #00ffd5'
                : '1px solid rgba(0, 240, 255, 0.4)',
              color: isLiveCallActive ? '#00ffd5' : '#00f0ff',
              borderRadius: '4px',
              padding: '6px 14px',
              fontSize: '0.74rem',
              fontFamily: 'var(--font-display)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: isLiveCallActive
                ? '0 0 16px rgba(0, 255, 213, 0.6)'
                : 'none',
              animation: isLiveCallActive ? 'holoPulse 1.4s infinite' : 'none',
              transition: 'all 0.2s ease',
            }}
            title="Start continuous hands-free Live Duplex Voice conversation with J.A.R.V.I.S."
          >
            <span>{isLiveCallActive ? '🟢' : '⚡'}</span>
            <span>
              {isLiveCallActive
                ? `LIVE CALL: ${liveIntercomState}`
                : 'START LIVE SPEAKING'}
            </span>
          </button>

          <button
            onClick={toggleLiveScreenStream}
            style={{
              background: screenStream
                ? 'rgba(0, 240, 255, 0.22)'
                : 'rgba(0, 240, 255, 0.08)',
              border: `1px solid ${
                screenStream ? '#00f0ff' : 'rgba(0, 240, 255, 0.35)'
              }`,
              color: screenStream ? '#00f0ff' : 'var(--text-cyan)',
              borderRadius: '4px',
              padding: '6px 14px',
              fontSize: '0.74rem',
              fontFamily: 'var(--font-display)',
              fontWeight: 600,
              letterSpacing: '0.06em',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: screenStream
                ? '0 0 16px rgba(0, 240, 255, 0.6)'
                : 'none',
              animation: screenStream ? 'holoPulse 2s infinite' : 'none',
              transition: 'all 0.2s ease',
            }}
            title="Continuous real-time screen sharing and visual monitoring for J.A.R.V.I.S."
          >
            <span>{screenStream ? '🟢' : '👁️'}</span>
            <span>
              {screenStream ? 'LIVE SCREEN STREAMING' : 'SHARE LIVE SCREEN'}
            </span>
          </button>

          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.76rem',
              color: 'var(--text-cyan)',
              letterSpacing: '0.08em',
            }}
          >
            {currentTime}
          </div>

          {pendingApprovals.length > 0 && (
            <button
              onClick={() => {
                soundFx.playClick();
                setIsApprovalModalOpen(true);
              }}
              style={{
                background: 'rgba(255, 0, 85, 0.15)',
                border: '1px solid #ff0055',
                color: '#ff0055',
                borderRadius: '4px',
                padding: '6px 12px',
                fontSize: '0.74rem',
                fontFamily: 'var(--font-display)',
                cursor: 'pointer',
                boxShadow: '0 0 10px rgba(255, 0, 85, 0.4)',
                animation: 'holoPulse 1.2s infinite',
              }}
            >
              ⚠ APPROVAL REQUIRED ({pendingApprovals.length})
            </button>
          )}

          <button
            className="holo-btn"
            onClick={() => {
              soundFx.playClick();
              setIsSettingsOpen(true);
            }}
            style={{ padding: '6px 14px', fontSize: '0.74rem' }}
          >
            ⚡ SYSTEM CONFIG
          </button>
        </div>
      </header>

      {/* Main Holographic Workspace Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(340px, 420px) 1fr',
          gap: '14px',
          flex: 1,
          minHeight: 0,
        }}
      >
        {/* Left Column: Arc Reactor Core & Telemetry */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
            minHeight: 0,
          }}
        >
          {/* Tactical Arc Reactor Visualizer Card */}
          <div
            className="glass-panel"
            style={{
              flex: 1,
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              alignItems: 'center',
              position: 'relative',
            }}
          >
            <div className="hud-corner-tl" />
            <div className="hud-corner-tr" />
            <div className="hud-corner-bl" />
            <div className="hud-corner-br" />

            <div
              style={{
                width: '100%',
                display: 'flex',
                justifyContent: 'space-between',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.68rem',
                color: 'var(--text-muted)',
                letterSpacing: '0.08em',
              }}
            >
              <span>TACTICAL ARC REACTOR // CORE TELEMETRY</span>
              <span style={{ color: isLiveCallActive ? '#00ffd5' : '#00f0ff' }}>
                {isLiveCallActive ? '● LIVE INTERCOM ACTIVE' : 'MK-VII ACTIVE'}
              </span>
            </div>

            {screenStream && (
              <div
                style={{
                  width: '100%',
                  marginTop: '10px',
                  marginBottom: '10px',
                  borderRadius: '6px',
                  overflow: 'hidden',
                  border: '1px solid rgba(0, 240, 255, 0.45)',
                  background: 'rgba(0, 8, 18, 0.85)',
                  position: 'relative',
                  boxShadow: '0 0 15px rgba(0, 240, 255, 0.25)',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: '6px',
                    left: '8px',
                    right: '8px',
                    zIndex: 2,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: '0.62rem',
                    fontFamily: 'var(--font-mono)',
                    color: '#00f0ff',
                    background: 'rgba(0, 10, 22, 0.85)',
                    padding: '3px 8px',
                    borderRadius: '3px',
                    border: '1px solid rgba(0, 240, 255, 0.3)',
                  }}
                >
                  <span
                    style={{
                      color: '#00ffd5',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <span
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: '#00ffd5',
                        display: 'inline-block',
                      }}
                    />
                    LIVE OPTICAL HUD FEED
                  </span>
                  <button
                    onClick={toggleLiveScreenStream}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#ff0055',
                      cursor: 'pointer',
                      fontSize: '0.62rem',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    DISCONNECT [✕]
                  </button>
                </div>
                <video
                  ref={screenVideoRef}
                  autoPlay
                  playsInline
                  muted
                  style={{
                    width: '100%',
                    height: '140px',
                    objectFit: 'contain',
                    display: 'block',
                    background: '#020710',
                  }}
                />
              </div>
            )}

            <HolographicCore
              status={coreStatus}
              pulseIntensity={
                isLiveCallActive
                  ? Math.min(1.6, 1.0 + liveMicVolume * 0.8)
                  : isAudioActive
                  ? 1.5
                  : 1.0
              }
              onClick={toggleLiveDuplex}
            />

            <div style={{ width: '100%' }}>
              {isLiveCallActive && (
                <div
                  style={{
                    background: 'rgba(0, 255, 213, 0.08)',
                    border: '1px solid rgba(0, 255, 213, 0.35)',
                    borderRadius: '4px',
                    padding: '8px 12px',
                    marginBottom: '8px',
                    boxSizing: 'border-box',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '0.66rem',
                      fontFamily: 'var(--font-mono)',
                      color: '#00ffd5',
                      marginBottom: '3px',
                    }}
                  >
                    <span>● LIVE CONVERSATION: {liveIntercomState}</span>
                    <span>BARGE-IN READY</span>
                  </div>
                  <div
                    style={{
                      fontSize: '0.78rem',
                      color: '#ffffff',
                      fontStyle: 'italic',
                      minHeight: '1.2em',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {liveTranscript
                      ? `Hearing: "${liveTranscript}"`
                      : 'Listening continuously... speak naturally, sir.'}
                  </div>
                </div>
              )}

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.68rem',
                  color: 'var(--text-muted)',
                  marginBottom: '6px',
                }}
              >
                <span>VOICE FREQUENCY SPECTRUM // 44.1 kHz</span>
                <span
                  style={{
                    color:
                      isLiveCallActive || isAudioActive
                        ? '#00ffd5'
                        : 'var(--text-muted)',
                  }}
                >
                  {isLiveCallActive
                    ? `LIVE ${liveIntercomState}`
                    : isAudioActive
                    ? 'SYNTHESIZING'
                    : 'STANDBY'}
                </span>
              </div>
              <WaveformMonitor
                isActive={
                  isLiveCallActive ||
                  isAudioActive ||
                  coreStatus === 'SPEAKING' ||
                  isLoading
                }
                amplitude={
                  isLiveCallActive
                    ? Math.max(0.35, liveMicVolume)
                    : isAudioActive
                    ? 0.9
                    : 0.25
                }
              />
            </div>
          </div>

          {/* Lower Left Telemetry HUD */}
          <TelemetryPanel
            usage={usage}
            voicePreferences={voicePreferences}
            wsStatus={wsStatus}
            activeModelRole={activeModelRole}
            systemStatus={systemStatus}
            onOpenSettings={() => {
              soundFx.playClick();
              setIsSettingsOpen(true);
            }}
          />
        </div>

        {/* Right Column: Neural Dialogue Feed */}
        <div style={{ minHeight: 0, height: '100%' }}>
          <ConversationFeed
            messages={messages}
            onSendMessage={async (text) => {
              await handleSendMessage(text);
            }}
            isLoading={isLoading}
            onAudioStart={() => {
              setIsAudioActive(true);
              setCoreStatus('SPEAKING');
            }}
            onAudioEnd={() => {
              setIsAudioActive(false);
              setCoreStatus('IDLE');
            }}
            selectedProfileId={voicePreferences?.selected_profile_id || 'indian_english_male'}
            onToggleLiveCall={toggleLiveDuplex}
            isLiveCallActive={isLiveCallActive}
          />
        </div>
      </div>

      {/* Settings Drawer */}
      <SettingsDrawer
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        voicePreferences={voicePreferences}
        onPreferencesUpdated={(newPrefs) => setVoicePreferences(newPrefs)}
        activeModelRole={activeModelRole}
        onModelRoleChanged={(role) => setActiveModelRole(role)}
        systemStatus={systemStatus}
        onStatusUpdated={(s) => setSystemStatus(s)}
      />

      {/* Consequential Action Approval Modal */}
      {isApprovalModalOpen && pendingApprovals.length > 0 && (
        <ApprovalModal
          approvals={pendingApprovals}
          onDecided={loadInitialData}
          onClose={() => setIsApprovalModalOpen(false)}
        />
      )}
    </div>
  );
};

export default App;
