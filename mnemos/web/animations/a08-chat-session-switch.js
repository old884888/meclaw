/**
 * A08 · Chat Session Switch
 * Crossfade + slide for #view-chat when switching sidebar sessions.
 */
(function registerA08() {
  const DURATION = 260;
  const EASING = "cubic-bezier(0.32, 0.72, 0, 1)";

  function cleanup(el) {
    if (!el) return;
    el.classList.remove("is-animating");
    el.style.opacity = "";
    el.style.transform = "";
    el.style.transition = "";
    el.style.willChange = "";
    el.style.pointerEvents = "";
  }

  function runEnter(el) {
    if (!el) return Promise.resolve(false);
    el.classList.add("is-animating");
    el.style.pointerEvents = "none";
    el.style.willChange = "opacity, transform";
    el.style.opacity = "0";
    el.style.transform = "translateX(16px)";
    el.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.style.opacity = "1";
          el.style.transform = "translateX(0)";
        });
      });
      AnimEngine.waitTransition(el, "transform", DURATION).then(() => {
        cleanup(el);
        resolve(true);
      });
    });
  }

  function runExit(el) {
    if (!el) return Promise.resolve(false);
    el.classList.add("is-animating");
    el.style.pointerEvents = "none";
    el.style.willChange = "opacity, transform";
    el.style.opacity = "1";
    el.style.transform = "translateX(0)";
    el.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        el.style.opacity = "0";
        el.style.transform = "translateX(-12px)";
      });
      AnimEngine.waitTransition(el, "transform", DURATION).then(() => {
        cleanup(el);
        resolve(true);
      });
    });
  }

  AnimEngine.register("A08", {
    id: "A08",
    name: "chat-session-switch",
    duration: DURATION,

    run(element, action) {
      if (!element || (action !== "enter" && action !== "exit")) return Promise.resolve(false);
      return action === "enter" ? runEnter(element) : runExit(element);
    },

    reduced(element, action) {
      if (!element || (action !== "enter" && action !== "exit")) return false;
      cleanup(element);
      return true;
    },
  });
})();
