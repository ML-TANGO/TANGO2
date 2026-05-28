import interrupt from '../interrupt.js';

function selection_interrupt(name) {
  return this.each(function() {
    interrupt(this, name);
  });
}

export { selection_interrupt as default };
//# sourceMappingURL=interrupt.js.map
