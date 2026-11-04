function selection_datum(value) {
  return arguments.length
      ? this.property("__data__", value)
      : this.node().__data__;
}

export { selection_datum as default };
//# sourceMappingURL=datum.js.map
