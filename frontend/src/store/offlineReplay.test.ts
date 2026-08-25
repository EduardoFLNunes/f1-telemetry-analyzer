import { beforeEach, describe, expect, it } from 'vitest';
import { useTelemetryStore } from './useTelemetryStore';

/**
 * Watching a lap back with the simulator closed.
 *
 * This is the path a user takes when the driving is over: pick a recorded
 * session, pick a lap, press play. Nothing here talks to the game, so the whole
 * thing can be exercised without Assetto Corsa running -- which is also how the
 * rest of the app gets tested without a car on track.
 */

const store = useTelemetryStore;
const pristine = store.getState();

/** A lap of samples, one every tenth of a second, going round the circuit. */
function lapSamples(count: number, options: { lapNumber?: number; step?: number; length?: number } = {}): any[] {
  const step = options.step ?? 0.1;
  const length = options.length ?? 4300;
  return Array.from({ length: count }, (_, index) => ({
    driver_id: 'dokas',
    lap_number: options.lapNumber ?? 7,
    lap_time: index * step,
    s: (index / Math.max(1, count - 1)) * length,
    speed: 60,
    throttle: 1,
    brake: 0,
    steering: 0,
    gear: 4,
    lapProgress: index / Math.max(1, count - 1),
  }));
}

function play(samples: any[], extra: Record<string, any> = {}) {
  store.getState().startOfflineReplay({
    lapId: 'lap-1',
    sessionId: 'session-1',
    samples,
    ...extra,
  } as any);
  return store.getState();
}

beforeEach(() => {
  store.setState(pristine, true);
});

describe('starting a replay', () => {
  it('takes the app out of live and puts the recorded lap on screen', () => {
    const samples = lapSamples(50);
    const state = play(samples, { track: 'interlagos', car: 'formula', lapNumber: 7 });

    expect(state.viewMode).toBe('replay');
    expect(state.isStreaming).toBe(false);
    expect(state.offlineReplay.active).toBe(true);
    expect(state.offlineReplay.source).toBe('persisted_lap');
    // The map and the traces read the same fields they do when live, so the
    // whole dashboard replays without knowing where the frames came from.
    expect(state.latestFrame).toBe(samples[0]);
    expect(state.history).toBe(samples);
    expect(state.offlineReplay.track).toBe('interlagos');
    expect(state.offlineReplay.lapNumber).toBe(7);
  });

  it('starts playing on its own so pressing replay is one click', () => {
    expect(play(lapSamples(50)).offlineReplay.playing).toBe(true);
  });

  it('measures the lap from the samples when the session did not say', () => {
    const state = play(lapSamples(50));           // 49 steps of 0.1 s
    expect(state.offlineReplay.duration).toBeCloseTo(4.9, 6);
    expect(state.offlineReplay.lapTime).toBeCloseTo(4.9, 6);
  });

  it('believes the recorded lap time over the samples', () => {
    const state = play(lapSamples(50), { duration: 71.2, lapTime: 71.2 });
    expect(state.offlineReplay.duration).toBeCloseTo(71.2, 6);
  });

  it('holds a lap of one sample without pretending to play it', () => {
    const state = play(lapSamples(1));
    expect(state.offlineReplay.active).toBe(true);
    expect(state.offlineReplay.playing).toBe(false);
  });

  it('does not enter replay with nothing to replay', () => {
    const state = play([]);
    expect(state.offlineReplay.active).toBe(false);
    expect(state.offlineReplay.playing).toBe(false);
  });

  it('carries the reference lap through as the ghost', () => {
    const reference = lapSamples(50, { lapNumber: 6 });
    const state = play(lapSamples(50), { referenceSamples: reference, referenceLapId: 'lap-0', referenceLapNumber: 6 });
    expect(state.ghostHistory).toBe(reference);
    expect(state.offlineReplay.referenceLapNumber).toBe(6);
    expect(state.lapMetrics.hasPreviousLap).toBe(true);
  });

  it('reports what the session said about the recording', () => {
    const state = play(lapSamples(20), {
      assettoClosed: true,
      validationStatus: 'accepted',
      issues: ['sem referencia'],
      message: 'volta parcial',
      canAnalyze: true,
    });
    expect(state.offlineReplay.assettoClosed).toBe(true);
    expect(state.offlineReplay.validationStatus).toBe('accepted');
    expect(state.offlineReplay.issues).toEqual(['sem referencia']);
    expect(state.offlineReplay.canAnalyze).toBe(true);
  });
});

