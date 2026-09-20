// Active elapsed time only. Provider/network time never belongs to the child.
export function answerClock(now = () => performance.now()) {
  let started = now(), excluded = 0, paused = null;
  return {
    reset() { started = now(); excluded = 0; paused = null; },
    pause() { if (paused === null) paused = now(); },
    resume() { if (paused !== null) { excluded += now() - paused; paused = null; } },
    seconds() { return Math.min(3600, Math.max(0, Math.round(((paused ?? now()) - started - excluded) / 1000))); }
  };
}
