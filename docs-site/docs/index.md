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
    
    <!-- Draggable add-on package card: drag into Blender to install, click to download zip -->
    <a href="https://github.com/Artbyo3/DEVIL-DESIGNER/releases/download/v0.10.0/devil_designer-0.10.0.zip"
       download
       draggable="true"
       id="dd-install-card"
       class="dd-install-card"
       aria-label="Download or drag Devil Designer v0.10.0 into Blender">
      <div class="dd-install-header">
        <span class="dd-install-name">Devil Designer</span>
        <span class="dd-install-version">v0.10.0</span>
      </div>
      <div class="dd-install-hint">Drag into Blender</div>
    </a>

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
// Wire HTML5 drag-and-drop payload for the install card
(function() {
  const card = document.getElementById('dd-install-card');
  if (!card) return;
  const assetUrl = 'https://github.com/Artbyo3/DEVIL-DESIGNER/releases/download/v0.10.0/devil_designer-0.10.0.zip';
  card.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/uri-list', assetUrl);
    e.dataTransfer.setData('text/plain', assetUrl);
    e.dataTransfer.setData('DownloadURL', `application/zip:devil_designer-0.10.0.zip:${assetUrl}`);
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
