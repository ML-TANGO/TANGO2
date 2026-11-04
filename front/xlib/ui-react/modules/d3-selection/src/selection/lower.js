function lower() {
  if (this.previousSibling) this.parentNode.insertBefore(this, this.parentNode.firstChild);
}

function selection_lower() {
  return this.each(lower);
}

export { selection_lower as default };
//# sourceMappingURL=lower.js.map
