function sourceEvent(event) {
  let sourceEvent;
  while (sourceEvent = event.sourceEvent) event = sourceEvent;
  return event;
}

export { sourceEvent as default };
//# sourceMappingURL=sourceEvent.js.map
