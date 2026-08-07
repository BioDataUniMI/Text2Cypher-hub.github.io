(() => {
  const setup = () => {
    const title = document.querySelector(".md-nav--primary > .md-nav__title");
    const logo = title && title.querySelector(".md-logo");
    if (!title || !logo || title.dataset.homeReady) return;
    title.dataset.homeReady = "true";
    title.style.cursor = "pointer";
    title.addEventListener("click", (event) => {
      if (event.target.closest("a")) return;
      logo.click();
    });
  };

  document.addEventListener("DOMContentLoaded", setup);
  if (typeof document$ !== "undefined") document$.subscribe(setup);
})();
