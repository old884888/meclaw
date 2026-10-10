/**
 * A05 · Modal Sheet
 * Reusable glass modal enter/exit animation.
 */
(function registerA05() {
  const DURATION = 300;
  const EASING = "cubic-bezier(0.22, 0.78, 0.18, 1)";

  function panelOf(modal) {
    if (!modal) return null;
    return modal.querySelector(".modal-panel");
  }

  function cleanup(modal, panel) {
    if (!modal) return;
    modal.classList.remove("is-modal-animating");
    modal.style.opacity = "";
    modal.style.transition = "";
    if (!panel) return;
    panel.style.opacity = "";
    panel.style.transform = "";
    panel.style.transition = "";
    panel.style.willChange = "";
  }

  function runEnter(modal) {
    const panel = panelOf(modal);
    if (!panel) return Promise.resolve(false);
    modal.classList.remove("hidden");
    modal.classList.add("is-modal-animating");
    modal.style.opacity = "0";
    modal.style.transition = `opacity ${DURATION}ms ${EASING}`;
    panel.style.willChange = "opacity, transform";
    panel.style.opacity = "0";
    panel.style.transform = "translateY(22px) scale(0.965)";
    panel.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        modal.style.opacity = "1";
        panel.style.opacity = "1";
        panel.style.transform = "translateY(0) scale(1)";
      });
    });

    return Promise.all([
      AnimEngine.waitTransition(modal, "opacity", DURATION),
      AnimEngine.waitTransition(panel, "transform", DURATION),
    ]).then(() => {
      cleanup(modal, panel);
      return true;
    });
  }

  function runExit(modal) {
    const panel = panelOf(modal);
    if (!panel) {
      modal?.classList.add("hidden");
      return Promise.resolve(false);
    }
    modal.classList.add("is-modal-animating");
    modal.style.opacity = "1";
    modal.style.transition = `opacity ${DURATION}ms ${EASING}`;
    panel.style.willChange = "opacity, transform";
    panel.style.opacity = "1";
    panel.style.transform = "translateY(0) scale(1)";
    panel.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    requestAnimationFrame(() => {
      modal.style.opacity = "0";
      panel.style.opacity = "0";
      panel.style.transform = "translateY(16px) scale(0.975)";
    });

    return Promise.all([
      AnimEngine.waitTransition(modal, "opacity", DURATION),
      AnimEngine.waitTransition(panel, "transform", DURATION),
    ]).then(() => {
      modal.classList.add("hidden");
      cleanup(modal, panel);
      return true;
    });
  }

  AnimEngine.register("A05", {
    id: "A05",
    name: "modal-sheet",
    duration: DURATION,

    run(element, action) {
      if (!element || (action !== "enter" && action !== "exit")) return Promise.resolve(false);
      return action === "enter" ? runEnter(element) : runExit(element);
    },

    reduced(element, action) {
      if (!element || (action !== "enter" && action !== "exit")) return false;
      if (action === "enter") element.classList.remove("hidden");
      else element.classList.add("hidden");
      cleanup(element, panelOf(element));
      return true;
    },
  });
})();
