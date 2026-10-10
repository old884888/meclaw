/**
 * A04 · Screen Transition
 * Full-view crossfade + slide for home ↔ chat (and other .anim-screen views).
 */
(function registerA04() {
  const DURATION = 360;
  const EASING = "cubic-bezier(0.32, 0.72, 0, 1)";

  function cleanup(element) {
    if (!element) return;
    element.style.opacity = "";
    element.style.transform = "";
    element.style.transition = "";
    element.style.willChange = "";
    element.classList.remove("is-animating");
  }

  function directionOf(options = {}) {
    return options.direction === "back" ? "back" : "forward";
  }

  function runEnter(element, options = {}) {
    const forward = directionOf(options) === "forward";
    element.classList.remove("hidden");
    element.classList.add("is-animating");
    element.style.willChange = "opacity, transform";
    element.style.opacity = "0";
    element.style.transform = forward ? "translateX(28px)" : "translateX(-28px)";
    element.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          element.style.opacity = "1";
          element.style.transform = "translateX(0)";
        });
      });
      AnimEngine.waitTransition(element, "transform", DURATION).then(() => {
        cleanup(element);
        resolve(true);
      });
    });
  }

  function runExit(element, options = {}) {
    const forward = directionOf(options) === "forward";
    element.classList.add("is-animating");
    element.style.willChange = "opacity, transform";
    element.style.opacity = "1";
    element.style.transform = "translateX(0)";
    element.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        element.style.opacity = "0";
        element.style.transform = forward ? "translateX(-24px) scale(0.985)" : "translateX(24px) scale(0.985)";
      });
      AnimEngine.waitTransition(element, "transform", DURATION).then(() => {
        cleanup(element);
        element.classList.add("hidden");
        resolve(true);
      });
    });
  }

  AnimEngine.register("A04", {
    id: "A04",
    name: "screen-transition",
    duration: DURATION,

    run(element, action, options = {}) {
      if (!element || (action !== "enter" && action !== "exit")) return Promise.resolve(false);
      return action === "enter" ? runEnter(element, options) : runExit(element, options);
    },

    reduced(element, action) {
      if (!element) return false;
      if (action === "enter") element.classList.remove("hidden");
      else element.classList.add("hidden");
      cleanup(element);
      return true;
    },
  });
})();
