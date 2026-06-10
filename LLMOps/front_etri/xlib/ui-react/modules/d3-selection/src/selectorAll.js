function empty() {
  return [];
}

function selectorAll(selector) {
  return selector == null ? empty : function() {
    return this.querySelectorAll(selector);
  };
}

export { selectorAll as default };
//# sourceMappingURL=selectorAll.js.map
