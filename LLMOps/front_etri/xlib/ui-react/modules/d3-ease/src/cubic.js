function cubicInOut(t) {
  return ((t *= 2) <= 1 ? t * t * t : (t -= 2) * t * t + 2) / 2;
}

export { cubicInOut };
//# sourceMappingURL=cubic.js.map
