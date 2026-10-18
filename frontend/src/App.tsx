import React, { useState, useEffect } from 'react';
import { HolographicCore } from './components/HolographicCore';
import { WaveformMonitor } from './components/WaveformMonitor';
import { ConversationFeed } from './components/ConversationFeed';
import type { DisplayMessage } from './components/ConversationFeed';
import { TelemetryPanel } from './components/TelemetryPanel';
import { ApprovalModal } from './components/ApprovalModal';
import { SettingsDrawer } from './components/SettingsDrawer';
import { api } from './services/api';
import type { ModelUsage, PendingApproval, VoicePreferences } from './services/api';
import { wsClient } from './services/websocket';

export const App: React.FC = () => {
  const [coreStatus, setCoreStatus] = useState<'IDLE' | 'PROCESSING' | 'SPEAKING' | 'ALERT'>('IDLE');
  const [wsStatus, setWsStatus] = useState<string>('OFFLINE');
  const [currentTime, setCurrentTime] = useState<string>('');
  const [activeModelRole, setActiveModelRole] = useState<string>('fast_chat');

  const [messages, setMessages] = useState<DisplayMessage[]>([
    {
      id: 'init-1',
      role: 'assistant',
      content: 'Good day, sir. All core systems are operational. Policy broker is active, neural model router is ready, and speech synthesis is calibrated.',
      timestamp: new Date().toLocaleTimeString(),
      model: 'meta/llama-3.1-8b-instruct',
      tokens: 42,
      latency_ms: 15,
    },
  ]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isAudioActive, setIsAudioActive] = useState<boolean>(false);

  const [usage, setUsage] = useState<ModelUsage | null>(null);
  const [voicePreferences, setVoicePreferences] = useState<VoicePreferences | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isApprovalModalOpen, setIsApprovalModalOpen] = useState<boolean>(false);

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
      const [usageData, prefsData, approvalsData] = await Promise.all([
        api.getModelUsage().catch(() => null),
        api.getVoicePreferences().catch(() => null),
        api.getPendingApprovals().catch(() => []),
      ]);
      if (usageData) setUsage(usageData);
      if (prefsData) setVoicePreferences(prefsData);
      if (approvalsData) setPendingApprovals(approvalsData);
    } catch (err) {
      console.warn('Initial data load error:', err);
    }
  };

  const handleSendMessage = async (text: string) => {
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
        tokens: res.total_tokens,
        latency_ms: res.latency_ms,
      };

      setMessages((prev) => [...prev, botMsg]);
      setCoreStatus('IDLE');

      // Refresh usage & approvals
      api.getModelUsage().then((u) => setUsage(u)).catch(() => null);
      api.getPendingApprovals().then((a) => setPendingApprovals(a)).catch(() => null);
    } catch (err: any) {
      const errorMsg: DisplayMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `System Warning: ${err.message || 'Failed to communicate with neural core.'}`,
        timestamp: new Date().toLocaleTimeString(),
        model: 'SYSTEM_FAULT',
      };
      setMessages((prev) => [...prev, errorMsg]);
      setCoreStatus('ALERT');
      setTimeout(() => setCoreStatus('IDLE'), 4000);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCoreClick = async () => {
    setCoreStatus('SPEAKING');
    setIsAudioActive(true);
    try {
      const prompt = "All primary diagnostics indicate optimal performance, sir. How may I be of service?";
      const res = await api.synthesizeSpeech(prompt);
      const audioUrl = `data:${res.content_type};base64,${res.audio_base64}`;
      const audio = new Audio(audioUrl);
      audio.onended = () => {
        setCoreStatus('IDLE');
        setIsAudioActive(false);
      };
      audio.onerror = () => {
        setCoreStatus('IDLE');
        setIsAudioActive(false);
      };
      await audio.play();
    } catch {
      setCoreStatus('IDLE');
      setIsAudioActive(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        padding: '16px 24px',
        gap: '16px',
        maxWidth: '1600px',
        margin: '0 auto',
      }}
    >
      {/* Top Holographic Navigation HUD */}
      <header
        className="glass-panel"
        style={{
          padding: '12px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div className="hud-corner-tl" />
        <div className="hud-corner-tr" />
        <div className="hud-corner-bl" />
        <div className="hud-corner-br" />

        {/* Branding */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '14px',
              height: '14px',
              borderRadius: '50%',
              background: '#00f0ff',
              boxShadow: '0 0 12px #00f0ff',
            }}
          />
          <div>
            <h1
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: '1.25rem',
                fontWeight: 900,
                letterSpacing: '0.15em',
                color: 'var(--cyan-primary)',
                textShadow: '0 0 10px rgba(0, 240, 255, 0.5)',
              }}
            >
              J.A.R.V.I.S.
            </h1>
            <p
              style={{
                fontSize: '0.65rem',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.08em',
              }}
            >
              PERSONAL AI OPERATING SYSTEM // MK-VII CORE
            </p>
          </div>
        </div>

        {/* Live Clock & Action Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.82rem',
              color: 'var(--cyan-primary)',
              letterSpacing: '0.08em',
            }}
          >
            {currentTime || '12:00:00 UTC+5:30'}
          </div>

          {/* Pending Approval Badge */}
          {pendingApprovals.length > 0 && (
            <button
              className="holo-btn holo-btn-danger"
              onClick={() => setIsApprovalModalOpen(true)}
              style={{ fontSize: '0.75rem', padding: '6px 12px' }}
            >
              ⚠ {pendingApprovals.length} APPROVAL REQUIRED
            </button>
          )}

          {/* Settings Trigger */}
          <button
            className="holo-btn"
            onClick={() => setIsSettingsOpen(true)}
            style={{ fontSize: '0.75rem', padding: '6px 12px' }}
          >
            PROTOCOLS ⚙
          </button>
        </div>
      </header>

      {/* Main Cockpit Layout */}
      <main
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: 'minmax(380px, 1fr) minmax(420px, 1.2fr)',
          gap: '20px',
        }}
      >
        {/* Left Column: Core Reactor, Waveform, and Telemetry */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Reactor & Waveform Stage */}
          <div
            className="glass-panel"
            style={{
              padding: '24px 16px 16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
            }}
          >
            <div className="hud-corner-tl" />
            <div className="hud-corner-tr" />
            <div className="hud-corner-bl" />
            <div className="hud-corner-br" />

            <div style={{ position: 'relative', width: '100%', textAlign: 'center' }}>
              <div
                style={{
                  fontSize: '0.7rem',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-muted)',
                  letterSpacing: '0.12em',
                  marginBottom: '12px',
                }}
              >
                TACTICAL ARC REACTOR VISUALIZER // CORE TELEMETRY
              </div>
              <HolographicCore
                status={coreStatus}
                pulseIntensity={isAudioActive ? 1.5 : 1.0}
                onClick={handleCoreClick}
              />
            </div>

            <div style={{ width: '100%', marginTop: '16px' }}>
              <WaveformMonitor isActive={isAudioActive || isLoading} />
            </div>
          </div>

          {/* Telemetry Status HUD */}
          <TelemetryPanel
            usage={usage}
            voicePreferences={voicePreferences}
            wsStatus={wsStatus}
            activeModelRole={activeModelRole}
          />
        </div>

        {/* Right Column: High-Throughput Dialogue Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <ConversationFeed
            messages={messages}
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            onAudioStart={() => {
              setCoreStatus('SPEAKING');
              setIsAudioActive(true);
            }}
            onAudioEnd={() => {
              setCoreStatus('IDLE');
              setIsAudioActive(false);
            }}
          />
        </div>
      </main>

      {/* Consequential Action Approval Modal */}
      {isApprovalModalOpen && (
        <ApprovalModal
          approvals={pendingApprovals}
          onDecided={() => {
            api.getPendingApprovals().then((a) => setPendingApprovals(a)).catch(() => null);
            setIsApprovalModalOpen(false);
          }}
          onClose={() => setIsApprovalModalOpen(false)}
        />
      )}

      {/* Settings Protocols Drawer */}
      <SettingsDrawer
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        voicePreferences={voicePreferences}
        onPreferencesUpdated={(newPrefs) => setVoicePreferences(newPrefs)}
        activeModelRole={activeModelRole}
        onModelRoleChanged={(role) => setActiveModelRole(role)}
      />
    </div>
  );
};

export default App;
