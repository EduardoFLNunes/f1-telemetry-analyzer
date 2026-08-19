import React, { useEffect, useRef, useState } from 'react';
import { useTelemetryStore } from '../../store/useTelemetryStore';
import { drawMiniMap } from './OverlayRenderer';
import { driverState, speedKmh } from './BroadcastOverlay';
import { resolveSampleMapPosition } from '../../utils/spatialTransform';
import { formatLapTime } from '../../utils/lapFormat';

/**
 * The two corners of the map that carry text.
 *
 * They used to be painted onto the track canvas, laid out by a cursor walked up
 * from the bottom edge. That works until something else wants the same corner:
 * two overlays measured in different places have no way of knowing they
 * overlap. As DOM they sit in the map's overlay grid, where the four quadrants
 * cannot reach into each other however tall their contents grow.
 */

/** The lap in the corner, with the car on it. */
export const TrackMiniMap: React.FC<{ trackData: any; car: any; lapNumber?: number | null }> = ({
  trackData, car, lapNumber,
}) => {
  const boxRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const box = boxRef.current;
    if (!box || typeof ResizeObserver === 'undefined') return undefined;
    const update = () => {
      const rect = box.getBoundingClientRect();
      setSize({ width: rect.width, height: rect.height });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(box);
    return () => observer.disconnect();
  }, []);

  const position = resolveSampleMapPosition(car);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || size.width < 20 || size.height < 20) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(size.width * dpr);
    canvas.height = Math.round(size.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.width, size.height);
    // The inset fills its own canvas: no corner, no margin, no scrim -- the box
    // around it is the panel.
    drawMiniMap(ctx, size.width, size.height, trackData, position, {
      size: Math.min(size.width, size.height),
      margin: 0,
      corner: 'top-left',
      bare: true,
    });
  }, [trackData, size, position?.x, position?.y]);

  const name = trackData?.trackName || trackData?.name;

  return (
    <div ref={boxRef} className="panel map-minimap map-bl">
      <div className="map-minimap-body">
        <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      </div>
      <div className="map-minimap-foot">
        <span>{name ? String(name).replace(/[_-]+/g, ' ').toUpperCase() : 'PISTA'}</span>
        <span>{lapNumber == null ? '' : `VOLTA ${lapNumber}`}</span>
      </div>
    </div>
  );
};

/**
 * What the car is doing, in the corner opposite the inset.
 *
 * Order is the driver's: what the pedals are doing, how fast that is, in what
 * unit, and how long the lap has taken.
 */
export const MapReadout: React.FC<{ trackData: any }> = ({ trackData }) => {
  const latestFrame = useTelemetryStore((state) => state.latestFrame);
  const lapMetrics = useTelemetryStore((state) => state.lapMetrics);
  if (!latestFrame) return null;

  const state = driverState(latestFrame);
  const speed = speedKmh(latestFrame);
  const [r, g, b] = state.colour;
  const lapTime = lapMetrics.currentLapTime ?? (latestFrame as any).lap_time ?? null;
  const track = trackData?.trackName || trackData?.name;

  return (
    <div className="map-readout map-br num">
      <span className="ro-state" style={{ color: `rgb(${r},${g},${b})` }}>{state.label}</span>
      <span className="ro-speed">{speed === null ? '--' : Math.round(speed)}</span>
      <span className="ro-unit">KM/H</span>
      <span className="ro-lap">VOLTA {formatLapTime(Number.isFinite(lapTime) ? lapTime : null)}</span>
      {track && <span className="ro-track">{String(track).replace(/[_-]+/g, ' ').toUpperCase()}</span>}
    </div>
  );
};
