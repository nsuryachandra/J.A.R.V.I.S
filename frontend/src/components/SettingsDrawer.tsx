import React, { useState, useEffect } from 'react';
import type { VoicePreferences, VoiceProfile, SystemStatus } from '../services/api';
import { api } from '../services/api';
import { soundFx } from '../services/sound';

interface SettingsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  voicePreferences: VoicePreferences | null;
  onPreferencesUpdated: (newPrefs: VoicePreferences) => void;
  activeModelRole: string;
  onModelRoleChanged: (role: string) => void;
  systemStatus: SystemStatus | null;
  onStatusUpdated?: (status: SystemStatus) => void;
}

export const SettingsDrawer: React.FC<SettingsDrawerProps> = ({
  isOpen,
  onClose,
  voicePreferences,
  onPreferencesUpdated,
  activeModelRole,
  onModelRoleChanged,
  systemStatus,
  onStatusUpdated,
}) => {
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<string>('indian_english_male');
  const [speed, setSpeed] = useState<number>(1.0);
  const [voiceEnabled, setVoiceEnabled] = useState<boolean>(true);
  const [privacyMode, setPrivacyMode] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  // API Key Inputs
  const [grokKey, setGrokKey] = useState<string>('');
  const [groqKey, setGroqKey] = useState<string>('');
  const [nvidiaKey, setNvidiaKey] = useState<string>('');
  const [keyStatusMessage, setKeyStatusMessage] = useState<string | null>(null);
  const [isTestingKey, setIsTestingKey] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      soundFx.playClick();
      api.getVoiceProfiles().then((p) => setProfiles(p)).catch(console.error);
      api.getSystemStatus().then((s) => onStatusUpdated?.(s)).catch(console.error);
    }
  }, [isOpen]);

  useEffect(() => {
    if (voicePreferences) {
      setSelectedProfile(voicePreferences.selected_profile_id);
      setSpeed(voicePreferences.speed);
      setVoiceEnabled(voicePreferences.voice_enabled);
      setPrivacyMode(voicePreferences.privacy_mode);
    }
  }, [voicePreferences]);

  const handleSaveVoice = async () => {
    try {
      soundFx.playClick();
      setIsSaving(true);
      const updated = await api.updateVoicePreferences({
        selected_profile_id: selectedProfile,
        speed,
        voice_enabled: voiceEnabled,
        privacy_mode: privacyMode,
      });
      onPreferencesUpdated(updated);
      setKeyStatusMessage('Voice preferences updated.');
    } catch (err: any) {
      setKeyStatusMessage(`Update failed: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleActivateKeys = async () => {
    try {
      soundFx.playReactorHum();
      setIsTestingKey(true);
      setKeyStatusMessage('Verifying API keys against providers...');

      const res = await api.updateSystemKeys({
        grok_api_key: grokKey.trim() || undefined,
        groq_api_key: groqKey.trim() || undefined,
        nvidia_api_key: nvidiaKey.trim() || undefined,
      });

      if (res.status) {
        onStatusUpdated?.(res.status);
      }

      setKeyStatusMessage(res.message);
      if (res.success) {
        soundFx.playResponse();
      }
    } catch (err: any) {
      setKeyStatusMessage(`Verification error: ${err.message}`);
    } finally {
      setIsTestingKey(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(3, 7, 18, 0.85)',
        backdropFilter: 'blur(10px)',
        zIndex: 100,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
      onClick={onClose}
    >
      <div
        className="glass-panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '460px',
          height: '100%',
          padding: '24px',
          borderRadius: '12px 0 0 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '18px',
          boxShadow: '-15px 0 40px rgba(0, 240, 255, 0.25)',
          overflowY: 'auto',
        }}
      >
        <div className="hud-corner-tl" />
        <div className="hud-corner-bl" />

        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid rgba(0, 240, 255, 0.3)',
            paddingBottom: '12px',
          }}
        >
          <div>
            <h3
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: '1rem',
                color: 'var(--cyan-primary)',
                letterSpacing: '0.12em',
              }}
            >
              STARK PROTOCOL // SYSTEM CONFIG
            </h3>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              Configure live neural providers & speech synthesis
            </span>
          </div>
          <button
            onClick={() => {
              soundFx.playClick();
              onClose();
            }}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-cyan)',
              cursor: 'pointer',
              fontSize: '1.4rem',
            }}
          >
            ✕
          </button>
        </div>

        {/* Provider Live Status Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '10px',
            background: 'rgba(4, 13, 29, 0.7)',
            padding: '12px',
            borderRadius: '6px',
            border: '1px solid rgba(0, 240, 255, 0.2)',
          }}
        >
          <div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
              VOICE ENGINE
            </div>
            <div
              style={{
                fontSize: '0.8rem',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                color: '#00ff88',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                marginTop: '4px',
              }}
            >
              <span>●</span>
              <span>OPEN-SOURCE NEURAL (ACTIVE)</span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
              NEURAL AI INFERENCE
            </div>
            <div
              style={{
                fontSize: '0.8rem',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                color: systemStatus?.ai_configured ? '#00ff88' : '#00ffd5',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                marginTop: '4px',
              }}
            >
              <span>{systemStatus?.ai_configured ? '●' : '⚡'}</span>
              <span>
                {systemStatus?.grok_configured
                  ? 'GROK-2 (LIVE)'
                  : systemStatus?.groq_configured
                  ? 'GROQ LLAMA-3 (LIVE)'
                  : systemStatus?.nvidia_configured
                  ? 'NVIDIA NIM (LIVE)'
                  : 'AUTONOMOUS CORE'}
              </span>
            </div>
          </div>
        </div>

        {/* API Key Configuration Form */}
        <div
          style={{
            background: 'rgba(0, 240, 255, 0.04)',
            border: '1px solid rgba(0, 240, 255, 0.25)',
            borderRadius: '6px',
            padding: '14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', fontFamily: 'var(--font-display)', color: 'var(--cyan-primary)' }}>
              AI INFERENCE API KEYS
            </span>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Auto-saves to backend/.env</span>
          </div>

          {/* Voice Engine Info Banner */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: '4px',
              background: 'rgba(0, 255, 136, 0.08)',
              border: '1px solid rgba(0, 255, 136, 0.25)',
              fontSize: '0.72rem',
              color: '#00ff88',
              lineHeight: 1.4,
            }}
          >
            <strong>✓ Open-Source Multi-Lingual Voice Ready:</strong> Zero external credentials needed. Speaks fluent English, Telugu, Tenglish, and Hindi with calibrated regional pacing.
          </div>

          {/* Grok API Key */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              GROK API KEY (xAI Grok-2 / Vision)
            </label>
            <input
              type="password"
              placeholder={systemStatus?.grok_configured ? '•••••••••••••••• (Active)' : 'Paste Grok API key (xai-...)'}
              value={grokKey}
              onChange={(e) => setGrokKey(e.target.value)}
              style={{
                background: 'var(--bg-input)',
                border: '1px solid rgba(0, 240, 255, 0.3)',
                color: 'var(--text-main)',
                borderRadius: '4px',
                padding: '8px 10px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                outline: 'none',
              }}
            />
          </div>

          {/* Groq / NVIDIA API Key */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              GROQ API KEY (Free & Instant Llama 3.3)
            </label>
            <input
              type="password"
              placeholder={systemStatus?.groq_configured ? '•••••••••••••••• (Active)' : 'Paste Groq key (gsk_...)'}
              value={groqKey}
              onChange={(e) => setGroqKey(e.target.value)}
              style={{
                background: 'var(--bg-input)',
                border: '1px solid rgba(0, 240, 255, 0.3)',
                color: 'var(--text-main)',
                borderRadius: '4px',
                padding: '8px 10px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                outline: 'none',
              }}
            />
          </div>

          {/* NVIDIA NIM Key */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              OR NVIDIA NIM API KEY (build.nvidia.com)
            </label>
            <input
              type="password"
              placeholder={systemStatus?.nvidia_configured ? '•••••••••••••••• (Active)' : 'Paste NVIDIA key (nvapi-...)'}
              value={nvidiaKey}
              onChange={(e) => setNvidiaKey(e.target.value)}
              style={{
                background: 'var(--bg-input)',
                border: '1px solid rgba(0, 240, 255, 0.3)',
                color: 'var(--text-main)',
                borderRadius: '4px',
                padding: '8px 10px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                outline: 'none',
              }}
            />
          </div>

          <button
            className="holo-btn"
            onClick={handleActivateKeys}
            disabled={isTestingKey}
            style={{
              padding: '10px',
              fontSize: '0.78rem',
              justifyContent: 'center',
              backgroundColor: 'rgba(0, 240, 255, 0.15)',
            }}
          >
            {isTestingKey ? 'VERIFYING...' : '⚡ TEST & ACTIVATE API KEYS'}
          </button>

          {keyStatusMessage && (
            <div
              style={{
                fontSize: '0.72rem',
                fontFamily: 'var(--font-mono)',
                color: keyStatusMessage.includes('failed') || keyStatusMessage.includes('error') ? '#ff0055' : '#00ffd5',
                padding: '6px 8px',
                background: 'rgba(0,0,0,0.4)',
                borderRadius: '4px',
              }}
            >
              {keyStatusMessage}
            </div>
          )}
        </div>

        {/* Model Role Strategy */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '0.76rem', fontFamily: 'var(--font-display)', color: 'var(--text-cyan)' }}>
            AI REASONING DISPATCH STRATEGY
          </label>
          <select
            value={activeModelRole}
            onChange={(e) => onModelRoleChanged(e.target.value)}
            style={{
              background: 'var(--bg-input)',
              border: '1px solid rgba(0, 240, 255, 0.3)',
              color: 'var(--text-main)',
              borderRadius: '4px',
              padding: '10px',
              fontFamily: 'var(--font-mono)',
              outline: 'none',
              fontSize: '0.82rem',
            }}
          >
            <option value="auto">⚡ Auto (AI Evaluates Prompt Dynamically)</option>
            <option value="fast_chat">Fast Chat (Llama 3.1 8B)</option>
            <option value="reasoning">Deep Reasoning (Llama 3.1 70B)</option>
            <option value="coding">Code Synthesis (Llama 3.1 70B)</option>
            <option value="vision">Vision Multimodal (Neva 22B)</option>
          </select>
        </div>

        {/* Voice Profile */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <label style={{ fontSize: '0.76rem', fontFamily: 'var(--font-display)', color: 'var(--text-cyan)' }}>
            SPEECH SYNTHESIS VOICE
          </label>
          <select
            value={selectedProfile}
            onChange={(e) => setSelectedProfile(e.target.value)}
            style={{
              background: 'var(--bg-input)',
              border: '1px solid rgba(0, 240, 255, 0.3)',
              color: 'var(--text-main)',
              borderRadius: '4px',
              padding: '10px',
              fontFamily: 'var(--font-mono)',
              outline: 'none',
              fontSize: '0.82rem',
            }}
          >
            {profiles.map((p) => (
              <option key={p.profile_id} value={p.profile_id}>
                {p.display_name} ({p.locale})
              </option>
            ))}
          </select>
        </div>

        {/* Speech Speed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem' }}>
            <span style={{ fontFamily: 'var(--font-display)', color: 'var(--text-cyan)' }}>SPEECH TEMPO RATE</span>
            <span style={{ fontFamily: 'var(--font-mono)' }}>{speed.toFixed(2)}x</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.05"
            value={speed}
            onChange={(e) => setSpeed(parseFloat(e.target.value))}
            style={{ accentColor: 'var(--cyan-primary)' }}
          />
        </div>

        {/* Toggles */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}>
            <span style={{ fontSize: '0.82rem' }}>Voice Audio Synthesis</span>
            <input
              type="checkbox"
              checked={voiceEnabled}
              onChange={(e) => setVoiceEnabled(e.target.checked)}
              style={{ width: '18px', height: '18px', accentColor: 'var(--cyan-primary)' }}
            />
          </label>

          <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}>
            <div>
              <div style={{ fontSize: '0.82rem' }}>Privacy Mode</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Mask text from audit ledger</div>
            </div>
            <input
              type="checkbox"
              checked={privacyMode}
              onChange={(e) => setPrivacyMode(e.target.checked)}
              style={{ width: '18px', height: '18px', accentColor: 'var(--cyan-primary)' }}
            />
          </label>
        </div>

        {/* Save button */}
        <div style={{ marginTop: 'auto', paddingTop: '10px' }}>
          <button
            className="holo-btn"
            onClick={handleSaveVoice}
            disabled={isSaving}
            style={{ width: '100%', justifyContent: 'center', padding: '12px' }}
          >
            {isSaving ? 'UPDATING...' : 'APPLY CONFIGURATION'}
          </button>
        </div>
      </div>
    </div>
  );
};
