function remove() {
  var parent = this.parentNode;
  if (parent) parent.removeChild(this);
}

function selection_remove() {
  return this.each(remove);
}

export { selection_remove as default };
//# sourceMappingURL=remove.js.map
