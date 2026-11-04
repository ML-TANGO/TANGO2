function matcher(selector) {
  return function() {
    return this.matches(selector);
  };
}

function childMatcher(selector) {
  return function(node) {
    return node.matches(selector);
  };
}

export { childMatcher, matcher as default };
//# sourceMappingURL=matcher.js.map
