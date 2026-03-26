import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';

interface RevealSectionProps {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
  variant?: 'default' | 'hero' | 'panel';
}

export default function RevealSection({
  children,
  className,
  delayMs = 0,
  variant = 'default',
}: RevealSectionProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.16, rootMargin: '0px 0px -8% 0px' },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) return;

    let frameId = 0;

    const updateScene = () => {
      const rect = node.getBoundingClientRect();
      const viewportHeight = window.innerHeight || 1;
      const progress = Math.min(1, Math.max(0, (viewportHeight - rect.top) / (viewportHeight + rect.height)));
      const depth = variant === 'hero' ? 22 : 30;
      const scaleFloor = variant === 'hero' ? 0.988 : 0.982;
      const offset = (0.5 - progress) * depth;
      const scale = scaleFloor + progress * (1 - scaleFloor);

      node.style.setProperty('--scene-offset', `${offset.toFixed(2)}px`);
      node.style.setProperty('--scene-scale', scale.toFixed(4));
      node.style.setProperty('--scene-progress', progress.toFixed(4));
      frameId = 0;
    };

    const scheduleUpdate = () => {
      if (frameId) return;
      frameId = window.requestAnimationFrame(updateScene);
    };

    scheduleUpdate();
    window.addEventListener('scroll', scheduleUpdate, { passive: true });
    window.addEventListener('resize', scheduleUpdate);

    return () => {
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
      window.removeEventListener('scroll', scheduleUpdate);
      window.removeEventListener('resize', scheduleUpdate);
    };
  }, [variant]);

  return (
    <div
      ref={ref}
      className={clsx(
        'reveal-section',
        `reveal-scene-${variant}`,
        visible && 'reveal-section-visible',
        className
      )}
      style={{ transitionDelay: `${delayMs}ms` }}
    >
      {children}
    </div>
  );
}
