/**
 * A07 · Settings Tab
 * Smooth enter/exit for settings tab content.
 */
(function registerA07() {
  const DURATION = 220;
  const EASING = "cubic-bezier(0.22, 0.82, 0.2, 1)";

  function cleanup(el) {
    if (!el) return;
    el.classList.remove("is-tab-animating");
    el.style.opacity = "";
    el.style.transform = "";
    el.style.transition = "";
    el.style.willChange = "";
  }

  function runEnter(el) {
    if (!el) return Promise.resolve(false);
    el.classList.remove("hidden");
    el.classList.add("is-tab-animating");
    el.style.willChange = "opacity, transform";
    el.style.opacity = "0";
    el.style.transform = "translateY(10px)";
    el.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    requestAnimationFrame(() => {
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    });

    return Promise.all([
      AnimEngine.waitTransition(el, "opacity", DURATION),
      AnimEngine.waitTransition(el, "transform", DURATION),
    ]).then(() => {
      cleanup(el);
      return true;
    });
  }

  function runExit(el) {
    if (!el) return Promise.resolve(false);
    el.classList.add("is-tab-animating");
    el.style.willChange = "opacity, transform";
    el.style.opacity = "1";
    el.style.transform = "translateY(0)";
    el.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    requestAnimationFrame(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(-6px)";
    });

    return Promise.all([
      AnimEngine.waitTransition(el, "opacity", DURATION),
      AnimEngine.waitTransition(el, "transform", DURATION),
    ]).then(() => {
      el.classList.add("hidden");
      cleanup(el);
      return true;
    });
  }

  AnimEngine.register("A07", {
    id: "A07",
    name: "settings-tab",
    duration: DURATION,

    run(element, action) {
      if (!element || (action !== "enter" && action !== "exit")) return Promise.resolve(false);
      return action === "enter" ? runEnter(element) : runExit(element);
    },

    reduced(element, action) {
      if (!element || (action !== "enter" && action !== "exit")) return false;
      if (action === "enter") element.classList.remove("hidden");
      else element.classList.add("hidden");
      cleanup(element);
      return true;
    },
  });
})();
