function selection_call() {
  var callback = arguments[0];
  arguments[0] = this;
  callback.apply(null, arguments);
  return this;
}

export { selection_call as default };
//# sourceMappingURL=call.js.map
