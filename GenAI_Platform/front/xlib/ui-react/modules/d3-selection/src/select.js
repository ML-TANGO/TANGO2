import { Selection, root } from './selection/index.js';

function select(selector) {
  return typeof selector === "string"
      ? new Selection([[document.querySelector(selector)]], [document.documentElement])
      : new Selection([[selector]], root);
}

export { select as default };
//# sourceMappingURL=select.js.map
