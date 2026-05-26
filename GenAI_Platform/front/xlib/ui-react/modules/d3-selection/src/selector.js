function none() {}

function selector(selector) {
  return selector == null ? none : function() {
    return this.querySelector(selector);
  };
}

export { selector as default };
//# sourceMappingURL=selector.js.map
