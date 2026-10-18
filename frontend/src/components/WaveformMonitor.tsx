import React, { useEffect, useRef } from 'react';

interface WaveformMonitorProps {
  isActive?: boolean;
  amplitude?: number; // 0.0 to 1.0
  color?: string;
}

export const WaveformMonitor: React.FC<WaveformMonitorProps> = ({
  isActive = false,
  amplitude = 0.5,
  color = '#00f0ff',
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let phase = 0;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const width = canvas.width;
      const height = canvas.height;
      const centerY = height / 2;
      const effectiveAmp = isActive ? Math.max(0.25, amplitude) : 0.08;

      // Draw Equalizer Frequency Bars
      const numBars = 36;
      const barWidth = 4;
      const spacing = (width - numBars * barWidth) / (numBars + 1);

      for (let i = 0; i < numBars; i++) {
        const x = spacing + i * (barWidth + spacing);
        const wave = Math.sin(phase + i * 0.25) * 0.5 + 0.5;
        const barHeight = Math.max(4, wave * height * 0.75 * effectiveAmp);

        const gradient = ctx.createLinearGradient(0, centerY - barHeight / 2, 0, centerY + barHeight / 2);
        gradient.addColorStop(0, '#00ffd5');
        gradient.addColorStop(0.5, color);
        gradient.addColorStop(1, 'rgba(0, 240, 255, 0.2)');

        ctx.fillStyle = gradient;
        ctx.fillRect(x, centerY - barHeight / 2, barWidth, barHeight);
      }

      // Draw Center Oscilloscope Sine Wave
      ctx.beginPath();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = 8;
      ctx.shadowColor = color;

      for (let x = 0; x < width; x += 2) {
        const y = centerY + Math.sin(x * 0.04 + phase * 2) * (20 * effectiveAmp) * Math.sin(x / width * Math.PI);
        if (x === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();

      phase += isActive ? 0.08 : 0.02;
      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [isActive, amplitude, color]);

  return (
    <div
      style={{
        width: '100%',
        padding: '8px 16px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '4px',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          width: '100%',
          fontSize: '0.7rem',
          fontFamily: 'var(--font-mono)',
          color: 'var(--cyan-dim)',
          letterSpacing: '0.08em',
        }}
      >
        <span>VOICE FREQUENCY MONITOR // 44.1 kHz</span>
        <span style={{ color: isActive ? '#00ffd5' : 'var(--text-muted)' }}>
          {isActive ? 'SIGNAL DETECTED' : 'STANDBY'}
        </span>
      </div>
      <canvas
        ref={canvasRef}
        width={380}
        height={54}
        style={{
          width: '100%',
          maxWidth: '420px',
          height: '54px',
          borderRadius: '4px',
          background: 'rgba(2, 6, 23, 0.7)',
          border: '1px solid rgba(0, 240, 255, 0.2)',
        }}
      />
    </div>
  );
};
