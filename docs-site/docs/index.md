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
    
    <!-- Install action: single element with two states (resting: Get Add-on; clicked/active: Drag and Drop into Blender + fallback) -->
    <div class="dd-install-card" id="dd-install-card">
      <button type="button"
              class="dd-install-btn-primary"
              id="dd-install-btn"
              aria-label="Get Add-on">
        Get Add-on
      </button>
      <div class="dd-install-drag-group" id="dd-install-drag-group">
        <div class="dd-install-drag-zone"
             id="dd-install-drag"
             draggable="true"
             role="button"
             tabindex="0"
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
        </div>
        <div class="dd-install-fallback">
          ...or <a href="https://extensions.blender.org/download/sha256:8baed67506582a6ac40a68d13c181eb92cb181fc871c84e0f02c6be294672f9c/add-on-devil-designer-v0.12.0.zip?repository=%2Fapi%2Fv1%2Fextensions%2F&amp;blender_version_min=5.2.0" class="dd-install-fallback-link" download>download</a> and <a href="install/#alternative-install-from-github-release-zip" class="dd-install-fallback-link">Install from Disk</a>
        </div>
      </div>
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
// Install card: single element with resting and drag states
(function() {
  const card = document.getElementById('dd-install-card');
  const btn = document.getElementById('dd-install-btn');
  const dragZone = document.getElementById('dd-install-drag');
  if (!card) return;

  const installUrl = 'https://extensions.blender.org/download/sha256:8baed67506582a6ac40a68d13c181eb92cb181fc871c84e0f02c6be294672f9c/add-on-devil-designer-v0.12.0.zip?repository=%2Fapi%2Fv1%2Fextensions%2F&blender_version_min=5.2.0';

  function revealDrag() {
    card.classList.add('is-active');
  }

  if (btn) {
    btn.addEventListener('click', revealDrag);
  }

  function handleDragStart(e) {
    if (e.target && e.target.closest && e.target.closest('.dd-install-fallback-link')) {
      return;
    }
    revealDrag();
    e.dataTransfer.setData('text/uri-list', installUrl);
    e.dataTransfer.setData('text/plain', installUrl);
    e.dataTransfer.effectAllowed = 'copyLink';
  }

  if (dragZone) {
    dragZone.addEventListener('dragstart', handleDragStart);
  }
  card.addEventListener('dragstart', handleDragStart);
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
