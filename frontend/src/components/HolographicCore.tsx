import React from 'react';

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

  return (
    <div
      onClick={onClick}
      style={{
        position: 'relative',
        width: '320px',
        height: '320px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
      }}
      title="Click to interact with JARVIS Core"
    >
      {/* Outer Ring with Coordinate Ticks */}
      <svg
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
          animation: `spinClockwise ${status === 'PROCESSING' ? '6s' : '24s'} linear infinite`,
        }}
        viewBox="0 0 320 320"
      >
        <circle
          cx="160"
          cy="160"
          r="150"
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeDasharray="4 8 16 8"
          opacity="0.4"
        />
        <circle
          cx="160"
          cy="160"
          r="138"
          fill="none"
          stroke={color}
          strokeWidth="1"
          strokeDasharray="60 30 15 30"
          opacity="0.6"
        />
        {/* Cardinal North/South/East/West markers */}
        <line x1="160" y1="5" x2="160" y2="15" stroke={color} strokeWidth="2" opacity="0.8" />
        <line x1="160" y1="305" x2="160" y2="315" stroke={color} strokeWidth="2" opacity="0.8" />
        <line x1="5" y1="160" x2="15" y2="160" stroke={color} strokeWidth="2" opacity="0.8" />
        <line x1="305" y1="160" x2="315" y2="160" stroke={color} strokeWidth="2" opacity="0.8" />
      </svg>

      {/* Middle Counter-Rotating Segmented Ring */}
      <svg
        style={{
          position: 'absolute',
          width: '260px',
          height: '260px',
          animation: `spinCounterClockwise ${status === 'PROCESSING' ? '4s' : '16s'} linear infinite`,
        }}
        viewBox="0 0 260 260"
      >
        <circle
          cx="130"
          cy="130"
          r="115"
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeDasharray="90 40 20 40"
          opacity="0.75"
        />
        <circle
          cx="130"
          cy="130"
          r="95"
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeDasharray="6 6"
          opacity="0.5"
        />
      </svg>

      {/* Inner Fast Orbiting Gyro Ring */}
      <svg
        style={{
          position: 'absolute',
          width: '180px',
          height: '180px',
          animation: `spinClockwise ${status === 'SPEAKING' ? '3s' : '10s'} linear infinite`,
        }}
        viewBox="0 0 180 180"
      >
        <polygon
          points="90,15 165,90 90,165 15,90"
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeDasharray="10 5"
          opacity="0.55"
        />
        <circle
          cx="90"
          cy="90"
          r="65"
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeDasharray="40 20"
          opacity="0.8"
        />
      </svg>

      {/* Central Arc Reactor Glowing Nucleus */}
      <div
        style={{
          width: '84px',
          height: '84px',
          borderRadius: '50%',
          background: `radial-gradient(circle, #ffffff 0%, ${color} 55%, transparent 95%)`,
          boxShadow: `0 0 ${40 * pulseIntensity}px ${color}, inset 0 0 20px #ffffff`,
          animation: 'pulseGlow 2.5s ease-in-out infinite',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 2,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '0.65rem',
            fontWeight: 800,
            color: '#020617',
            letterSpacing: '0.12em',
          }}
        >
          {status}
        </span>
      </div>

      {/* Ambient Pulsing Glow Halo */}
      <div
        style={{
          position: 'absolute',
          width: '280px',
          height: '280px',
          borderRadius: '50%',
          background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
          opacity: 0.15 * pulseIntensity,
          pointerEvents: 'none',
        }}
      />
    </div>
  );
};
