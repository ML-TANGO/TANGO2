function interpolateNumber(a, b) {
  return a = +a, b = +b, function(t) {
    return a * (1 - t) + b * t;
  };
}

export { interpolateNumber as default };
//# sourceMappingURL=number.js.map
