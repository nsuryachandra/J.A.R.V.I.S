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
      const effectiveAmp = isActive ? Math.max(0.35, amplitude) : 0.08;

      // Draw Grid Matrix Lines
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.08)';
      ctx.lineWidth = 1;
      for (let y = 10; y < height; y += 15) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Draw Equalizer Frequency Bars
      const numBars = 48;
      const barWidth = 4;
      const spacing = (width - numBars * barWidth) / (numBars + 1);

      for (let i = 0; i < numBars; i++) {
        const x = spacing + i * (barWidth + spacing);
        // Multi-frequency wave synthesis
        const wave1 = Math.sin(phase * 1.8 + i * 0.28) * 0.5 + 0.5;
        const wave2 = Math.cos(phase * 1.2 + i * 0.15) * 0.3 + 0.3;
        const combined = (wave1 + wave2) / 2;
        const barHeight = Math.max(3, combined * height * 0.85 * effectiveAmp);

        const gradient = ctx.createLinearGradient(0, centerY - barHeight / 2, 0, centerY + barHeight / 2);
        gradient.addColorStop(0, '#00ffd5');
        gradient.addColorStop(0.5, color);
        gradient.addColorStop(1, 'rgba(0, 112, 243, 0.3)');

        ctx.fillStyle = gradient;
        ctx.fillRect(x, centerY - barHeight / 2, barWidth, barHeight);

        // Peak tick cap
        if (isActive) {
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(x, centerY - barHeight / 2 - 2, barWidth, 1.5);
        }
      }

      // Draw Center Oscilloscope Hologram Trace
      ctx.beginPath();
      ctx.strokeStyle = isActive ? '#ffffff' : color;
      ctx.lineWidth = isActive ? 2 : 1.2;
      ctx.shadowBlur = isActive ? 12 : 4;
      ctx.shadowColor = color;

      for (let x = 0; x < width; x += 3) {
        const envelope = Math.sin((x / width) * Math.PI);
        const y =
          centerY +
          Math.sin(x * 0.05 + phase * 3) * (24 * effectiveAmp) * envelope +
          Math.cos(x * 0.02 - phase * 1.5) * (8 * effectiveAmp) * envelope;

        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      ctx.shadowBlur = 0;
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
        position: 'relative',
        width: '100%',
        height: '75px',
        background: 'rgba(3, 10, 25, 0.75)',
        border: '1px solid rgba(0, 240, 255, 0.2)',
        borderRadius: '6px',
        overflow: 'hidden',
        boxShadow: isActive ? '0 0 15px rgba(0, 240, 255, 0.2)' : 'none',
      }}
    >
      <canvas
        ref={canvasRef}
        width={480}
        height={75}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: '4px',
          right: '8px',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.62rem',
          color: isActive ? '#00ffd5' : 'var(--text-muted)',
          letterSpacing: '0.08em',
        }}
      >
        {isActive ? '● 44.1 kHz // SYNTHESIZING AUDIO' : '○ 44.1 kHz // STANDBY'}
      </div>
    </div>
  );
};
