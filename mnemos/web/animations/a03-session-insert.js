/**
 * A03 · Item Reveal
 * enter / exit for vertical list rows (.session-item) and grid cards (.bot-tile).
 */
(function registerA03() {
  const DURATION = 320;
  const EASING = "cubic-bezier(0.32, 0.72, 0, 1)";

  function variantOf(element, options = {}) {
    if (options.variant === "list" || options.variant === "card") return options.variant;
    if (element?.classList.contains("bot-tile")) return "card";
    return "list";
  }

  function finish(el, cleanup) {
    if (!el) return;
    if (cleanup) {
      el.style.height = "";
      el.style.maxHeight = "";
      el.style.marginBottom = "";
      el.style.paddingTop = "";
      el.style.paddingBottom = "";
      el.style.opacity = "";
      el.style.transform = "";
      el.style.overflow = "";
      el.style.transition = "";
      el.style.transformOrigin = "";
      el.style.willChange = "";
    }
    el.classList.remove("is-animating");
  }

  function prepAnimating(el) {
    el.classList.add("is-animating");
    el.style.willChange = "opacity, transform";
  }

  function runListEnter(element) {
    prepAnimating(element);
    element.style.overflow = "hidden";
    element.style.height = "0px";
    element.style.opacity = "0";
    element.style.transform = "translateY(-10px)";
    element.style.transition = `height ${DURATION}ms ${EASING}, opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    requestAnimationFrame(() => {
      element.style.height = `${element.scrollHeight}px`;
      element.style.opacity = "1";
      element.style.transform = "translateY(0)";
    });

    return AnimEngine.waitTransition(element, "height", DURATION).then(() => {
      finish(element, true);
      element.classList.add("is-entered");
      return true;
    });
  }

  function runListExit(element) {
    const EXIT_MS = 300;
    const list = element.parentElement;
    if (!list) return Promise.resolve(false);

    const height = element.getBoundingClientRect().height;
    const marginBottom = parseFloat(getComputedStyle(element).marginBottom) || 0;
    const total = height + marginBottom;
    const top = element.offsetTop;
    const left = element.offsetLeft;
    const width = element.offsetWidth;

    const placeholder = document.createElement("div");
    placeholder.className = "session-item-spacer";
    placeholder.style.height = `${total}px`;
    placeholder.style.overflow = "hidden";
    placeholder.style.transition = `height ${EXIT_MS}ms ${EASING}`;

    list.insertBefore(placeholder, element);

    prepAnimating(element);
    element.style.position = "absolute";
    element.style.top = `${top}px`;
    element.style.left = `${left}px`;
    element.style.width = `${width}px`;
    element.style.margin = "0";
    element.style.zIndex = "2";
    element.style.pointerEvents = "none";
    element.style.transformOrigin = "center top";
    element.style.opacity = "1";
    element.style.transform = "translateY(0) scale(1)";
    element.style.transition = `opacity ${EXIT_MS}ms ${EASING}, transform ${EXIT_MS}ms ${EASING}`;

    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          element.style.opacity = "0";
          element.style.transform = "translateY(-6px) scale(0.98)";
          placeholder.style.height = "0px";
        });
      });

      Promise.all([
        AnimEngine.waitTransition(element, "opacity", EXIT_MS),
        AnimEngine.waitTransition(placeholder, "height", EXIT_MS),
      ]).then(() => {
        element.remove();
        placeholder.remove();
        resolve(true);
      });
    });
  }

  function runCardEnter(element) {
    prepAnimating(element);
    element.style.overflow = "hidden";
    element.style.transformOrigin = "center center";
    element.style.opacity = "0";
    element.style.transform = "scale(0.92) translateY(10px)";
    element.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    requestAnimationFrame(() => {
      element.style.opacity = "1";
      element.style.transform = "scale(1) translateY(0)";
    });

    return AnimEngine.waitTransition(element, "transform", DURATION).then(() => {
      finish(element, true);
      element.classList.add("is-entered");
      return true;
    });
  }

  function runCardExit(element) {
    prepAnimating(element);
    element.style.overflow = "hidden";
    element.style.transformOrigin = "center center";
    element.style.opacity = "1";
    element.style.transform = "scale(1) translateY(0)";
    element.style.transition = `opacity ${DURATION}ms ${EASING}, transform ${DURATION}ms ${EASING}`;

    requestAnimationFrame(() => {
      element.style.opacity = "0";
      element.style.transform = "scale(0.92) translateY(-8px)";
    });

    return AnimEngine.waitTransition(element, "transform", DURATION).then(() => {
      finish(element, true);
      element.classList.remove("is-entered");
      return true;
    });
  }

  AnimEngine.register("A03", {
    id: "A03",
    name: "item-reveal",
    duration: DURATION,

    run(element, action, options = {}) {
      if (!element || (action !== "enter" && action !== "exit")) return Promise.resolve(false);
      const variant = variantOf(element, options);
      if (action === "enter") {
        return variant === "card" ? runCardEnter(element) : runListEnter(element);
      }
      return variant === "card" ? runCardExit(element) : runListExit(element);
    },

    reduced(element, action) {
      if (!element || (action !== "enter" && action !== "exit")) return false;
      if (action === "enter") element.classList.add("is-entered");
      else element.classList.remove("is-entered");
      finish(element, true);
      return true;
    },
  });
})();
