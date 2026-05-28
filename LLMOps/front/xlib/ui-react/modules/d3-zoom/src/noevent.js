function nopropagation(event) {
  event.stopImmediatePropagation();
}

function noevent(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
}

export { noevent as default, nopropagation };
//# sourceMappingURL=noevent.js.map
