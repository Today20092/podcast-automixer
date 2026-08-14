import { useCallback, useLayoutEffect, useRef, useState } from "react";

const MAX_PIXELS_PER_SECOND = 100;

export function useDiagnosticViewport(duration: number, playhead: number, onSeek: (time: number) => void) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [viewportWidth, setViewportWidth] = useState(1);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(1);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [following, setFollowing] = useState(true);
  const fitPixelsPerSecond = viewportWidth / duration;

  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const resize = () => {
      const width = viewport.clientWidth || 1;
      setViewportWidth(width);
      setPixelsPerSecond((current) => current <= fitPixelsPerSecond * 1.001 ? width / duration : current);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(viewport);
    return () => observer.disconnect();
  }, [duration, fitPixelsPerSecond]);

  const clampTime = useCallback((time: number) => Math.max(0, Math.min(duration, time)), [duration]);
  const timeToPixel = useCallback((time: number) => clampTime(time) * pixelsPerSecond, [clampTime, pixelsPerSecond]);
  const pixelToTime = useCallback((pixel: number) => clampTime(pixel / pixelsPerSecond), [clampTime, pixelsPerSecond]);
  const fit = useCallback(() => {
    const viewport = viewportRef.current;
    const width = viewport?.clientWidth || viewportWidth;
    setViewportWidth(width);
    setPixelsPerSecond(width / duration);
    viewport?.scrollTo({ left: 0 });
    setScrollLeft(0);
    setFollowing(true);
  }, [duration, viewportWidth]);
  const zoomAt = useCallback((factor: number, anchorClientX?: number) => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const rect = viewport.getBoundingClientRect();
    const anchor = anchorClientX == null
      ? Math.max(0, Math.min(viewportWidth, timeToPixel(playhead) - viewport.scrollLeft))
      : anchorClientX - rect.left;
    const anchorTime = pixelToTime(viewport.scrollLeft + anchor);
    const next = Math.max(viewport.clientWidth / duration, Math.min(MAX_PIXELS_PER_SECOND, pixelsPerSecond * factor));
    setPixelsPerSecond(next);
    requestAnimationFrame(() => {
      const left = Math.max(0, anchorTime * next - anchor);
      viewport.scrollLeft = left;
      setScrollLeft(left);
    });
  }, [duration, pixelToTime, pixelsPerSecond, playhead, timeToPixel, viewportWidth]);
  const seekAt = useCallback((clientX: number) => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    onSeek(pixelToTime(viewport.scrollLeft + clientX - viewport.getBoundingClientRect().left));
  }, [onSeek, pixelToTime]);

  return {
    viewportRef, viewportWidth, pixelsPerSecond, scrollLeft, following,
    contentWidth: Math.max(viewportWidth, duration * pixelsPerSecond),
    playheadPixel: timeToPixel(playhead), timeToPixel, pixelToTime, fit, zoomAt, seekAt,
    onScroll: () => {
      const left = viewportRef.current?.scrollLeft || 0;
      setScrollLeft(left);
      setFollowing(Math.abs(timeToPixel(playhead) - left - viewportWidth / 2) < viewportWidth / 2);
    },
    setFollowing,
  };
}
