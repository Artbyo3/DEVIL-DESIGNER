---
hide:
  - navigation
  - toc
---

<div class="dd-landing-container">
  <!-- Video slot: placeholder demonstration illustration -->
  <div class="dd-video-slot" aria-hidden="true">
    <img src="assets/images/video-placeholder.png" alt="" class="dd-video-placeholder-img" />
  </div>

  <main class="dd-landing-content">
    <h1 class="dd-landing-title">Devil Designer</h1>
    <p class="dd-landing-tagline">A movable 2D clothing-pattern editor and cloth authoring tool for Blender.</p>
    
    <!-- Install action: solid primary button + dashed drag-and-drop zone -->
    <div class="dd-install-card" id="dd-install-card">
      <a href="https://extensions.blender.org/add-ons/devil-designer/"
         class="dd-install-btn-primary"
         target="_blank"
         rel="noopener">
        Get Add-on
      </a>
      <a href="https://extensions.blender.org/add-ons/devil-designer/"
         draggable="true"
         id="dd-install-drag"
         class="dd-install-drag-zone"
         target="_blank"
         rel="noopener"
         aria-label="Drag and Drop into Blender">
        <svg class="dd-install-drag-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="5 9 2 12 5 15"></polyline>
          <polyline points="9 5 12 2 15 5"></polyline>
          <polyline points="15 19 12 22 9 19"></polyline>
          <polyline points="19 9 22 12 19 15"></polyline>
          <line x1="2" y1="12" x2="22" y2="12"></line>
          <line x1="12" y1="2" x2="12" y2="22"></line>
        </svg>
        <span>Drag and Drop into Blender</span>
      </a>
    </div>

    <!-- Minimal entry options (Quickstart, Documentation, GitHub) -->
    <nav class="dd-landing-nav" aria-label="Documentation entry points">
      <a href="quickstart/" class="dd-landing-btn dd-landing-btn--primary">Quickstart</a>
      <a href="draft/" class="dd-landing-btn">Documentation</a>
      <a href="https://github.com/Artbyo3/DEVIL-DESIGNER" class="dd-landing-btn" target="_blank" rel="noopener">GitHub</a>
    </nav>
  </main>

  <!-- Live contributors space: static centered label above truly infinite seamless marquee -->
  <div class="dd-contributors-container" id="dd-contributors-container" style="display: none;">
    <div class="dd-contributors-label">Contributors</div>
    <div class="dd-contributors-stripe">
      <div class="dd-contributors-track" id="dd-contributors-track"></div>
    </div>
  </div>
</div>

<script>
// Wire HTML5 drag-and-drop payload for the Extensions listing
(function() {
  const card = document.getElementById('dd-install-card');
  if (!card) return;
  const extensionUrl = 'https://extensions.blender.org/add-ons/devil-designer/';
  card.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/uri-list', extensionUrl);
    e.dataTransfer.setData('text/plain', extensionUrl);
    e.dataTransfer.effectAllowed = 'copyLink';
  });
})();

// Fetch live GitHub contributors and populate truly seamless marquee
(async function() {
  try {
    const res = await fetch('https://api.github.com/repos/Artbyo3/DEVIL-DESIGNER/contributors');
    if (!res.ok) return;
    const contributors = await res.json();
    if (!Array.isArray(contributors) || contributors.length === 0) return;

    const track = document.getElementById('dd-contributors-track');
    const container = document.getElementById('dd-contributors-container');
    if (!track || !container) return;

    // Single plain, non-clickable contributor element
    function renderItem(c) {
      return `
        <span class="dd-contributor-item">
          <img src="${c.avatar_url}" alt="" class="dd-contributor-avatar" loading="lazy" width="28" height="28" />
          <span class="dd-contributor-name">${c.login}</span>
        </span>
      `;
    }

    const baseHtml = contributors.map(renderItem).join('');

    // Ensure ONE set contains enough items to span at least 4500px across,
    // guaranteeing it always exceeds the viewport width on any monitor.
    let count = contributors.length;
    let setHtml = baseHtml;
    while (count < 24) {
      setHtml += baseHtml;
      count += contributors.length;
    }

    // Two identical halves: track shifts by -50% (exactly 1 set width) for an invisible loop
    track.innerHTML = `
      <div class="dd-marquee-set">${setHtml}</div>
      <div class="dd-marquee-set" aria-hidden="true">${setHtml}</div>
    `;
    container.style.display = 'flex';
  } catch (e) {
    // Fail silently: no error text, no clutter
  }
})();
</script>
