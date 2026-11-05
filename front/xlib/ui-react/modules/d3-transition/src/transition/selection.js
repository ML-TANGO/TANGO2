import selection from '../../../d3-selection/src/selection/index.js';
import '../../../d3-selection/src/local.js';

var Selection = selection.prototype.constructor;

function transition_selection() {
  return new Selection(this._groups, this._parents);
}

export { transition_selection as default };
//# sourceMappingURL=selection.js.map
