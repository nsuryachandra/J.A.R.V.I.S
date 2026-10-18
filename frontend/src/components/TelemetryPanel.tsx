import React from 'react';
import type { ModelUsage, VoicePreferences, SystemStatus } from '../services/api';

interface TelemetryPanelProps {
  usage?: ModelUsage | null;
  voicePreferences?: VoicePreferences | null;
  wsStatus: string;
  activeModelRole: string;
  systemStatus?: SystemStatus | null;
  onOpenSettings?: () => void;
}

export const TelemetryPanel: React.FC<TelemetryPanelProps> = ({
  usage,
  voicePreferences,
  wsStatus,
  activeModelRole,
  systemStatus,
  onOpenSettings,
}) => {
  const isVoiceLive = Boolean(systemStatus?.voice_configured ?? true);
  const isAiLive = Boolean(systemStatus?.ai_configured);

  const getAiProviderLabel = () => {
    if (systemStatus?.grok_configured) return 'GROK-2 [LIVE]';
    if (systemStatus?.groq_configured) return 'GROQ [LIVE]';
    if (systemStatus?.nvidia_configured) return 'NVIDIA NIM';
    if (systemStatus?.openai_configured) return 'OPENAI';
    return 'AUTONOMOUS [LOCAL]';
  };

  return (
    <div
      className="glass-panel"
      style={{
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
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
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid rgba(0, 240, 255, 0.2)',
          paddingBottom: '8px',
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '0.82rem',
            color: 'var(--cyan-primary)',
            letterSpacing: '0.1em',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span style={{ color: '#00ffd5' }}>◈</span> TELEMETRY // SYSTEM HUD
        </span>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            color: wsStatus === 'ONLINE' ? '#00ffd5' : '#94a3b8',
          }}
        >
          WS: {wsStatus}
        </span>
      </div>

      {/* Key Metric Gauges */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '8px',
        }}
      >
        {/* Voice Engine Status */}
        <div
          onClick={onOpenSettings}
          style={{
            background: 'rgba(4, 13, 29, 0.65)',
            border: isVoiceLive ? '1px solid rgba(0, 255, 136, 0.4)' : '1px solid rgba(255, 183, 0, 0.3)',
            borderRadius: '4px',
            padding: '8px 10px',
            cursor: 'pointer',
            transition: 'border 0.2s ease',
          }}
          title="Click to select voice profile or configure AI keys"
        >
          <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
            SPEECH SYNTHESIS
          </div>
          <div
            style={{
              fontSize: '0.78rem',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              color: isVoiceLive ? '#00ff88' : '#ffb700',
              marginTop: '3px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>{isVoiceLive ? '●' : '○'}</span>
            <span>NEURAL VOICE [STUDIO]</span>
          </div>
          <div style={{ fontSize: '0.62rem', color: '#00f0ff', marginTop: '2px' }}>
            {voicePreferences?.selected_profile_id || 'indian_english_male'} (Multi-Lingual)
          </div>
        </div>

        {/* Neural AI Core Status */}
        <div
          onClick={onOpenSettings}
          style={{
            background: 'rgba(4, 13, 29, 0.65)',
            border: isAiLive ? '1px solid rgba(0, 255, 136, 0.4)' : '1px solid rgba(0, 240, 255, 0.25)',
            borderRadius: '4px',
            padding: '8px 10px',
            cursor: 'pointer',
          }}
          title="Click to configure AI Model"
        >
          <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
            AI REASONING CORE
          </div>
          <div
            style={{
              fontSize: '0.78rem',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              color: isAiLive ? '#00ff88' : 'var(--cyan-primary)',
              marginTop: '3px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>{isAiLive ? '●' : '⚡'}</span>
            <span>{getAiProviderLabel()}</span>
          </div>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            {activeModelRole === 'auto' ? 'Llama 3.1 Suite' : activeModelRole}
          </div>
        </div>

        {/* Token Bandwidth */}
        <div
          style={{
            background: 'rgba(4, 13, 29, 0.65)',
            border: '1px solid rgba(0, 240, 255, 0.2)',
            borderRadius: '4px',
            padding: '8px 10px',
          }}
        >
          <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
            TOTAL TOKENS
          </div>
          <div
            style={{
              fontSize: '0.82rem',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              color: 'var(--text-main)',
              marginTop: '3px',
            }}
          >
            {usage?.total_tokens ?? 0}
          </div>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            {usage?.total_calls ?? 0} inference requests
          </div>
        </div>

        {/* Policy Broker */}
        <div
          style={{
            background: 'rgba(4, 13, 29, 0.65)',
            border: '1px solid rgba(0, 240, 255, 0.2)',
            borderRadius: '4px',
            padding: '8px 10px',
          }}
        >
          <div style={{ fontSize: '0.64rem', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
            POLICY BROKER
          </div>
          <div
            style={{
              fontSize: '0.78rem',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              color: '#00ffd5',
              marginTop: '3px',
            }}
          >
            ACTIVE [ENFORCED]
          </div>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            Audit Hash Chained
          </div>
        </div>
      </div>
    </div>
  );
};