describe('running the replay', () => {
  it('advances by real time, scaled by the playback rate', () => {
    play(lapSamples(200));
    store.getState().advanceOfflineReplay(1);
    const single = store.getState().offlineReplay.currentTime;
    expect(single).toBeCloseTo(1, 6);

    store.getState().setOfflineReplayPlaybackRate(2);
    store.getState().advanceOfflineReplay(1);
    expect(store.getState().offlineReplay.currentTime - single).toBeCloseTo(2, 6);
  });

  it('moves the frame the rest of the app reads', () => {
    const samples = lapSamples(200);
    play(samples);
    store.getState().advanceOfflineReplay(3);
    const { currentIndex, currentSample } = store.getState().offlineReplay;
    expect(currentIndex).toBe(30);
    expect(store.getState().latestFrame).toBe(samples[30]);
    expect(currentSample).toBe(samples[30]);
    expect(store.getState().globalCursorS).toBeCloseTo(samples[30].s, 6);
  });

  it('stops at the end of the lap instead of running past it', () => {
    play(lapSamples(50));
    store.getState().advanceOfflineReplay(30);
    const replay = store.getState().offlineReplay;
    expect(replay.playing).toBe(false);
    expect(replay.currentTime).toBeCloseTo(replay.duration, 6);
    expect(replay.currentIndex).toBe(49);
  });

  it('starts the lap over when play is pressed at the end', () => {
    play(lapSamples(50));
    store.getState().advanceOfflineReplay(30);
    store.getState().setOfflineReplayPlaying(true);
    const replay = store.getState().offlineReplay;
    expect(replay.playing).toBe(true);
    expect(replay.currentTime).toBe(0);
    expect(replay.currentIndex).toBe(0);
  });

  it('stays where it is while paused', () => {
    play(lapSamples(200));
    store.getState().advanceOfflineReplay(2);
    const before = store.getState().offlineReplay.currentTime;
    store.getState().setOfflineReplayPlaying(false);
    store.getState().advanceOfflineReplay(5);
    expect(store.getState().offlineReplay.playing).toBe(false);
    expect(store.getState().offlineReplay.currentTime).toBeCloseTo(before, 6);
  });

  it('ignores a tick that carries no time', () => {
    play(lapSamples(200));
    const before = store.getState().offlineReplay.currentTime;
    store.getState().advanceOfflineReplay(0);
    store.getState().advanceOfflineReplay(-3);
    store.getState().advanceOfflineReplay(NaN);
    expect(store.getState().offlineReplay.currentTime).toBe(before);
  });

  it('does nothing at all when no replay is loaded', () => {
    store.getState().advanceOfflineReplay(1);
    store.getState().setOfflineReplayIndex(4);
    expect(store.getState().offlineReplay.active).toBe(false);
    expect(store.getState().viewMode).not.toBe('replay');
  });
});

