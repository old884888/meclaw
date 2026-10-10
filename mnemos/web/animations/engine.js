/**
 * MNEMOS Animation Engine
 * Register animations by ID (A01, A02, ...) and invoke via AnimEngine.run().
 */
const AnimEngine = {
  registry: new Map(),

  register(id, impl) {
    this.registry.set(String(id).toUpperCase(), impl);
  },

  get(id) {
    return this.registry.get(String(id).toUpperCase()) || null;
  },

  prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  },

  run(id, element, action, options = {}) {
    const impl = this.get(id);
    if (!impl || !element) return Promise.resolve(false);
    if (this.prefersReducedMotion() && typeof impl.reduced === "function") {
      return Promise.resolve(impl.reduced(element, action, options));
    }
    if (typeof impl.run === "function") {
      return Promise.resolve(impl.run(element, action, options));
    }
    return Promise.resolve(false);
  },

  /** Wait for a specific CSS transition property (avoids multi-property transitionend firing too early). */
  waitTransition(element, propertyName, durationMs) {
    return new Promise((resolve) => {
      if (!element) {
        resolve();
        return;
      }
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        element.removeEventListener("transitionend", onEnd);
        resolve();
      };
      const onEnd = (ev) => {
        if (ev.target !== element) return;
        if (!propertyName || ev.propertyName === propertyName) finish();
      };
      element.addEventListener("transitionend", onEnd);
      setTimeout(finish, durationMs + 64);
    });
  },
};

window.AnimEngine = AnimEngine;
