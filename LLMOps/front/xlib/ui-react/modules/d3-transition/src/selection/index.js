import selection from '../../../d3-selection/src/selection/index.js';
import '../../../d3-selection/src/local.js';
import selection_interrupt from './interrupt.js';
import selection_transition from './transition.js';

selection.prototype.interrupt = selection_interrupt;
selection.prototype.transition = selection_transition;
//# sourceMappingURL=index.js.map