describe('scrubbing the replay', () => {
  it('lands on the sample nearest the time asked for', () => {
    play(lapSamples(200));
    store.getState().setOfflineReplayTime(5.04);
    expect(store.getState().offlineReplay.currentIndex).toBe(50);
    store.getState().setOfflineReplayTime(5.07);
    expect(store.getState().offlineReplay.currentIndex).toBe(51);
  });

  it('cannot be dragged outside the lap', () => {
    play(lapSamples(50));
    const { duration } = store.getState().offlineReplay;

    store.getState().setOfflineReplayTime(-12);
    expect(store.getState().offlineReplay.currentTime).toBe(0);
    expect(store.getState().offlineReplay.currentIndex).toBe(0);

    store.getState().setOfflineReplayTime(900);
    expect(store.getState().offlineReplay.currentTime).toBeCloseTo(duration, 6);
    // Dragging to the end stops it, the same as playing to the end.
    expect(store.getState().offlineReplay.playing).toBe(false);
  });

  it('clamps a frame step to the lap it has', () => {
    play(lapSamples(50));
    store.getState().setOfflineReplayIndex(-5);
    expect(store.getState().offlineReplay.currentIndex).toBe(0);
    store.getState().setOfflineReplayIndex(999);
    expect(store.getState().offlineReplay.currentIndex).toBe(49);
    expect(store.getState().offlineReplay.playing).toBe(false);
  });

  it('keeps the lap timing in step with the frame on screen', () => {
    const reference = lapSamples(200, { lapNumber: 6 });
    play(lapSamples(200), { referenceSamples: reference, referenceLapNumber: 6 });
    store.getState().setOfflineReplayIndex(80);
    expect(store.getState().lapMetrics.currentLapTime).toBeCloseTo(8, 6);
    expect(store.getState().lapMetrics.currentLapNumber).toBe(7);
    expect(store.getState().lapMetrics.referenceLapNumber).toBe(6);
  });

  it('holds the playback rate inside what the player can do', () => {
    play(lapSamples(50));
    store.getState().setOfflineReplayPlaybackRate(99);
    expect(store.getState().offlineReplay.playbackRate).toBe(4);
    store.getState().setOfflineReplayPlaybackRate(0.01);
    expect(store.getState().offlineReplay.playbackRate).toBe(0.25);
    store.getState().setOfflineReplayPlaybackRate('rapido' as any);
    expect(store.getState().offlineReplay.playbackRate).toBe(1);
  });
});

describe('leaving the replay', () => {
  it('goes back to live and forgets the lap', () => {
    play(lapSamples(50));
    store.getState().clearOfflineReplay();
    const state = store.getState();
    expect(state.viewMode).toBe('live');
    expect(state.offlineReplay.active).toBe(false);
    expect(state.offlineReplay.samples).toEqual([]);
    expect(state.selectedLap).toBeNull();
    expect(state.selectedSessionId).toBeNull();
    expect(state.globalCursorS).toBeNull();
  });

  it('can load another lap straight after', () => {
    play(lapSamples(50, { lapNumber: 7 }));
    store.getState().advanceOfflineReplay(2);
    const second = lapSamples(80, { lapNumber: 9 });
    play(second, { lapId: 'lap-2', lapNumber: 9 });
    const replay = store.getState().offlineReplay;
    expect(replay.lapNumber).toBe(9);
    expect(replay.currentIndex).toBe(0);
    expect(replay.currentTime).toBe(0);
    expect(replay.sampleCount).toBe(80);
  });
});

