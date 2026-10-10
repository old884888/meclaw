/**
 * A01 · Panel Expand / Collapse
 * Height + opacity transition for .anim-panel regions (detail slot, etc.).
 */
(function registerA01() {
  const DURATION = 340;
  const EASING = "cubic-bezier(0.32, 0.72, 0, 1)";

  function panelOf(el) {
    if (!el) return null;
    if (el.classList.contains("anim-panel")) return el;
    return el.querySelector(".anim-panel");
  }

  function hostOf(panel) {
    return panel?.closest(".anim-panel-host") || panel?.parentElement || null;
  }

  function finish(panel, cleanup) {
    if (!panel) return;
    if (cleanup) {
      panel.style.height = "";
      panel.style.opacity = "";
      panel.style.overflow = "";
      panel.style.transition = "";
    }
    panel.classList.remove("is-animating");
    hostOf(panel)?.classList.remove("is-animating");
  }

  AnimEngine.register("A01", {
    id: "A01",
    name: "panel-expand",
    duration: DURATION,

    run(element, action) {
      const panel = panelOf(element);
      if (!panel) return Promise.resolve(false);
      const host = hostOf(panel);

      return new Promise((resolve) => {
        panel.classList.add("is-animating");
        host?.classList.add("is-animating");

        if (action === "expand") {
          panel.hidden = false;
          panel.classList.add("is-expanded");
          panel.style.overflow = "hidden";
          panel.style.height = "0px";
          panel.style.opacity = "0";
          panel.style.transition = `height ${DURATION}ms ${EASING}, opacity ${Math.round(DURATION * 0.9)}ms ease`;

          requestAnimationFrame(() => {
            panel.style.height = `${panel.scrollHeight}px`;
            panel.style.opacity = "1";
          });

          const onEnd = () => {
            finish(panel, true);
            resolve(true);
          };
          panel.addEventListener("transitionend", onEnd, { once: true });
          setTimeout(onEnd, DURATION + 80);
          return;
        }

        if (action === "collapse") {
          panel.style.overflow = "hidden";
          panel.style.height = `${panel.scrollHeight}px`;
          panel.style.opacity = "1";
          panel.style.transition = `height ${DURATION}ms ${EASING}, opacity ${Math.round(DURATION * 0.75)}ms ease`;

          requestAnimationFrame(() => {
            panel.style.height = "0px";
            panel.style.opacity = "0";
          });

          const onEnd = () => {
            panel.hidden = true;
            panel.classList.remove("is-expanded");
            finish(panel, true);
            resolve(true);
          };
          panel.addEventListener("transitionend", onEnd, { once: true });
          setTimeout(onEnd, DURATION + 80);
          return;
        }

        finish(panel, true);
        resolve(false);
      });
    },

    reduced(element, action) {
      const panel = panelOf(element);
      if (!panel) return false;
      if (action === "expand") {
        panel.hidden = false;
        panel.classList.add("is-expanded");
      } else {
        panel.hidden = true;
        panel.classList.remove("is-expanded");
      }
      panel.classList.remove("is-animating");
      hostOf(panel)?.classList.remove("is-animating");
      return true;
    },
  });
})();
