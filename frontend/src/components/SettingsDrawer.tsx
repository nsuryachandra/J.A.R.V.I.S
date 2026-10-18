import React, { useState, useEffect } from 'react';
import type { VoicePreferences, VoiceProfile } from '../services/api';
import { api } from '../services/api';

interface SettingsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  voicePreferences: VoicePreferences | null;
  onPreferencesUpdated: (newPrefs: VoicePreferences) => void;
  activeModelRole: string;
  onModelRoleChanged: (role: string) => void;
}

export const SettingsDrawer: React.FC<SettingsDrawerProps> = ({
  isOpen,
  onClose,
  voicePreferences,
  onPreferencesUpdated,
  activeModelRole,
  onModelRoleChanged,
}) => {
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<string>('indian_english_male');
  const [speed, setSpeed] = useState<number>(1.0);
  const [voiceEnabled, setVoiceEnabled] = useState<boolean>(true);
  const [privacyMode, setPrivacyMode] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      api.getVoiceProfiles().then((p) => setProfiles(p)).catch(console.error);
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
      setIsSaving(true);
      const updated = await api.updateVoicePreferences({
        selected_profile_id: selectedProfile,
        speed,
        voice_enabled: voiceEnabled,
        privacy_mode: privacyMode,
      });
      onPreferencesUpdated(updated);
    } catch (err) {
      console.error('Failed to update voice preferences:', err);
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(3, 7, 18, 0.75)',
        backdropFilter: 'blur(6px)',
        zIndex: 90,
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
          maxWidth: '420px',
          height: '100%',
          padding: '24px',
          borderRadius: '8px 0 0 8px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
          boxShadow: '-10px 0 30px rgba(0, 240, 255, 0.15)',
        }}
      >
        <div className="hud-corner-tl" />
        <div className="hud-corner-bl" />

        {/* Drawer Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid rgba(0, 240, 255, 0.25)',
            paddingBottom: '12px',
          }}
        >
          <h3
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '1rem',
              color: 'var(--cyan-primary)',
              letterSpacing: '0.1em',
            }}
          >
            SYSTEM PROTOCOLS & CONFIG
          </h3>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '1.2rem',
            }}
          >
            ✕
          </button>
        </div>

        {/* Model Role Strategy */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '0.78rem', fontFamily: 'var(--font-display)', color: 'var(--text-cyan)' }}>
            NEURAL MODEL ROLE STRATEGY
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
            }}
          >
            <option value="fast_chat">Fast Chat (Llama 3.1 8B)</option>
            <option value="reasoning">Reasoning (Llama 3.1 70B)</option>
            <option value="coding">Coding (Llama 3.1 70B)</option>
            <option value="vision">Vision (Multimodal Llama 3.2)</option>
          </select>
        </div>

        {/* Voice Profile */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '0.78rem', fontFamily: 'var(--font-display)', color: 'var(--text-cyan)' }}>
            ELEVENLABS VOICE PROFILE
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '10px' }}>
          <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}>
            <span style={{ fontSize: '0.85rem' }}>Voice Audio Synthesis</span>
            <input
              type="checkbox"
              checked={voiceEnabled}
              onChange={(e) => setVoiceEnabled(e.target.checked)}
              style={{ width: '18px', height: '18px', accentColor: 'var(--cyan-primary)' }}
            />
          </label>

          <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}>
            <div>
              <div style={{ fontSize: '0.85rem' }}>Privacy Mode</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Mask text from audit ledger</div>
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
        <div style={{ marginTop: 'auto' }}>
          <button
            className="holo-btn"
            onClick={handleSaveVoice}
            disabled={isSaving}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            {isSaving ? 'UPDATING...' : 'APPLY CONFIGURATION'}
          </button>
        </div>
      </div>
    </div>
  );
};