describe('coaching over a replayed lap', () => {
  /** Events as the backend returns them, tagged with when in the lap they fall. */
  const coaching = (...seconds: number[]) => seconds.map((at, index) => ({
    type: 'coaching_event',
    event: `perda no setor ${index}`,
    severity: 0.5,
    evidence: { atLapTimeSeconds: at, microsector: index, lossSeconds: 0.3 },
    driver_id: 'dokas',
    lap_number: 7,
    s: at * 50,
    timestamp: 1,
  }));

  it('says nothing before the car reaches the corner', () => {
    play(lapSamples(200), { coachEvents: coaching(4, 9, 14) });
    expect(store.getState().coachingEvents).toEqual([]);
  });

  it('speaks each event as the replay drives past it', () => {
    play(lapSamples(200), { coachEvents: coaching(4, 9, 14) });
    store.getState().setOfflineReplayTime(5);
    expect(store.getState().coachingEvents.length).toBe(1);
    store.getState().setOfflineReplayTime(10);
    expect(store.getState().coachingEvents.length).toBe(2);
    store.getState().setOfflineReplayTime(19.9);
    expect(store.getState().coachingEvents.length).toBe(3);
  });

  it('carries the event through, not a placeholder', () => {
    play(lapSamples(200), { coachEvents: coaching(4) });
    store.getState().setOfflineReplayTime(5);
    const [event] = store.getState().coachingEvents;
    expect(event.event).toContain('perda no setor 0');
    expect(event.severity).toBeCloseTo(0.5, 5);
  });

  it('releases them while playing, not only while scrubbing', () => {
    play(lapSamples(200), { coachEvents: coaching(2, 6) });
    store.getState().advanceOfflineReplay(7);
    expect(store.getState().coachingEvents.length).toBe(2);
  });

  it('says them again after the slider goes back', () => {
    // Dragging back and playing again has to replay the commentary too;
    // swallowing it would make the second watch quieter than the first.
    //
    // This asserted two events at the end, which is the same event twice: the
    // feed was appended to on the second pass instead of rebuilt. Watching a
    // lap three times showed each corner three times. The commentary still
    // plays again -- the event below is released a second time -- it just does
    // not stack.
    play(lapSamples(200), { coachEvents: coaching(3) });
    store.getState().setOfflineReplayTime(5);
    expect(store.getState().coachingEvents.length).toBe(1);
    store.getState().setOfflineReplayTime(0);
    expect(store.getState().offlineReplay.coachEmittedCount).toBe(0);
    expect(store.getState().coachingEvents).toEqual([]);
    store.getState().setOfflineReplayTime(5);
    expect(store.getState().coachingEvents.length).toBe(1);
    expect(store.getState().offlineReplay.coachEmittedCount).toBe(1);
  });

  it('a lap with no coaching plays exactly as before', () => {
    play(lapSamples(200));
    store.getState().advanceOfflineReplay(5);
    expect(store.getState().coachingEvents).toEqual([]);
    expect(store.getState().offlineReplay.coachEvents).toEqual([]);
  });

  it('forgets the previous lap when another replay starts', () => {
    play(lapSamples(200), { coachEvents: coaching(2) });
    store.getState().setOfflineReplayTime(5);
    play(lapSamples(200), { coachEvents: coaching(3) });
    expect(store.getState().offlineReplay.coachEmittedCount).toBe(0);
    expect(store.getState().offlineReplay.coachEvents.length).toBe(1);
    // And the panel, not only the replay's own copy: the feed used to keep the
    // previous lap's events above the new lap's.
    expect(store.getState().coachingEvents).toEqual([]);
  });

  /**
   * Watching the same lap twice.
   *
   * The clock re-counts from the start of the lap on every move, so a rewind
   * makes it say everything again. The feed has to start over when that
   * happens -- six events became twelve on the second run, then eighteen.
   */
  it('does not stack a second copy when the lap is replayed', () => {
    play(lapSamples(200), { coachEvents: coaching(4, 9, 14) });
    store.getState().setOfflineReplayTime(19.9);
    expect(store.getState().coachingEvents.length).toBe(3);

    store.getState().setOfflineReplayTime(0);
    expect(store.getState().coachingEvents).toEqual([]);

    store.getState().setOfflineReplayTime(19.9);
    expect(store.getState().coachingEvents.length).toBe(3);
  });

  it('does not stack when scrubbing back over an event and forward again', () => {
    play(lapSamples(200), { coachEvents: coaching(4, 9) });
    store.getState().setOfflineReplayTime(10);
    expect(store.getState().coachingEvents.length).toBe(2);

    store.getState().setOfflineReplayTime(6);   // atras do segundo evento
    expect(store.getState().coachingEvents.length).toBe(1);

    store.getState().setOfflineReplayTime(10);
    expect(store.getState().coachingEvents.length).toBe(2);
  });

  it('keeps what it has said while the lap only moves forward', () => {
    play(lapSamples(200), { coachEvents: coaching(4, 9) });
    store.getState().setOfflineReplayTime(5);
    store.getState().setOfflineReplayTime(6);
    store.getState().setOfflineReplayTime(7);
    expect(store.getState().coachingEvents.length).toBe(1);
  });
});
