import color from '../../../d3-color/src/color.js';
import '../../../d3-color/src/lab.js';
import '../../../d3-color/src/cubehelix.js';
import interpolateRgb from '../../../d3-interpolate/src/rgb.js';
import interpolateNumber from '../../../d3-interpolate/src/number.js';
import interpolateString from '../../../d3-interpolate/src/string.js';
import '../../../d3-interpolate/src/zoom.js';
import '../../../d3-interpolate/src/cubehelix.js';

function interpolate(a, b) {
  var c;
  return (typeof b === "number" ? interpolateNumber
      : b instanceof color ? interpolateRgb
      : (c = color(b)) ? (b = c, interpolateRgb)
      : interpolateString)(a, b);
}

export { interpolate as default };
//# sourceMappingURL=interpolate.js.map
