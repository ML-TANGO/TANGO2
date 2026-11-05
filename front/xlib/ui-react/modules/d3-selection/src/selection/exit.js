import sparse from './sparse.js';
import { Selection } from './index.js';

function selection_exit() {
  return new Selection(this._exit || this._groups.map(sparse), this._parents);
}

export { selection_exit as default };
//# sourceMappingURL=exit.js.map
