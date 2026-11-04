import { rgb } from '../../d3-color/src/color.js';
import '../../d3-color/src/lab.js';
import '../../d3-color/src/cubehelix.js';
import nogamma, { gamma } from './color.js';

var interpolateRgb = (function rgbGamma(y) {
  var color = gamma(y);

  function rgb$1(start, end) {
    var r = color((start = rgb(start)).r, (end = rgb(end)).r),
        g = color(start.g, end.g),
        b = color(start.b, end.b),
        opacity = nogamma(start.opacity, end.opacity);
    return function(t) {
      start.r = r(t);
      start.g = g(t);
      start.b = b(t);
      start.opacity = opacity(t);
      return start + "";
    };
  }

  rgb$1.gamma = rgbGamma;

  return rgb$1;
})(1);

export { interpolateRgb as default };
//# sourceMappingURL=rgb.js.map
