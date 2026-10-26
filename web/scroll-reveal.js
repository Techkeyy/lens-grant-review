// Progressive enhancement: content stays visible when scripts or observers are unavailable.
(() => {
  if (!('IntersectionObserver' in window)) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (reducedMotion.matches) return;

  const selectors = [
    '#welcome .hero-proof',
    '#how-it-works > div',
    '#how-it-works li',
    '#start-stage .home-heading',
    '#start-stage .review-picker',
    '#start-stage .start-options > div',
    '#workspace .workspace-heading',
    '#workspace .flow-nav',
    '#workspace .flow-panel > .panel-heading',
    '#workspace .finding',
    '#workspace .results-next',
    '#workspace .export-layout > div'
  ].join(', ');

  const seen = new WeakSet();
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.remove('scroll-await');
      entry.target.classList.add('scroll-shown');
      observer.unobserve(entry.target);
    }
  }, { rootMargin: '0px 0px 48px 0px', threshold: 0.01 });

  document.documentElement.classList.add('scroll-motion');

  function scan() {
    document.querySelectorAll(selectors).forEach((element) => {
      if (seen.has(element) || element.closest('.hidden')) return;
      const rect = element.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      seen.add(element);
      // Keep anything already in view immediately readable and actionable.
      if (rect.top <= window.innerHeight + 20 && rect.bottom >= -20) return;
      element.classList.add('scroll-target', 'scroll-await');
      observer.observe(element);
    });
  }

  let pending = false;
  function scheduleScan() {
    if (pending) return;
    pending = true;
    window.requestAnimationFrame(() => {
      pending = false;
      scan();
    });
  }

  // App views and finding cards are rendered after initial page load.
  const changes = new MutationObserver(scheduleScan);
  changes.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['class']
  });
  scheduleScan();

  // Keyboard focus must never land in visually hidden content.
  document.addEventListener('focusin', (event) => {
    const target = event.target.closest?.('.scroll-await');
    if (!target) return;
    target.classList.remove('scroll-await');
    target.classList.add('scroll-shown');
    observer.unobserve(target);
  });

  reducedMotion.addEventListener?.('change', () => {
    if (!reducedMotion.matches) return;
    document.documentElement.classList.remove('scroll-motion');
    observer.disconnect();
    changes.disconnect();
  });
})();
