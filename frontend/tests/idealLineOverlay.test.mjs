import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildCurrentLinePathCache,
  buildIdealLineRenderModel,
  computeSpeedRange,
  getSpeedColor,
} from '../src/components/map/idealLineOverlay.js';

test('getSpeedColor maps low, medium and high speeds', () => {
  assert.equal(getSpeedColor(100, 100, 300), 'rgb(239, 68, 68)');
  assert.equal(getSpeedColor(200, 100, 300), 'rgb(245, 158, 11)');
  assert.equal(getSpeedColor(300, 100, 300), 'rgb(34, 197, 94)');
});

test('getSpeedColor uses a neutral color for unknown speed', () => {
  assert.equal(getSpeedColor(null, 100, 300), 'rgba(148, 163, 184, 0.52)');
  assert.equal(getSpeedColor(200, null, 300), 'rgba(148, 163, 184, 0.52)');
});

test('computeSpeedRange ignores null and zero speeds', () => {
  assert.deepEqual(
    computeSpeedRange([
      { speedKmh: null },
      { speedKmh: 0 },
      { speedKmh: 92 },
      { speedKmh: 256 },
    ]),
    { minSpeedKmh: 92, maxSpeedKmh: 256 },
  );
});

test('buildIdealLineRenderModel ignores invalid points and breaks abnormal jumps', () => {
  const model = buildIdealLineRenderModel(
    {
      source: 'REFERENCE_LAP',
      points: [
        { x: 0, z: 0, speedKmh: 120 },
        { x: null, z: 1, speedKmh: 140 },
        { x: 8, z: 0, speedKmh: 160 },
        { x: 16, z: 0, speedKmh: 180 },
        { x: 300, z: 0, speedKmh: 260 },
      ],
    },
    { performanceMode: 'QUALITY', maxJumpMeters: 50 },
  );

  assert.equal(model.centerSegments.length, 3);
  assert.equal(model.centerSegments[0].length, 1);
  assert.equal(model.centerSegments[1].length, 2);
  assert.equal(model.centerSegments[2].length, 1);
  assert.equal(model.coloredSegments.length, 1);
});

test('buildCurrentLinePathCache builds lap line segments from telemetry samples', () => {
  const cache = buildCurrentLinePathCache(
    [
      { timestamp: 1, lap_number: 7, speedKmh: 100, mapPosition: { x: 0, y: 0 } },
      { timestamp: 2, lap_number: 7, speedKmh: 140, mapPosition: { x: 10, y: 0 } },
      { timestamp: 3, lap_number: 7, speedKmh: 220, mapPosition: { x: 250, y: 0 } },
      { timestamp: 4, lap_number: 7, speedKmh: 260, mapPosition: { x: 260, y: 0 } },
    ],
    'QUALITY',
  );

  assert.equal(cache.validPointCount, 4);
  assert.equal(cache.centerSegments.length, 2);
  assert.equal(cache.centerSegments[0].length, 2);
  assert.equal(cache.centerSegments[1].length, 2);
  assert.equal(cache.coloredSegments.length, 2);
  assert.equal(cache.minSpeedKmh, 100);
  assert.equal(cache.maxSpeedKmh, 260);
});
