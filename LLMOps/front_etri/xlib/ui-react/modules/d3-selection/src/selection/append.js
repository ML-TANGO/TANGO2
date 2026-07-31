import creator from '../creator.js';

function selection_append(name) {
  var create = typeof name === "function" ? name : creator(name);
  return this.select(function() {
    return this.appendChild(create.apply(this, arguments));
  });
}

export { selection_append as default };
//# sourceMappingURL=append.js.map
