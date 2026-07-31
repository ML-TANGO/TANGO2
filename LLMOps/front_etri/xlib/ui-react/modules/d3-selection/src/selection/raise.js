function raise() {
  if (this.nextSibling) this.parentNode.appendChild(this);
}

function selection_raise() {
  return this.each(raise);
}

export { selection_raise as default };
//# sourceMappingURL=raise.js.map
