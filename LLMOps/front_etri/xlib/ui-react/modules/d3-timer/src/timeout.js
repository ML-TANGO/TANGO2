import { Timer } from './timer.js';

function timeout(callback, delay, time) {
  var t = new Timer;
  delay = delay == null ? 0 : +delay;
  t.restart(elapsed => {
    t.stop();
    callback(elapsed + delay);
  }, delay, time);
  return t;
}

export { timeout as default };
//# sourceMappingURL=timeout.js.map
