import React from 'react';
import { soundFx } from '../services/sound';

interface HolographicCoreProps {
  status: 'IDLE' | 'PROCESSING' | 'SPEAKING' | 'ALERT';
  pulseIntensity?: number;
  onClick?: () => void;
}

export const HolographicCore: React.FC<HolographicCoreProps> = ({
  status,
  pulseIntensity = 1.0,
  onClick,
}) => {
  const getStatusColor = () => {
    switch (status) {
      case 'SPEAKING':
        return '#00ffd5'; // Neon teal
      case 'PROCESSING':
        return '#38bdf8'; // Electric blue
      case 'ALERT':
        return '#ff0055'; // Crimson
      default:
        return '#00f0ff'; // Holographic cyan
    }
  };

  const color = getStatusColor();

  const handleClick = () => {
    soundFx.playReactorHum();
    onClick?.();
  };

  return (
    <div
      onClick={handleClick}
      style={{
        position: 'relative',
        width: '340px',
        height: '340px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        userSelect: 'none',
        transform: `scale(${pulseIntensity})`,
        transition: 'transform 0.3s ease',
      }}
      title="STARK ARC REACTOR // Click to initialize diagnostic pulse"
    >
      {/* Background Radial Glow */}
      <div
        style={{
          position: 'absolute',
          width: '280px',
          height: '280px',
          borderRadius: '50%',
          background: `radial-gradient(circle, ${color}25 0%, ${color}08 45%, transparent 70%)`,
          filter: 'blur(20px)',
          transition: 'background 0.5s ease',
        }}
      />

      {/* Outer Ring 1: Radar Compass & Degree Markings */}
      <svg
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
          animation: `spinClockwise ${status === 'PROCESSING' ? '6s' : '40s'} linear infinite`,
        }}
        viewBox="0 0 340 340"
      >
        <circle
          cx="170"
          cy="170"
          r="162"
          fill="none"
          stroke={color}
          strokeWidth="1"
          strokeDasharray="4 8 20 8 4 16"
          opacity="0.35"
        />
        <circle
          cx="170"
          cy="170"
          r="154"
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeDasharray="80 20 10 20"
          opacity="0.5"
        />
        {/* Calipers and Cardinal ticks */}
        <line x1="170" y1="4" x2="170" y2="16" stroke={color} strokeWidth="2" opacity="0.9" />
        <line x1="170" y1="324" x2="170" y2="336" stroke={color} strokeWidth="2" opacity="0.9" />
        <line x1="4" y1="170" x2="16" y2="170" stroke={color} strokeWidth="2" opacity="0.9" />
        <line x1="324" y1="170" x2="336" y2="170" stroke={color} strokeWidth="2" opacity="0.9" />
      </svg>

      {/* Middle Ring 2: Counter-Rotating Mechanical Segment Brackets */}
      <svg
        style={{
          position: 'absolute',
          width: '280px',
          height: '280px',
          animation: `spinCounterClockwise ${status === 'PROCESSING' ? '4s' : '22s'} linear infinite`,
        }}
        viewBox="0 0 280 280"
      >
        <circle
          cx="140"
          cy="140"
          r="128"
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeDasharray="90 30 15 30"
          opacity="0.7"
        />
        <circle
          cx="140"
          cy="140"
          r="118"
          fill="none"
          stroke={color}
          strokeWidth="1"
          strokeDasharray="4 6"
          opacity="0.4"
        />
      </svg>

      {/* Ring 3: Fast Inner Data Wheel */}
      <svg
        style={{
          position: 'absolute',
          width: '220px',
          height: '220px',
          animation: `spinClockwise ${status === 'PROCESSING' ? '3s' : '14s'} linear infinite`,
        }}
        viewBox="0 0 220 220"
      >
        <circle
          cx="110"
          cy="110"
          r="98"
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeDasharray="30 15 60 15"
          opacity="0.8"
        />
        {/* Radial Spokes */}
        {[0, 45, 90, 135, 180, 225, 270, 315].map((angle) => (
          <line
            key={angle}
            x1="110"
            y1="22"
            x2="110"
            y2="32"
            stroke={color}
            strokeWidth="1.5"
            opacity="0.6"
            transform={`rotate(${angle} 110 110)`}
          />
        ))}
      </svg>

      {/* Pulsating Reactor Core */}
      <div
        style={{
          position: 'relative',
          width: '130px',
          height: '130px',
          borderRadius: '50%',
          background: `radial-gradient(circle at 40% 40%, #ffffff 0%, ${color} 40%, rgba(3, 15, 38, 0.95) 90%)`,
          boxShadow: `0 0 30px ${color}80, 0 0 60px ${color}40, inset 0 0 20px #ffffff90`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          animation:
            status === 'SPEAKING'
              ? 'holoPulse 1s ease-in-out infinite'
              : status === 'PROCESSING'
              ? 'holoPulse 0.6s ease-in-out infinite'
              : 'holoPulse 3s ease-in-out infinite',
          border: `2px solid ${color}`,
        }}
      >
        {/* Arc Core Triangular Geometry (Stark Mk VII style) */}
        <div
          style={{
            position: 'absolute',
            width: '84px',
            height: '84px',
            border: `1.5px solid rgba(255, 255, 255, 0.6)`,
            transform: 'rotate(45deg)',
            boxShadow: `0 0 10px ${color}`,
            borderRadius: '4px',
            pointerEvents: 'none',
          }}
        />

        <span
          style={{
            position: 'relative',
            zIndex: 2,
            fontFamily: 'var(--font-display)',
            fontSize: '0.82rem',
            fontWeight: 800,
            letterSpacing: '0.14em',
            color: '#030712',
            textShadow: '0 0 8px rgba(255, 255, 255, 0.9)',
          }}
        >
          {status}
        </span>
        <span
          style={{
            position: 'relative',
            zIndex: 2,
            fontFamily: 'var(--font-mono)',
            fontSize: '0.62rem',
            fontWeight: 600,
            color: '#04172f',
            letterSpacing: '0.08em',
          }}
        >
          MK-VII CORE
        </span>
      </div>

      {/* Orbital Telemetry Float Points */}
      <div
        style={{
          position: 'absolute',
          bottom: '12px',
          left: '50%',
          transform: 'translateX(-50%)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.65rem',
          color: color,
          letterSpacing: '0.12em',
          opacity: 0.85,
          textShadow: `0 0 6px ${color}`,
        }}
      >
        SYS // 98.4% FLUX
      </div>
    </div>
  );
};
