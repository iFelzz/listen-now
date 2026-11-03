    'use strict';

    // ── DOM refs ──────────────────────────────────────────────
    const $form = document.getElementById('search-form');
    const $input = document.getElementById('search-input');
    const $searchBtn = document.getElementById('search-btn');
    const $loading = document.getElementById('loading');
    const $loadingText = document.getElementById('loading-text');
    const $emptyState = document.getElementById('empty-state');
    const $errorState = document.getElementById('error-state');
    const $errorMsg = document.getElementById('error-msg');
    const $noResults = document.getElementById('no-results-state');
    const $results = document.getElementById('results');
    const $grid = document.getElementById('results-grid');
    const $count = document.getElementById('results-count');
    const $toastWrap = document.getElementById('toast-container');

    // Pagination elements
    const $limitSelect = document.getElementById('limit-select');
    const $paginationControls = document.getElementById('pagination-controls');
    const $btnPrev = document.getElementById('btn-prev');
    const $btnNext = document.getElementById('btn-next');
    const $pageCurrent = document.getElementById('page-current');
    const $pageTotal = document.getElementById('page-total');

    // Global state
    let allSearchResults = [];
    let currentPage = 1;
    let itemsPerPage = 10;

    // ── Helpers ───────────────────────────────────────────────

    /** Format view count to human-readable string */
    function formatViews(n) {
      if (!n || n === 0) return '';
      if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M views`;
      if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K views`;
      return `${n} views`;
    }

    /** Show / hide the named state panel */
    function showState(state) {
      $emptyState.style.display = state === 'empty' ? '' : 'none';
      $errorState.style.display = state === 'error' ? '' : 'none';
      $noResults.style.display = state === 'no-results' ? '' : 'none';
      $results.classList.toggle('visible', state === 'results');
      $loading.classList.toggle('visible', state === 'loading');
    }

    /** Render a toast notification */
    function toast(type, msg, duration = 4000) {
      const icons = { success: '✅', error: '❌', info: 'ℹ️' };
      const el = document.createElement('div');
      el.className = `toast ${type}`;
      el.setAttribute('role', 'status');
      el.innerHTML = `
      <span class="toast-icon" aria-hidden="true">${icons[type] || 'ℹ️'}</span>
      <span class="toast-msg">${msg}</span>`;
      $toastWrap.appendChild(el);
      setTimeout(() => {
        el.style.animation = 'toast-out 0.3s ease forwards';
        el.addEventListener('animationend', () => el.remove());
      }, duration);
    }

    /** Escape HTML to prevent XSS */
    function esc(str) {
      const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
      return String(str).replace(/[&<>"']/g, c => map[c]);
    }

    // ── SVG Icons ────────────────────────────────────────────

    const ICON_DOWNLOAD = `<svg class="btn-icon" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2"
      d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M16 12l-4 4-4-4M12 3v13"/>
  </svg>`;

    const ICON_SPIN = `<svg class="btn-icon" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
      d="M4 12a8 8 0 018-8v4l3-3-3-3V4A10 10 0 1012 22"/>
  </svg>`;

    const ICON_CHECK = `<svg class="btn-icon" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
  </svg>`;

    const ICON_PLAY = `<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
    const ICON_PAUSE = `<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;

    // ── Build card HTML ───────────────────────────────────────

    function buildCard(item, index) {
      const views = formatViews(item.views);
      const cardId = `card-${index}`;
      const btnId = `btn-dl-${index}`;

      return `
    <article class="card" id="${cardId}" role="listitem" aria-label="${esc(item.title)}">
      <div class="card-thumb-wrap">
        <img
          class="card-thumb"
          src="${esc(item.thumbnail)}"
          alt="${esc(item.title)} thumbnail"
          loading="lazy"
          decoding="async"
          onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 160 90%22><rect fill=%22%231a1a2e%22 width=%22160%22 height=%2290%22/><text x=%2280%22 y=%2250%22 fill=%22%234b4c6e%22 text-anchor=%22middle%22 font-size=%2224%22>♪</text></svg>'"
        />
        <span class="card-duration" aria-label="Duration ${esc(item.duration)}">${esc(item.duration)}</span>
        <button class="btn-play-overlay"
          data-url="${esc(item.url)}"
          data-title="${esc(item.title)}"
          data-artist="${esc(item.channel)}"
          data-thumb="${esc(item.thumbnail)}"
          aria-label="Play Preview">
          ${ICON_PLAY}
        </button>
      </div>

      <div class="card-info">
        <h3 class="card-title" title="${esc(item.title)}">${esc(item.title)}</h3>
        <div class="card-meta">
          <span class="card-channel" aria-label="Channel: ${esc(item.channel)}">${esc(item.channel)}</span>
          ${views ? `<span class="card-views" aria-label="${views}">${views}</span>` : ''}
        </div>
      </div>

      <div class="card-action">
        <div class="quality-selector" role="group" aria-label="Audio quality">
          <button class="quality-btn" data-card="${index}" data-q="128" aria-pressed="false">128k</button>
          <button class="quality-btn active" data-card="${index}" data-q="192" aria-pressed="true">192k</button>
          <button class="quality-btn" data-card="${index}" data-q="320" aria-pressed="false">320k</button>
        </div>
        <button
          class="btn-download"
          id="${btnId}"
          data-url="${esc(item.url)}"
          data-title="${esc(item.title)}"
          data-quality="192"
          aria-label="Download MP3: ${esc(item.title)}"
          title="Download as MP3"
        >
          <div class="progress-fill" style="width: 0%"></div>
          <span class="btn-text">
            ${ICON_DOWNLOAD}
            MP3
          </span>
        </button>
      </div>
    </article>`;
    }

    // ── Pagination Logic ─────────────────────────────────────

    function renderPage() {
      const totalPages = Math.ceil(allSearchResults.length / itemsPerPage) || 1;

      if (currentPage < 1) currentPage = 1;
      if (currentPage > totalPages) currentPage = totalPages;

      const startIndex = (currentPage - 1) * itemsPerPage;
      const endIndex = startIndex + itemsPerPage;
      const pageItems = allSearchResults.slice(startIndex, endIndex);

      // Render cards
      $grid.innerHTML = pageItems.map((item, i) => buildCard(item, startIndex + i)).join('');

      // Update pagination UI
      $pageCurrent.textContent = currentPage;
      $pageTotal.textContent = totalPages;
      $btnPrev.disabled = currentPage === 1;
      $btnNext.disabled = currentPage === totalPages;

      $paginationControls.style.display = allSearchResults.length > itemsPerPage ? 'flex' : 'none';

      // Attach quality selector handlers
      document.querySelectorAll('.quality-btn').forEach(qBtn => {
        qBtn.addEventListener('click', () => {
          const cardIdx = qBtn.dataset.card;
          const quality = qBtn.dataset.q;
          document.querySelectorAll(`.quality-btn[data-card="${cardIdx}"]`).forEach(b => {
            b.classList.toggle('active', b === qBtn);
            b.setAttribute('aria-pressed', b === qBtn ? 'true' : 'false');
          });
          const dlBtn = document.getElementById(`btn-dl-${cardIdx}`);
          if (dlBtn) dlBtn.dataset.quality = quality;
        });
      });

      // Attach preview player handlers
      document.querySelectorAll('.btn-play-overlay').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();

          // Same button clicked: toggle play/pause without losing reference
          if (currentPlayingBtn === btn) {
            if (audioPlayer.paused) {
              audioPlayer.play();
            } else {
              audioPlayer.pause();
            }
            return;
          }

          if (currentPlayingBtn) {
            currentPlayingBtn.innerHTML = ICON_PLAY;
            currentPlayingBtn.classList.remove('playing');
            currentPlayingBtn = null; // Clear stale ref before new song loads
          }

          btn.classList.add('loading');
          btn.innerHTML = ICON_SPIN;

          try {
            const res = await fetch(`/api/preview?url=${encodeURIComponent(btn.dataset.url)}`);
            if (!res.ok) throw new Error('Preview not found');
            const data = await res.json();

            audioPlayer.src = data.stream_url;
            await audioPlayer.play();

            btn.classList.remove('loading');
            btn.classList.add('playing');
            btn.innerHTML = ICON_PAUSE;
            currentPlayingBtn = btn;

            showMiniPlayer(btn.dataset.title, btn.dataset.artist, btn.dataset.thumb);
          } catch (err) {
            console.error(err);
            btn.classList.remove('loading');
            btn.innerHTML = ICON_PLAY;
            toast('error', 'Preview unavailable for this video.');
          }
        });
      });

      // Attach download handlers
      pageItems.forEach((item, i) => {
        const btn = document.getElementById(`btn-dl-${startIndex + i}`);
        if (btn) btn.addEventListener('click', () => handleDownload(btn, item));
      });
    }

    $btnPrev.addEventListener('click', () => {
      if (currentPage > 1) {
        currentPage--;
        renderPage();
        document.getElementById('results-count').scrollIntoView({ behavior: 'smooth' });
      }
    });

    $btnNext.addEventListener('click', () => {
      const totalPages = Math.ceil(allSearchResults.length / itemsPerPage);
      if (currentPage < totalPages) {
        currentPage++;
        renderPage();
        document.getElementById('results-count').scrollIntoView({ behavior: 'smooth' });
      }
    });

    $limitSelect.addEventListener('change', (e) => {
      itemsPerPage = parseInt(e.target.value, 10);
      currentPage = 1;
      renderPage();
    });

    // ── Search ───────────────────────────────────────────────

    async function performSearch(query) {
      showState('loading');
      $loadingText.textContent = 'Searching for songs…';
      $searchBtn.disabled = true;

      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=50`);
        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.detail || `HTTP ${res.status}`);
        }

        allSearchResults = data.results || [];

        if (allSearchResults.length === 0) {
          showState('no-results');
          return;
        }

        $count.textContent = `${allSearchResults.length} results`;
        showState('results');

        currentPage = 1;
        renderPage();

      } catch (err) {
        console.error('[Search Error]', err);
        $errorMsg.textContent = err.message || 'An error occurred while searching. Please try again.';
        showState('error');
      } finally {
        $searchBtn.disabled = false;
      }
    }

    // ── Global Player Setup ───────────────────────────────────
    const audioPlayer = document.getElementById('global-player');
    const $volumeControl = document.getElementById('volume-control');
    const $volumeSlider = document.getElementById('volume-slider');
    let currentPlayingBtn = null;

    // ── Mini Player DOM refs ──────────────────────────────────
    const $miniPlayer = document.getElementById('mini-player');
    const $miniThumb = document.getElementById('mini-thumb');
    const $miniTitle = document.getElementById('mini-title');
    const $miniArtist = document.getElementById('mini-artist');
    const $miniCurrent = document.getElementById('mini-current');
    const $miniDuration = document.getElementById('mini-duration');
    const $miniSeek = document.getElementById('mini-seek');
    const $miniPlayPause = document.getElementById('mini-playpause');
    const $miniPlayIcon = document.getElementById('mini-play-icon');

    // SVG paths for mini player icons
    const MINI_ICON_PLAY = 'M8 5v14l11-7z';
    const MINI_ICON_PAUSE = 'M6 19h4V5H6v14zm8-14v14h4V5h-4z';

    function formatTime(seconds) {
      if (!isFinite(seconds) || isNaN(seconds)) return '0:00';
      const m = Math.floor(seconds / 60);
      const s = Math.floor(seconds % 60);
      return `${m}:${s.toString().padStart(2, '0')}`;
    }

    function showMiniPlayer(title, artist, thumb) {
      $miniTitle.textContent = title || '—';
      $miniArtist.textContent = artist || '';
      $miniThumb.src = thumb || '/static/logo.png';
      $miniThumb.onerror = () => { $miniThumb.src = '/static/logo.png'; };
      $miniSeek.value = 0;
      $miniCurrent.textContent = '0:00';
      $miniDuration.textContent = '0:00';
      $miniPlayIcon.querySelector('path') && ($miniPlayIcon.innerHTML = `<path d="${MINI_ICON_PAUSE}"/>`);
      $miniPlayer.classList.add('show');
      $volumeControl.classList.add('player-open');
      document.body.classList.add('player-open');
    }

    function hideMiniPlayer() {
      $miniPlayer.classList.remove('show');
      $volumeControl.classList.remove('player-open');
      document.body.classList.remove('player-open');
    }

    function setMiniIcon(isPaused) {
      $miniPlayIcon.innerHTML = `<path d="${isPaused ? MINI_ICON_PLAY : MINI_ICON_PAUSE}"/>`;
    }

    // Volume slider initialization
    const savedVol = localStorage.getItem('listen_now_volume');
    if (savedVol !== null) {
      $volumeSlider.value = savedVol;
    }
    audioPlayer.volume = $volumeSlider.value;
    $volumeSlider.addEventListener('input', (e) => {
      audioPlayer.volume = e.target.value;
      localStorage.setItem('listen_now_volume', e.target.value);
    });

    // ── Audio events ──────────────────────────────────────────

    audioPlayer.addEventListener('play', () => {
      $volumeControl.classList.add('show');
      setMiniIcon(false); // show pause icon in mini player
      // Restore pause icon on card button (covers Space-key resume)
      if (currentPlayingBtn) {
        currentPlayingBtn.innerHTML = ICON_PAUSE;
        currentPlayingBtn.classList.add('playing');
      }
    });

    audioPlayer.addEventListener('ended', () => {
      $volumeControl.classList.remove('show');
      hideMiniPlayer();
      if (currentPlayingBtn) {
        currentPlayingBtn.innerHTML = ICON_PLAY;
        currentPlayingBtn.classList.remove('playing');
        currentPlayingBtn = null;
      }
    });

    audioPlayer.addEventListener('pause', () => {
      $volumeControl.classList.remove('show');
      setMiniIcon(true); // show play icon in mini player
      // Update card button icon to PLAY, but KEEP currentPlayingBtn reference
      // so Space bar can resume without losing track of which song is active.
      if (currentPlayingBtn && !audioPlayer.ended) {
        currentPlayingBtn.innerHTML = ICON_PLAY;
        currentPlayingBtn.classList.remove('playing');
        // NOTE: intentionally NOT setting currentPlayingBtn = null here
      }
    });

    // ── Seekbar & time display ────────────────────────────────

    let isSeeking = false;

    audioPlayer.addEventListener('timeupdate', () => {
      if (isSeeking) return;
      const { currentTime, duration } = audioPlayer;
      $miniCurrent.textContent = formatTime(currentTime);
      if (isFinite(duration) && duration > 0) {
        $miniDuration.textContent = formatTime(duration);
        $miniSeek.value = (currentTime / duration) * 100;
        // Update seekbar fill gradient
        $miniSeek.style.background = `linear-gradient(to right, var(--clr-accent) ${$miniSeek.value}%, rgba(255,255,255,0.1) ${$miniSeek.value}%)`;
      }
    });

    audioPlayer.addEventListener('loadedmetadata', () => {
      if (isFinite(audioPlayer.duration)) {
        $miniDuration.textContent = formatTime(audioPlayer.duration);
      }
    });

    $miniSeek.addEventListener('mousedown', () => { isSeeking = true; });
    $miniSeek.addEventListener('touchstart', () => { isSeeking = true; }, { passive: true });

    $miniSeek.addEventListener('input', () => {
      const pct = $miniSeek.value;
      $miniSeek.style.background = `linear-gradient(to right, var(--clr-accent) ${pct}%, rgba(255,255,255,0.1) ${pct}%)`;
      if (isFinite(audioPlayer.duration)) {
        $miniCurrent.textContent = formatTime(audioPlayer.duration * pct / 100);
      }
    });

    $miniSeek.addEventListener('change', () => {
      isSeeking = false;
      if (isFinite(audioPlayer.duration)) {
        audioPlayer.currentTime = audioPlayer.duration * $miniSeek.value / 100;
      }
    });

    // ── Mini player controls ──────────────────────────────────

    $miniPlayPause.addEventListener('click', () => {
      if (audioPlayer.paused) {
        audioPlayer.play();
      } else {
        audioPlayer.pause();
      }
    });

    // ── Download (Zero-Disk Stream Piping, Cobalt-Style) ──────

    async function handleDownload(btn, item) {
      btn.classList.add('loading');

      const btnText = btn.querySelector('.btn-text');
      const progressFill = btn.querySelector('.progress-fill');
      const quality = btn.dataset.quality || '192';
      const label = quality === 'm4a' ? 'M4A' : 'MP3';

      btnText.innerHTML = `${ICON_SPIN} Connecting…`;
      progressFill.style.width = '35%';
      btn.setAttribute('aria-label', `Connecting stream for ${item.title}…`);
      $loadingText.textContent = `Streaming: ${item.title}`;

      try {
        // Fast URL stream resolution (~0.5s)
        const res = await fetch('/api/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: item.url, title: item.title, quality }),
        });
        const data = await res.json();

        if (!res.ok) {
          if (res.status === 429) {
            throw new Error('Too many requests. Please wait a moment and try again.');
          }
          throw new Error(data.detail || `HTTP ${res.status}`);
        }

        // Trigger native browser stream download immediately
        progressFill.style.width = '100%';
        btnText.innerHTML = `${ICON_CHECK} Streaming…`;

        const link = document.createElement('a');
        link.href = data.download_url;
        link.download = data.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        btn.classList.remove('loading');
        btn.classList.add('done');
        toast('success', `🎵 Mengalirkan <strong>${esc(item.title)}</strong> langsung ke browser!`);

        if (Notification.permission === 'granted') {
          new Notification('✅ Download Started!', {
            body: item.title,
            icon: item.thumbnail || '/static/logo.png',
            badge: '/static/logo.png',
            tag: 'listen-now-download',
          });
        }

        setTimeout(() => {
          btn.classList.remove('done');
          progressFill.style.width = '0%';
          btnText.innerHTML = `${ICON_DOWNLOAD} ${label}`;
        }, 3000);

      } catch (err) {
        console.error('[Download Error]', err);

        btn.classList.remove('loading');
        btn.classList.add('error-state');
        progressFill.style.width = '0%';
        btnText.innerHTML = `${ICON_DOWNLOAD} Try Again`;
        btn.setAttribute('aria-label', `Retry download ${item.title}`);

        setTimeout(() => {
          btn.classList.remove('error-state');
          btnText.innerHTML = `${ICON_DOWNLOAD} ${label}`;
          btn.removeAttribute('disabled');
        }, 2500);

        toast('error', `Download failed: ${err.message}`);
      }
    }
    // ── Form submit ───────────────────────────────────────────

    $form.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = $input.value.trim();
      if (q) performSearch(q);
    });

    // Allow Enter key to submit from anywhere in the form
    $input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') $form.dispatchEvent(new Event('submit'));
    });

    // ── Keyboard Shortcuts ────────────────────────────────────
    let shortcutTipShown = false;
    document.addEventListener('keydown', (e) => {
      // Don't hijack shortcuts when typing in the search box
      if (document.activeElement === $input) return;
      // Don't trigger on modifier keys
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === ' ') {
        e.preventDefault();
        if (currentPlayingBtn) {
          if (audioPlayer.paused) {
            audioPlayer.play();
            currentPlayingBtn.classList.add('playing');
            currentPlayingBtn.innerHTML = ICON_PAUSE;
          } else {
            audioPlayer.pause();
          }
        }
      } else if (e.key === 'Escape') {
        // Explicitly reset button state FIRST (before pause fires),
        // then reset playback position. This avoids the race condition where
        // audioPlayer.currentTime = 0 runs before the pause event, causing
        // the pause handler's `currentTime > 0` check to fail silently.
        if (currentPlayingBtn) {
          currentPlayingBtn.innerHTML = ICON_PLAY;
          currentPlayingBtn.classList.remove('playing');
          currentPlayingBtn = null;
        }
        $volumeControl.classList.remove('show');
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        hideMiniPlayer();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const newVol = Math.min(1, parseFloat($volumeSlider.value) + 0.1);
        $volumeSlider.value = newVol;
        audioPlayer.volume = newVol;
        localStorage.setItem('listen_now_volume', newVol);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const newVol = Math.max(0, parseFloat($volumeSlider.value) - 0.1);
        $volumeSlider.value = newVol;
        audioPlayer.volume = newVol;
        localStorage.setItem('listen_now_volume', newVol);
      }

      // Show keyboard tip on first use
      if (!shortcutTipShown && ['Space', 'ArrowUp', 'ArrowDown', 'Escape'].includes(e.code)) {
        shortcutTipShown = true;
      }
    });

    // ── Notification Permission Request ───────────────────────
    // Request after first search (avoids asking on page load which users dismiss)
    function requestNotificationPermission() {
      if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
      }
    }

    // ── PWA / Service Worker Registration ─────────────────────
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
          .then((reg) => console.log('[SW] Registered, scope:', reg.scope))
          .catch((err) => console.warn('[SW] Registration failed:', err));
      });
    }

    // ── Focus search on load ──────────────────────────────────
    window.addEventListener('load', () => {
      $input.focus();
      // Request notification permission after a short delay
      setTimeout(requestNotificationPermission, 3000);
    });

    // ── Load and display Git commit hash badge ────────────────
    function loadCommitHash() {
      fetch('/api/version')
        .then(res => res.json())
        .then(data => {
          const $commitLink = document.getElementById('commit-link');
          if ($commitLink && data.commit) {
            $commitLink.textContent = `#${data.commit}`;
            $commitLink.href = data.commit_url || `https://github.com/iFelzz/listen-now/commit/${data.commit}`;
            $commitLink.title = `Commit ${data.commit} on GitHub`;
          }
        })
        .catch(() => {});
    }
    loadCommitHash();
