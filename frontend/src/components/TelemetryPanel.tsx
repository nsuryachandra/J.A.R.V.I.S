import React from 'react';
import type { ModelUsage, VoicePreferences } from '../services/api';

interface TelemetryPanelProps {
  usage?: ModelUsage | null;
  voicePreferences?: VoicePreferences | null;
  wsStatus: string;
  activeModelRole: string;
}

export const TelemetryPanel: React.FC<TelemetryPanelProps> = ({
  usage,
  voicePreferences,
  wsStatus,
  activeModelRole,
}) => {
  return (
    <div
      className="glass-panel"
      style={{
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
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
            letterSpacing: '0.08em',
          }}
        >
          TELEMETRY // SYSTEM HUD
        </span>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            color: wsStatus === 'ONLINE' ? '#00ffd5' : '#ff0055',
          }}
        >
          WS: {wsStatus}
        </span>
      </div>

      {/* Grid of Status Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '10px',
        }}
      >
        {/* Model Route */}
        <div
          style={{
            background: 'rgba(8, 22, 45, 0.5)',
            border: '1px solid rgba(0, 240, 255, 0.2)',
            borderRadius: '4px',
            padding: '10px',
          }}
        >
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            ACTIVE MODEL
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-main)', fontWeight: 600, marginTop: '4px' }}>
            {activeModelRole}
          </div>
          <div style={{ fontSize: '0.65rem', color: '#38bdf8', marginTop: '2px' }}>Llama 3.1 8B</div>
        </div>

        {/* Voice Profile */}
        <div
          style={{
            background: 'rgba(8, 22, 45, 0.5)',
            border: '1px solid rgba(0, 240, 255, 0.2)',
            borderRadius: '4px',
            padding: '10px',
          }}
        >
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            SPEECH SYNTHESIS
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-main)', fontWeight: 600, marginTop: '4px' }}>
            {voicePreferences?.active_profile?.locale || 'en-IN'}
          </div>
          <div style={{ fontSize: '0.65rem', color: '#00ffd5', marginTop: '2px' }}>
            {voicePreferences?.selected_profile_id || 'indian_english_male'}
          </div>
        </div>

        {/* Token Count */}
        <div
          style={{
            background: 'rgba(8, 22, 45, 0.5)',
            border: '1px solid rgba(0, 240, 255, 0.2)',
            borderRadius: '4px',
            padding: '10px',
          }}
        >
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            TOTAL TOKENS
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-main)', fontWeight: 600, marginTop: '4px' }}>
            {usage?.total_tokens || 0}
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            {usage?.total_calls || 0} calls
          </div>
        </div>

        {/* Security Broker */}
        <div
          style={{
            background: 'rgba(8, 22, 45, 0.5)',
            border: '1px solid rgba(0, 240, 255, 0.2)',
            borderRadius: '4px',
            padding: '10px',
          }}
        >
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            POLICY BROKER
          </div>
          <div style={{ fontSize: '0.85rem', color: '#00ff88', fontWeight: 600, marginTop: '4px' }}>
            ACTIVE [ENFORCED]
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-dim)', marginTop: '2px' }}>Audit Hash Chained</div>
        </div>
      </div>
    </div>
  );
};
