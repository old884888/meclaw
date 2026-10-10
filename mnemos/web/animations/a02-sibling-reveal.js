/**
 * A02 · Grid Focus
 * When one card opens a detail panel, sibling cards gently dim (no layout reflow).
 */
(function registerA02() {
  const DURATION = 280;

  function cards(container, options = {}) {
    if (!container) return [];
    const active = options.active || null;
    return [...container.querySelectorAll(".note-card-expandable")].filter((card) => card !== active);
  }

  AnimEngine.register("A02", {
    id: "A02",
    name: "grid-focus",
    duration: DURATION,

    run(container, action, options = {}) {
      if (!container) return Promise.resolve(false);

      if (action === "focus") {
        for (const card of container.querySelectorAll(".note-card-expandable")) {
          card.classList.toggle("is-dimmed", card !== options.active);
        }
        return new Promise((resolve) => setTimeout(() => resolve(true), DURATION));
      }

      if (action === "restore") {
        for (const card of container.querySelectorAll(".note-card-expandable")) {
          card.classList.remove("is-dimmed");
        }
        return new Promise((resolve) => setTimeout(() => resolve(true), DURATION));
      }

      return Promise.resolve(false);
    },

    reduced(container, action, options = {}) {
      if (!container) return false;
      if (action === "focus") {
        for (const card of container.querySelectorAll(".note-card-expandable")) {
          card.classList.toggle("is-dimmed", card !== options.active);
        }
      } else {
        for (const card of container.querySelectorAll(".note-card-expandable")) {
          card.classList.remove("is-dimmed");
        }
      }
      return true;
    },
  });
})();
