import React, { useState } from 'react';
import type { PendingApproval } from '../services/api';
import { api } from '../services/api';

interface ApprovalModalProps {
  approvals: PendingApproval[];
  onDecided: () => void;
  onClose: () => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  approvals,
  onDecided,
  onClose,
}) => {
  const [processingId, setProcessingId] = useState<string | null>(null);

  const handleDecision = async (id: string, decision: 'APPROVE' | 'REJECT') => {
    try {
      setProcessingId(id);
      await api.decideApproval(id, decision, `User decided ${decision} via Holographic UI`);
      onDecided();
    } catch (err) {
      console.error('Approval decision error:', err);
    } finally {
      setProcessingId(null);
    }
  };

  if (!approvals || approvals.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(3, 7, 18, 0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '20px',
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '560px',
          border: '1px solid var(--crimson-alert)',
          boxShadow: 'var(--glow-crimson)',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '18px',
        }}
      >
        <div className="hud-corner-tl" style={{ borderColor: 'var(--crimson-alert)' }} />
        <div className="hud-corner-tr" style={{ borderColor: 'var(--crimson-alert)' }} />
        <div className="hud-corner-bl" style={{ borderColor: 'var(--crimson-alert)' }} />
        <div className="hud-corner-br" style={{ borderColor: 'var(--crimson-alert)' }} />

        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid rgba(255, 0, 85, 0.3)',
            paddingBottom: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: 'var(--crimson-alert)',
                boxShadow: '0 0 10px var(--crimson-alert)',
              }}
            />
            <h3
              style={{
                fontFamily: 'var(--font-display)',
                color: 'var(--crimson-alert)',
                fontSize: '1rem',
                letterSpacing: '0.1em',
              }}
            >
              CONSEQUENTIAL ACTION REVIEW
            </h3>
          </div>
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

        {/* Body list of pending approvals */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {approvals.map((appr) => (
            <div
              key={appr.id}
              style={{
                background: 'rgba(255, 0, 85, 0.05)',
                border: '1px solid rgba(255, 0, 85, 0.25)',
                borderRadius: '6px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#f0f9ff' }}>
                  {appr.tool_name} (v{appr.tool_version})
                </span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--crimson-alert)',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    border: '1px solid var(--crimson-alert)',
                  }}
                >
                  {appr.risk_class}
                </span>
              </div>

              <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', lineHeight: 1.4 }}>
                {appr.action_summary}
              </div>

              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.68rem',
                  color: 'var(--text-muted)',
                  wordBreak: 'break-all',
                }}
              >
                HASH: {appr.arguments_hash}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: '10px', marginTop: '6px' }}>
                <button
                  className="holo-btn holo-btn-success"
                  onClick={() => handleDecision(appr.id, 'APPROVE')}
                  disabled={processingId === appr.id}
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  {processingId === appr.id ? 'PROCESSING...' : 'AUTHORIZE & EXECUTE'}
                </button>
                <button
                  className="holo-btn holo-btn-danger"
                  onClick={() => handleDecision(appr.id, 'REJECT')}
                  disabled={processingId === appr.id}
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  DENY ACTION
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
