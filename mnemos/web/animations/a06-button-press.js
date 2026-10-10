/**
 * A06 · Button Press
 * Reusable micro interaction for button clicks.
 */
(function registerA06() {
  const DURATION = 180;
  const EASING = "cubic-bezier(0.2, 0.9, 0.25, 1)";

  function runPress(element) {
    if (!element) return Promise.resolve(false);

    // Prefer WAAPI to avoid clobbering existing inline styles.
    if (typeof element.animate === "function") {
      const animation = element.animate(
        [
          { transform: "scale(1)", filter: "brightness(1)" },
          { transform: "scale(0.94)", filter: "brightness(0.96)", offset: 0.48 },
          { transform: "scale(1)", filter: "brightness(1)" },
        ],
        {
          duration: DURATION,
          easing: EASING,
          fill: "none",
        }
      );
      return animation.finished.then(() => true).catch(() => true);
    }

    element.style.transition = `transform ${DURATION}ms ${EASING}`;
    element.style.transform = "scale(0.94)";
    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          element.style.transform = "scale(1)";
          AnimEngine.waitTransition(element, "transform", DURATION).then(() => {
            element.style.transition = "";
            element.style.transform = "";
            resolve(true);
          });
        });
      });
    });
  }

  AnimEngine.register("A06", {
    id: "A06",
    name: "button-press",
    duration: DURATION,
    run(element, action) {
      if (action !== "tap") return Promise.resolve(false);
      return runPress(element);
    },
    reduced(_, action) {
      return action === "tap";
    },
  });
})();
