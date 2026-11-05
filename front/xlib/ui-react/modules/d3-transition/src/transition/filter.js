import '../../../d3-selection/src/selection/index.js';
import '../../../d3-selection/src/local.js';
import matcher from '../../../d3-selection/src/matcher.js';
import { Transition } from './index.js';

function transition_filter(match) {
  if (typeof match !== "function") match = matcher(match);

  for (var groups = this._groups, m = groups.length, subgroups = new Array(m), j = 0; j < m; ++j) {
    for (var group = groups[j], n = group.length, subgroup = subgroups[j] = [], node, i = 0; i < n; ++i) {
      if ((node = group[i]) && match.call(node, node.__data__, i, group)) {
        subgroup.push(node);
      }
    }
  }

  return new Transition(subgroups, this._parents, this._name, this._id);
}

export { transition_filter as default };
//# sourceMappingURL=filter.js.map
