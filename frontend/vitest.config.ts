import { defineConfig } from 'vitest/config';

/**
 * The tests here are about the drawing maths, not the DOM: what the ribbon's
 * camera does to a point of road, what the map's paint does as the zoom pulls
 * back. They run in node against fakes for the canvas, which is faster and
 * catches more than rendering a component and looking at nothing.
 */
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
