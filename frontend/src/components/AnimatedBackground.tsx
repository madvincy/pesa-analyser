"use client";

import { useEffect, useRef } from "react";

// ─── Palette ──────────────────────────────────────────────────────────────
// M-PESA green as the anchor color, with a gold accent for "money" warmth.
const MPESA_GREEN = "34, 197, 94"; // rgb
const GOLD = "250, 204, 21"; // rgb
const KES_SYMBOLS = ["$", "KSh", "£", "€"];

interface CurrencySymbol {
  x: number;
  y: number;
  vy: number;
  size: number;
  text: string;
  phase: number; // for blink/pulse offset
  blinkSpeed: number;
  color: string;
}

interface Coin {
  x: number;
  y: number;
  vy: number;
  radius: number;
  rotation: number;
  rotationSpeed: number;
  opacity: number;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  opacity: number;
}

interface Bar {
  height: number;
  targetHeight: number;
  x: number;
}

export function AnimatedBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Respect users who've asked for less motion, without losing the theme entirely.
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    let time = 0;

    // ── Particle network (kept from the original, recolored) ───────────────
    const particles: Particle[] = [];
    const particleCount = prefersReducedMotion ? 20 : 45;

    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        radius: Math.random() * 1.8 + 0.8,
        opacity: Math.random() * 0.4 + 0.1,
      });
    }

    // ── Floating currency symbols ($ , KSh, £, €) that blink ───────────────
    const symbols: CurrencySymbol[] = [];
    const symbolCount = prefersReducedMotion ? 8 : 16;

    const spawnSymbol = (initial = false): CurrencySymbol => ({
      x: Math.random() * canvas.width,
      y: initial ? Math.random() * canvas.height : canvas.height + 40,
      vy: -(Math.random() * 0.35 + 0.15),
      size: Math.random() * 22 + 16,
      text: KES_SYMBOLS[Math.floor(Math.random() * KES_SYMBOLS.length)],
      phase: Math.random() * Math.PI * 2,
      blinkSpeed: Math.random() * 1.5 + 0.8,
      color: Math.random() > 0.35 ? MPESA_GREEN : GOLD,
    });

    for (let i = 0; i < symbolCount; i++) {
      symbols.push(spawnSymbol(true));
    }

    // ── Spinning coins (circle + $ , simulated 3D via horizontal squash) ───
    const coins: Coin[] = [];
    const coinCount = prefersReducedMotion ? 4 : 9;

    const spawnCoin = (initial = false): Coin => ({
      x: Math.random() * canvas.width,
      y: initial ? Math.random() * canvas.height : canvas.height + 40,
      vy: -(Math.random() * 0.25 + 0.1),
      radius: Math.random() * 10 + 10,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * 0.04,
      opacity: Math.random() * 0.25 + 0.15,
    });

    for (let i = 0; i < coinCount; i++) {
      coins.push(spawnCoin(true));
    }

    // ── Bottom bar-chart ticker, like a live market feed ────────────────────
    const barCount = 60;
    const barWidth = 0;
    const bars: Bar[] = Array.from({ length: barCount }, (_, i) => ({
      height: Math.random() * 60 + 10,
      targetHeight: Math.random() * 60 + 10,
      x: 0,
    }));
    let barRetargetCounter = 0;

    let animationFrameId: number;

    const animate = () => {
      time += prefersReducedMotion ? 0.006 : 0.016;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // ── 1. Bottom bar-chart ticker (drawn first, sits behind everything) ──
      const chartHeight = 90;
      const chartBaseY = canvas.height;
      const step = canvas.width / (barCount - 1);

      barRetargetCounter++;
      if (barRetargetCounter > 40) {
        barRetargetCounter = 0;
        // Nudge a random bar toward a new target so the "chart" looks alive
        // without every bar jittering every frame.
        const idx = Math.floor(Math.random() * barCount);
        bars[idx].targetHeight = Math.random() * chartHeight + 8;
      }

      ctx.beginPath();
      ctx.moveTo(0, chartBaseY);
      for (let i = 0; i < barCount; i++) {
        const bar = bars[i];
        bar.height += (bar.targetHeight - bar.height) * 0.03;
        const x = i * step;
        const y = chartBaseY - bar.height;
        ctx.lineTo(x, y);
      }
      ctx.lineTo(canvas.width, chartBaseY);
      ctx.closePath();

      const gradient = ctx.createLinearGradient(
        0,
        chartBaseY - chartHeight,
        0,
        chartBaseY,
      );
      gradient.addColorStop(0, `rgba(${MPESA_GREEN}, 0.18)`);
      gradient.addColorStop(1, `rgba(${MPESA_GREEN}, 0.02)`);
      ctx.fillStyle = gradient;
      ctx.fill();

      ctx.beginPath();
      for (let i = 0; i < barCount; i++) {
        const x = i * step;
        const y = chartBaseY - bars[i].height;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${MPESA_GREEN}, 0.35)`;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // ── 2. Particle network ────────────────────────────────────────────────
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${MPESA_GREEN}, ${p.opacity})`;
        ctx.fill();

        particles.forEach((p2) => {
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 140) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(${MPESA_GREEN}, ${0.08 * (1 - distance / 140)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        });
      });

      // ── 3. Spinning coins ───────────────────────────────────────────────────
      coins.forEach((coin, i) => {
        coin.y += coin.vy;
        coin.rotation += coin.rotationSpeed;

        if (coin.y < -40) {
          coins[i] = spawnCoin(false);
          return;
        }

        const squashX = Math.abs(Math.cos(coin.rotation));

        ctx.save();
        ctx.translate(coin.x, coin.y);
        ctx.scale(Math.max(squashX, 0.15), 1);

        ctx.beginPath();
        ctx.arc(0, 0, coin.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${GOLD}, ${coin.opacity})`;
        ctx.fill();
        ctx.strokeStyle = `rgba(${GOLD}, ${coin.opacity + 0.15})`;
        ctx.lineWidth = 1;
        ctx.stroke();

        // Only draw the $ glyph when the coin is facing roughly toward us,
        // otherwise it'd look garbled squished flat.
        if (squashX > 0.35) {
          ctx.scale(1 / Math.max(squashX, 0.15), 1);
          ctx.fillStyle = `rgba(${GOLD}, ${Math.min(coin.opacity + 0.3, 0.9)})`;
          ctx.font = `bold ${coin.radius}px sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText("$", 0, 1);
        }

        ctx.restore();
      });

      // ── 4. Floating, blinking currency symbols ──────────────────────────────
      symbols.forEach((sym, i) => {
        sym.y += sym.vy;

        if (sym.y < -40) {
          symbols[i] = spawnSymbol(false);
          return;
        }

        // Sine-wave blink -- a genuine pulse rather than a random flicker,
        // so it reads as intentional "live ticker" motion, not a glitch.
        const blink = prefersReducedMotion
          ? 0.5
          : (Math.sin(time * sym.blinkSpeed + sym.phase) + 1) / 2;
        const opacity = 0.15 + blink * 0.55;

        ctx.font = `600 ${sym.size}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = `rgba(${sym.color}, ${opacity})`;
        ctx.fillText(sym.text, sym.x, sym.y);
      });

      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ opacity: 0.5 }}
      aria-hidden="true"
    />
  );
}
