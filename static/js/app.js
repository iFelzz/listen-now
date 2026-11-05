    'use strict';

    // ── DOM refs ──────────────────────────────────────────────
    const $form = document.getElementById('search-form');
    const $input = document.getElementById('search-input');
    const $searchClearBtn = document.getElementById('btn-search-clear');
    const $searchSuggestions = document.getElementById('search-suggestions');
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

    // Artist & Mode DOM refs
    const $tabModeSongs = document.getElementById('tab-mode-songs');
    const $tabModeArtists = document.getElementById('tab-mode-artists');
    const $artistSearchResults = document.getElementById('artist-search-results');
    const $artistResultsGrid = document.getElementById('artist-results-grid');
    const $artistResultsCount = document.getElementById('artist-results-count');
    const $artistSuggestionsBar = document.getElementById('artist-suggestions-bar');
    const $artistSuggestionChips = document.getElementById('artist-suggestion-chips');
    const $artistLoadMoreWrap = document.getElementById('artist-load-more-wrap');
    const $btnLoadMoreArtists = document.getElementById('btn-load-more-artists');
    const $btnLoadMoreArtistsLabel = document.getElementById('btn-load-more-artists-label');

    // Artist Discography DOM refs
    const $artistView = document.getElementById('artist-view');
    const $btnBackArtist = document.getElementById('btn-back-artist');
    const $artistAvatar = document.getElementById('artist-avatar');
    const $artistName = document.getElementById('artist-name');
    const $artistGenre = document.getElementById('artist-genre');
    const $artistStats = document.getElementById('artist-stats');
    const $tabTopSongs = document.getElementById('tab-top-songs');
    const $tabAlbums = document.getElementById('tab-albums');
    const $panelTopSongs = document.getElementById('panel-top-songs');
    const $panelAlbums = document.getElementById('panel-albums');
    const $topSongsList = document.getElementById('top-songs-list');
    const $albumsGrid = document.getElementById('albums-grid');
    const $btnSelectAllTop = document.getElementById('btn-select-all-top');
    const $topSongsLimitSelect = document.getElementById('top-songs-limit-select');
    const $topSongsSubtitle = document.getElementById('top-songs-subtitle');

    // Batch Action Bar DOM refs
    const $batchActionBar = document.getElementById('batch-action-bar');
    const $batchCount = document.getElementById('batch-count');
    const $btnBatchClear = document.getElementById('btn-batch-clear');
    const $btnBatchDownload = document.getElementById('btn-batch-download');
    const $btnBatchDlText = document.getElementById('btn-batch-dl-text');

    // Batch Progress Widget DOM refs
    const $batchProgressWidget = document.getElementById('batch-progress-widget');
    const $batchProgressTitle = document.getElementById('batch-progress-title');
    const $batchProgressSub = document.getElementById('batch-progress-sub');
    const $batchProgressFill = document.getElementById('batch-progress-fill');
    const $batchProgressCount = document.getElementById('batch-progress-count');
    const $batchProgressStatus = document.getElementById('batch-progress-status');
    const $btnBatchCancel = document.getElementById('btn-batch-cancel');
    const $batchProgressActions = document.getElementById('batch-progress-actions');
    const $btnBatchRetry = document.getElementById('btn-batch-retry');
    const $btnBatchRetryText = document.getElementById('btn-batch-retry-text');
    const $btnBatchDismiss = document.getElementById('btn-batch-dismiss');
    const $batchSpinner = document.getElementById('batch-spinner');

    // Release Log / What's New DOM refs
    const $btnReleaseLog = document.getElementById('btn-release-log');
    const $releaseLogBadge = document.getElementById('release-log-badge');
    const $releaseLogModal = document.getElementById('release-log-modal');
    const $releaseLogCard = document.getElementById('release-modal-card');
    const $btnReleaseClose = document.getElementById('btn-release-close');
    const $releaseModalBody = document.getElementById('release-modal-body');

    // Bug Reporter DOM refs
    const $btnOpenBugReport = document.getElementById('btn-open-bug-report');
    const $bugReportModal = document.getElementById('bug-report-modal');
    const $btnReportClose = document.getElementById('btn-report-close');
    const $btnReportCancel = document.getElementById('btn-report-cancel');
    const $reportForm = document.getElementById('report-form');
    const $reportName = document.getElementById('report-name');
    const $reportEmail = document.getElementById('report-email');
    const $reportCategory = document.getElementById('report-category');
    const $reportDescription = document.getElementById('report-description');
    const $reportCharCount = document.getElementById('report-char-count');
    const $reportDropzone = document.getElementById('report-dropzone');
    const $reportFileInput = document.getElementById('report-file-input');
    const $dropzoneIdle = document.getElementById('dropzone-idle');
    const $dropzonePreview = document.getElementById('dropzone-preview');
    const $previewMediaWrap = document.getElementById('preview-media-wrap');
    const $previewFilename = document.getElementById('preview-filename');
    const $previewFilesize = document.getElementById('preview-filesize');
    const $btnPreviewRemove = document.getElementById('btn-preview-remove');
    const $diagAppVersion = document.getElementById('diag-app-version');
    const $diagPlatform = document.getElementById('diag-platform');
    const $diagScreen = document.getElementById('diag-screen');
    const $diagPage = document.getElementById('diag-page');
    const $btnReportSubmit = document.getElementById('btn-report-submit');

    // Global state
    let searchMode = 'songs'; // 'songs' | 'artists'
    let isSearching = false;
    let allSearchResults = [];
    let currentPage = 1;
    let itemsPerPage = 10;
    let currentPreferredQuality = '320';
    try {
      currentPreferredQuality = localStorage.getItem('melodyxx_quality') || localStorage.getItem('listen_now_quality') || '320';
    } catch (_) {}

    let currentPlayingBtn = null;

    // Batch download state
    const selectedTracks = new Map(); // trackId -> trackObj
    let isBatchDownloading = false;
    let cancelBatchDownload = false;
    let lastArtistSearchResults = [];
    let lastArtistSuggestions = [];
    let displayedArtistCount = 0;
    const ARTIST_BATCH_SIZE = 12;
    let currentDiscography = null;

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
      if ($artistSearchResults) $artistSearchResults.style.display = state === 'artists' ? '' : 'none';
      if ($artistView) $artistView.style.display = state === 'artist-view' ? '' : 'none';
    }

    /** Render a toast notification */
    function toast(type, msg, duration = 4000) {
      const icons = {
        success: `<svg viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>`,
        error: `<svg viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
        info: `<svg viewBox="0 0 24 24" fill="none" stroke="#c084fc" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`
      };

      // Prevent stacking duplicate or consecutive cooldown toasts
      if ($toastWrap) {
        const plainMsg = msg.replace(/<[^>]+>/g, '').trim();
        const isCooldownMsg = plainMsg.includes('before submitting another report');
        $toastWrap.querySelectorAll('.toast').forEach(t => {
          const tText = t.innerText.trim();
          if (tText === plainMsg || (isCooldownMsg && tText.includes('before submitting another report'))) {
            t.remove();
          }
        });
      }

      const el = document.createElement('div');
      el.className = `toast ${type}`;
      el.setAttribute('role', 'status');
      el.innerHTML = `
      <span class="toast-icon" aria-hidden="true">${icons[type] || icons.info}</span>
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

    const TRACK_ICON_PLAY = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
    const TRACK_ICON_PAUSE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
    const TRACK_ICON_SPIN = `<svg class="spinner-track-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`;

    function resetCurrentPlayingBtn() {
      if (!currentPlayingBtn) return;
      if (currentPlayingBtn.classList.contains('btn-track-play')) {
        currentPlayingBtn.innerHTML = TRACK_ICON_PLAY;
        currentPlayingBtn.classList.remove('loading', 'playing');
      } else {
        currentPlayingBtn.innerHTML = ICON_PLAY;
        currentPlayingBtn.classList.remove('loading', 'playing');
      }
      currentPlayingBtn = null;
    }

    function updateCurrentPlayingBtn(isPlaying) {
      if (!currentPlayingBtn) return;
      if (currentPlayingBtn.classList.contains('btn-track-play')) {
        currentPlayingBtn.classList.remove('loading');
        currentPlayingBtn.classList.toggle('playing', isPlaying);
        currentPlayingBtn.innerHTML = isPlaying ? TRACK_ICON_PAUSE : TRACK_ICON_PLAY;
      } else {
        currentPlayingBtn.classList.remove('loading');
        currentPlayingBtn.classList.toggle('playing', isPlaying);
        currentPlayingBtn.innerHTML = isPlaying ? ICON_PAUSE : ICON_PLAY;
      }
    }

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
        <button
          class="btn-download"
          id="${btnId}"
          data-url="${esc(item.url)}"
          data-title="${esc(item.title)}"
          data-quality="${currentPreferredQuality}"
          aria-label="Download MP3: ${esc(item.title)}"
          title="Download as ${currentPreferredQuality}kbps MP3"
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

          resetCurrentPlayingBtn();

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

    // ── Global Quality Sync ───────────────────────────────────

    function setGlobalQuality(quality) {
      if (!quality) return;
      currentPreferredQuality = String(quality);
      try {
        localStorage.setItem('melodyxx_quality', currentPreferredQuality);
      } catch (_) {}

      // 1. Sync header toggle buttons
      document.querySelectorAll('.global-q-btn').forEach(btn => {
        const isActive = btn.dataset.quality === currentPreferredQuality;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });

      // 2. Update all card download buttons with preferred quality
      document.querySelectorAll('.btn-download').forEach(dlBtn => {
        dlBtn.dataset.quality = currentPreferredQuality;
        dlBtn.title = `Download as ${currentPreferredQuality}kbps MP3`;
      });

      // 3. Update discography estimated size if currently viewing an artist
      if (currentDiscography && currentDiscography.top_songs) {
        let totalSec = 0;
        currentDiscography.top_songs.forEach(s => { totalSec += (s.duration_sec || 0); });
        const $statSize = document.getElementById('artist-stat-size');
        if ($statSize && totalSec > 0) {
          const qBitrate = parseInt(currentPreferredQuality || '320', 10) || 320;
          const mb = Math.round((totalSec * (qBitrate / 8)) / 1024);
          $statSize.textContent = mb >= 1000 ? `~${(mb / 1024).toFixed(1)} GB` : `~${mb} MB`;
        }
      }
    }

    // Attach listeners to header global quality buttons
    document.querySelectorAll('.global-q-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        setGlobalQuality(btn.dataset.quality);
      });
    });

    // Initialize UI with preferred quality
    setGlobalQuality(currentPreferredQuality);

    // ── Search Mode Switcher ──────────────────────────────────
    if ($tabModeSongs && $tabModeArtists) {
      $tabModeSongs.addEventListener('click', () => {
        searchMode = 'songs';
        $tabModeSongs.classList.add('active');
        $tabModeSongs.setAttribute('aria-selected', 'true');
        $tabModeArtists.classList.remove('active');
        $tabModeArtists.setAttribute('aria-selected', 'false');
        $input.placeholder = 'Type the song title, or paste a YouTube URL...';
        clearSelection();
        if (allSearchResults.length > 0) {
          showState('results');
        } else {
          showState('empty');
        }
      });

      $tabModeArtists.addEventListener('click', () => {
        searchMode = 'artists';
        $tabModeArtists.classList.add('active');
        $tabModeArtists.setAttribute('aria-selected', 'true');
        $tabModeSongs.classList.remove('active');
        $tabModeSongs.setAttribute('aria-selected', 'false');
        $input.placeholder = 'Type artist or band name (e.g. Coldplay, Red Velvet, Alan Walker)…';
        clearSelection();
        if (currentDiscography) {
          showState('artist-view');
        } else if (lastArtistSearchResults && lastArtistSearchResults.length > 0) {
          renderArtistSuggestions(lastArtistSuggestions);
          if ($artistResultsGrid.children.length === 0) {
            renderArtistResults(lastArtistSearchResults, true);
          } else {
            showState('artists');
          }
        } else {
          showState('empty');
        }
      });
    }

    // ── Search ───────────────────────────────────────────────

    async function performSearch(query) {
      if (!query || !query.trim()) return;
      const q = query.trim();

      if (typeof hideSearchSuggestions === 'function') {
        hideSearchSuggestions();
      }
      if ($input) $input.blur();

      if (searchMode === 'artists') {
        await performArtistSearch(q);
        return;
      }

      isSearching = true;
      showState('loading');
      $loadingText.textContent = 'Searching for songs…';
      $searchBtn.disabled = true;

      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=50`);
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
        isSearching = false;
        if (typeof hideSearchSuggestions === 'function') {
          hideSearchSuggestions();
        }
      }
    }

    // ── Artist Search & Discography ───────────────────────────

    async function performArtistSearch(query) {
      if (typeof hideSearchSuggestions === 'function') {
        hideSearchSuggestions();
      }
      if ($input) $input.blur();

      isSearching = true;
      showState('loading');
      $loadingText.textContent = `Searching artists for ${query}…`;
      $searchBtn.disabled = true;

      try {
        const res = await fetch(`/api/artist/search?q=${encodeURIComponent(query)}&limit=48`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

        const artists = data.results || [];
        const suggestions = data.suggestions || [];
        lastArtistSearchResults = artists;
        lastArtistSuggestions = suggestions;

        if (artists.length === 0) {
          showState('no-results');
          return;
        }

        renderArtistSuggestions(suggestions);
        renderArtistResults(artists, true);
      } catch (err) {
        console.error('[Artist Search Error]', err);
        $errorMsg.textContent = err.message || 'Failed to search artists. Please try again.';
        showState('error');
      } finally {
        $searchBtn.disabled = false;
        isSearching = false;
        if (typeof hideSearchSuggestions === 'function') {
          hideSearchSuggestions();
        }
      }
    }

    function renderArtistSuggestions(suggestions) {
      if (!$artistSuggestionsBar || !$artistSuggestionChips) return;
      if (!suggestions || suggestions.length === 0) {
        $artistSuggestionsBar.style.display = 'none';
        $artistSuggestionChips.innerHTML = '';
        return;
      }

      $artistSuggestionsBar.style.display = 'flex';
      $artistSuggestionChips.innerHTML = suggestions.map(s => `
        <button type="button" class="suggestion-chip" data-query="${esc(s)}" aria-label="Search suggested artist ${esc(s)}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          <span>${esc(s)}</span>
        </button>
      `).join('');

      $artistSuggestionChips.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
          const q = chip.dataset.query;
          if (q) {
            $searchInput.value = q;
            if (typeof updateSearchClearBtn === 'function') updateSearchClearBtn();
            performArtistSearch(q);
          }
        });
      });
    }

    const ARTIST_PLACEHOLDER_SVG = `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>`;

    function renderArtistResults(artists, reset = true) {
      if (reset) {
        displayedArtistCount = 0;
        $artistResultsGrid.innerHTML = '';
      }

      appendArtistBatch(ARTIST_BATCH_SIZE);
      showState('artists');
    }

    function appendArtistBatch(count = ARTIST_BATCH_SIZE) {
      const total = lastArtistSearchResults.length;
      const nextBatch = lastArtistSearchResults.slice(displayedArtistCount, displayedArtistCount + count);
      if (nextBatch.length === 0) return;

      const html = nextBatch.map(art => {
        const countryLabel = art.country
          ? `<span class="artist-card-country" title="${esc(art.country)}">${art.flag ? `${esc(art.flag)} ` : ''}${esc(art.country)}</span>`
          : '';
        const photoHtml = art.photo
          ? `<img src="${esc(art.photo)}" alt="${esc(art.name)}" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" /><div class="artist-card-placeholder" style="display:none;">${ARTIST_PLACEHOLDER_SVG}</div>`
          : `<div class="artist-card-placeholder">${ARTIST_PLACEHOLDER_SVG}</div>`;

        return `
          <div class="artist-card" data-artist-id="${art.artist_id}">
            <div class="artist-card-avatar">
              ${photoHtml}
            </div>
            <div class="artist-card-info">
              <div class="artist-card-name" title="${esc(art.name)}">${esc(art.name)}</div>
              <div class="artist-card-meta">
                ${countryLabel}
                <span class="artist-card-genre">${esc(art.genre || 'Music')}</span>
              </div>
            </div>
          </div>
        `;
      }).join('');

      $artistResultsGrid.insertAdjacentHTML('beforeend', html);
      displayedArtistCount += nextBatch.length;

      // Attach click listeners to newly appended cards
      $artistResultsGrid.querySelectorAll('.artist-card:not([data-bound])').forEach(card => {
        card.setAttribute('data-bound', 'true');
        card.addEventListener('click', () => {
          loadArtistDiscography(card.dataset.artistId);
        });
      });

      // Update count & load more button
      if (total > displayedArtistCount) {
        $artistResultsCount.textContent = `Showing ${displayedArtistCount} of ${total} artists found`;
        if ($artistLoadMoreWrap) {
          $artistLoadMoreWrap.style.display = 'flex';
          const remaining = total - displayedArtistCount;
          if ($btnLoadMoreArtistsLabel) {
            $btnLoadMoreArtistsLabel.textContent = `Load More Artists (+${Math.min(count, remaining)})`;
          }
        }
      } else {
        $artistResultsCount.textContent = `${total} artist${total === 1 ? '' : 's'} found`;
        if ($artistLoadMoreWrap) {
          $artistLoadMoreWrap.style.display = 'none';
        }
      }
    }

    if ($btnLoadMoreArtists) {
      $btnLoadMoreArtists.addEventListener('click', () => {
        appendArtistBatch(ARTIST_BATCH_SIZE);
      });
    }

    async function loadArtistDiscography(artistId) {
      showState('loading');
      $loadingText.textContent = 'Loading discography & popular tracks…';
      $searchBtn.disabled = true;

      try {
        const res = await fetch(`/api/artist/${artistId}/discography`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

        currentDiscography = data;
        renderDiscography(data);
        showState('artist-view');
      } catch (err) {
        console.error('[Discography Error]', err);
        $errorMsg.textContent = err.message || 'Failed to load artist discography.';
        showState('error');
      } finally {
        $searchBtn.disabled = false;
      }
    }

    if ($btnBackArtist) {
      $btnBackArtist.addEventListener('click', () => {
        currentDiscography = null;
        if (lastArtistSearchResults && lastArtistSearchResults.length > 0) {
          renderArtistSuggestions(lastArtistSuggestions);
          showState('artists');
        } else if (allSearchResults.length > 0) {
          searchMode = 'songs';
          $tabModeSongs.classList.add('active');
          $tabModeArtists.classList.remove('active');
          showState('results');
        } else {
          showState('empty');
        }
      });
    }

    // Discography Sub-tabs (Top Songs vs Albums)
    if ($tabTopSongs && $tabAlbums) {
      $tabTopSongs.addEventListener('click', () => {
        $tabTopSongs.classList.add('active');
        $tabAlbums.classList.remove('active');
        $panelTopSongs.style.display = 'block';
        $panelAlbums.style.display = 'none';
      });

      $tabAlbums.addEventListener('click', () => {
        $tabAlbums.classList.add('active');
        $tabTopSongs.classList.remove('active');
        $panelTopSongs.style.display = 'none';
        $panelAlbums.style.display = 'block';
      });
    }

    function getVisibleTopSongs() {
      if (!currentDiscography || !currentDiscography.top_songs) return [];
      const allSongs = currentDiscography.top_songs;
      const limitVal = $topSongsLimitSelect ? $topSongsLimitSelect.value : '100';
      const limit = limitVal === 'all' ? allSongs.length : (parseInt(limitVal, 10) || 100);
      return allSongs.slice(0, limit);
    }

    function renderTopSongsList() {
      if (!currentDiscography || !currentDiscography.top_songs) return;
      const allSongs = currentDiscography.top_songs;
      const visibleSongs = getVisibleTopSongs();

      if ($topSongsSubtitle) {
        $topSongsSubtitle.textContent = `Showing ${visibleSongs.length} of ${allSongs.length} popular tracks`;
      }

      $topSongsList.innerHTML = visibleSongs.map(track => buildTrackRow(track)).join('');
      attachTrackRowListeners($topSongsList);
      updateSelectAllTopButton();
    }

    function updateSelectAllTopButton() {
      if (!$btnSelectAllTop || !currentDiscography || !currentDiscography.top_songs) return;
      const visibleSongs = getVisibleTopSongs();
      if (visibleSongs.length === 0) return;

      const allSelected = visibleSongs.every(t => selectedTracks.has(t.track_id));
      $btnSelectAllTop.textContent = allSelected ? 'Deselect All' : 'Select All Popular Songs';
    }

    if ($topSongsLimitSelect) {
      $topSongsLimitSelect.addEventListener('change', () => {
        renderTopSongsList();
      });
    }

    function renderDiscography(disco) {
      $artistName.textContent = disco.name;
      $artistGenre.textContent = disco.genre || 'Music';
      $artistStats.textContent = `${disco.top_songs.length} Popular Tracks • ${disco.albums.length} Albums & EPs`;

      const $artistCountry = document.getElementById('artist-country');
      if ($artistCountry) {
        if (disco.country) {
          $artistCountry.textContent = `${disco.flag ? `${disco.flag} ` : ''}${disco.country}`;
          $artistCountry.style.display = 'inline-flex';
        } else {
          $artistCountry.style.display = 'none';
        }
      }

      const photoUrl = disco.photo || disco.artwork_url || '/static/logo.png';
      $artistAvatar.src = photoUrl;
      $artistAvatar.onerror = () => { $artistAvatar.src = disco.artwork_url || '/static/logo.png'; };

      // Ambient dynamic artwork backdrop
      const $ambientBg = document.getElementById('artist-ambient-backdrop');
      if ($ambientBg) {
        if (disco.photo || disco.artwork_url) {
          $ambientBg.style.backgroundImage = `url('${disco.photo || disco.artwork_url}')`;
          $ambientBg.style.display = 'block';
        } else {
          $ambientBg.style.display = 'none';
        }
      }

      // Compute Extra Statistics & Music Insights
      // 1. Career Span (Min Year - Max Year)
      const years = [];
      if (Array.isArray(disco.albums)) {
        disco.albums.forEach(a => {
          if (a.year && a.year.length >= 4) {
            const yr = parseInt(a.year, 10);
            if (yr > 1950 && yr < 2100) years.push(yr);
          }
        });
      }
      if (Array.isArray(disco.top_songs)) {
        disco.top_songs.forEach(s => {
          if (s.year && s.year.length >= 4) {
            const yr = parseInt(s.year, 10);
            if (yr > 1950 && yr < 2100) years.push(yr);
          }
        });
      }
      const $statCareer = document.getElementById('artist-stat-career');
      if ($statCareer) {
        if (years.length > 0) {
          const minY = Math.min(...years);
          const maxY = Math.max(...years);
          $statCareer.textContent = minY === maxY ? `${minY}` : `${minY} – ${maxY}`;
        } else {
          $statCareer.textContent = '—';
        }
      }

      // 2. Latest Album Release
      const $statLatest = document.getElementById('artist-stat-latest');
      if ($statLatest) {
        if (disco.albums && disco.albums.length > 0) {
          const latest = disco.albums[0];
          const latestTitle = latest.title || 'Latest Album';
          const yrSuffix = latest.year ? ` (${latest.year})` : '';
          $statLatest.textContent = `${latestTitle}${yrSuffix}`;
          $statLatest.title = `${latestTitle}${yrSuffix}`;
        } else {
          $statLatest.textContent = '—';
          $statLatest.title = '';
        }
      }

      // 3. Total Duration across popular songs
      let totalSec = 0;
      if (Array.isArray(disco.top_songs)) {
        disco.top_songs.forEach(s => {
          totalSec += (s.duration_sec || 0);
        });
      }
      const $statDuration = document.getElementById('artist-stat-duration');
      if ($statDuration) {
        if (totalSec > 0) {
          const hrs = Math.floor(totalSec / 3600);
          const mins = Math.floor((totalSec % 3600) / 60);
          $statDuration.textContent = hrs > 0 ? `~${hrs}h ${mins}m` : `~${mins}m`;
        } else {
          $statDuration.textContent = '—';
        }
      }

      // 4. Estimated Audio Download Size based on current preferred quality
      const $statSize = document.getElementById('artist-stat-size');
      if ($statSize) {
        if (totalSec > 0) {
          const qBitrate = parseInt(currentPreferredQuality || '320', 10) || 320;
          const mb = Math.round((totalSec * (qBitrate / 8)) / 1024);
          $statSize.textContent = mb >= 1000 ? `~${(mb / 1024).toFixed(1)} GB` : `~${mb} MB`;
        } else {
          $statSize.textContent = '—';
        }
      }

      // Render Top Songs List according to display limit
      renderTopSongsList();

      // Render Albums List
      $albumsGrid.innerHTML = disco.albums.map(album => `
        <div class="album-card" id="album-card-${album.album_id}" data-album-id="${album.album_id}">
          <div class="album-header" data-album-id="${album.album_id}">
            <img class="album-art" src="${album.artwork_url || '/static/logo.png'}" alt="Cover" loading="lazy" onerror="this.src='/static/logo.png'">
            <div class="album-info">
              <div class="album-title" title="${esc(album.title)}">${esc(album.title)}</div>
              <div class="album-meta-text">${album.year ? album.year + ' • ' : ''}${album.track_count} Tracks • ${esc(album.genre)}</div>
            </div>
            <div class="album-actions">
              <button type="button" class="btn-select-album" data-album-id="${album.album_id}">
                Select Album
              </button>
              <svg class="album-toggle-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
          </div>
          <div class="album-tracks-container" id="album-tracks-${album.album_id}">
            <div class="tracks-list" id="album-list-${album.album_id}">
              <div style="font-size: 0.8rem; color: var(--clr-text-muted); padding: 8px 0;">Loading tracklist...</div>
            </div>
          </div>
        </div>
      `).join('');

      // Attach Album Header click listeners (accordion toggle & lazy load tracks)
      $albumsGrid.querySelectorAll('.album-header').forEach(header => {
        header.addEventListener('click', async (e) => {
          if (e.target.closest('.btn-select-album')) return; // handled separately
          const albumId = header.dataset.albumId;
          const card = document.getElementById(`album-card-${albumId}`);
          card.classList.toggle('open');
          if (card.classList.contains('open')) {
            await ensureAlbumTracksLoaded(albumId);
          }
        });
      });

      // Attach "Select Album" click listeners
      $albumsGrid.querySelectorAll('.btn-select-album').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const albumId = btn.dataset.albumId;
          const card = document.getElementById(`album-card-${albumId}`);
          if (!card.classList.contains('open')) {
            card.classList.add('open');
          }
          const tracks = await ensureAlbumTracksLoaded(albumId);
          if (tracks && tracks.length > 0) {
            // Check if all are already selected
            const allSelected = tracks.every(t => selectedTracks.has(t.track_id));
            tracks.forEach(t => toggleTrackSelection(t, !allSelected));
            btn.textContent = !allSelected ? 'Deselect' : 'Select Album';
          }
        });
      });

      // "Select All Popular Songs" button
      if ($btnSelectAllTop) {
        $btnSelectAllTop.onclick = () => {
          if (!currentDiscography || !currentDiscography.top_songs) return;
          const visibleSongs = getVisibleTopSongs();
          if (visibleSongs.length === 0) return;

          const allSelected = visibleSongs.every(t => selectedTracks.has(t.track_id));
          visibleSongs.forEach(t => toggleTrackSelection(t, !allSelected));
          updateSelectAllTopButton();
        };
      }
    }

    async function ensureAlbumTracksLoaded(albumId) {
      const listEl = document.getElementById(`album-list-${albumId}`);
      if (!listEl) return [];
      if (listEl.dataset.loaded === 'true') {
        const albumObj = currentDiscography.albums.find(a => a.album_id === albumId);
        return albumObj ? albumObj.tracks || [] : [];
      }

      try {
        const res = await fetch(`/api/album/${albumId}/tracks`);
        const data = await res.json();
        const tracks = data.tracks || [];
        const albumObj = currentDiscography.albums.find(a => a.album_id === albumId);
        if (albumObj) albumObj.tracks = tracks;

        listEl.innerHTML = tracks.map(t => buildTrackRow(t)).join('');
        listEl.dataset.loaded = 'true';
        attachTrackRowListeners(listEl);
        return tracks;
      } catch (err) {
        console.error('Failed to load album tracks:', err);
        listEl.innerHTML = '<div style="font-size:0.8rem; color:#ff6b6b;">Failed to load album tracks.</div>';
        return [];
      }
    }

    function buildTrackRow(track) {
      const isChecked = selectedTracks.has(track.track_id);
      return `
        <div class="track-row ${isChecked ? 'selected' : ''}" id="track-row-${track.track_id}" data-id="${track.track_id}">
          <div class="track-cb-wrap">
            <input type="checkbox" class="track-checkbox" data-id="${track.track_id}" ${isChecked ? 'checked' : ''} aria-label="Select track ${esc(track.title)}">
          </div>
          <img class="track-art" src="${track.artwork_url || '/static/logo.png'}" alt="Art" loading="lazy" onerror="this.src='/static/logo.png'">
          <div class="track-main">
            <div class="track-title" title="${esc(track.title)}">${esc(track.title)}</div>
            <div class="track-sub">${esc(track.album || '')}${track.year ? ' • ' + track.year : ''}</div>
          </div>
          <div class="track-dur">${track.duration || ''}</div>
          <div class="track-actions">
            ${track.preview_url ? `
            <button type="button" class="btn-track-action btn-track-play" data-preview="${esc(track.preview_url)}" data-title="${esc(track.title)}" data-artist="${esc(track.artist)}" data-art="${esc(track.artwork_url)}" title="Preview Audio">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
            </button>` : ''}
            <button type="button" class="btn-track-action btn-track-download" data-id="${track.track_id}" title="Download Track">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
            </button>
          </div>
        </div>
      `;
    }

    function attachTrackRowListeners(container) {
      // Checkbox click
      container.querySelectorAll('.track-checkbox').forEach(cb => {
        cb.addEventListener('change', () => {
          const trackId = cb.dataset.id;
          const track = findTrackInDiscography(trackId);
          if (track) toggleTrackSelection(track, cb.checked);
        });
      });

      // Play preview click
      container.querySelectorAll('.btn-track-play').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const prevUrl = btn.dataset.preview;
          if (!prevUrl) return;

          // Same track button clicked: toggle play / pause
          if (currentPlayingBtn === btn) {
            if (audioPlayer.paused) {
              btn.innerHTML = TRACK_ICON_SPIN;
              btn.classList.add('loading');
              try {
                await audioPlayer.play();
                btn.classList.remove('loading');
                btn.classList.add('playing');
                btn.innerHTML = TRACK_ICON_PAUSE;
              } catch (_) {
                btn.classList.remove('loading', 'playing');
                btn.innerHTML = TRACK_ICON_PLAY;
              }
            } else {
              audioPlayer.pause();
              btn.classList.remove('loading', 'playing');
              btn.innerHTML = TRACK_ICON_PLAY;
            }
            return;
          }

          // Different button clicked: reset previous active button icon back to PLAY
          resetCurrentPlayingBtn();

          // Immediately give loading feedback!
          btn.innerHTML = TRACK_ICON_SPIN;
          btn.classList.add('loading');
          currentPlayingBtn = btn;

          try {
            audioPlayer.src = prevUrl;
            await audioPlayer.play();
            btn.classList.remove('loading');
            btn.classList.add('playing');
            btn.innerHTML = TRACK_ICON_PAUSE;
            showMiniPlayer(btn.dataset.title, btn.dataset.artist, btn.dataset.art);
          } catch (err) {
            console.error('Audio playback failed:', err);
            btn.classList.remove('loading', 'playing');
            btn.innerHTML = TRACK_ICON_PLAY;
            currentPlayingBtn = null;
            toast('error', 'Audio preview could not be loaded.');
          }
        });
      });

      // Single track download
      container.querySelectorAll('.btn-track-download').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const trackId = btn.dataset.id;
          const track = findTrackInDiscography(trackId);
          if (!track) return;

          btn.innerHTML = `<div class="spinner-small" style="margin:auto;"></div>`;
          btn.disabled = true;

          try {
            const res = await fetch('/api/download', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                url: '',
                title: track.title,
                artist: track.artist,
                album: track.album,
                year: track.year,
                poster_url: track.artwork_url,
                quality: currentPreferredQuality
              })
            });
            let data = null;
            try {
              data = await res.json();
            } catch (_) {}
            if (!res.ok) throw new Error((data && data.detail) || `Server error (${res.status})`);
            if (!data || !data.download_url) throw new Error('Download URL not found.');

            triggerDownload(data.download_url, data.filename);
            toast('success', `Downloading <strong>${esc(track.artist)} - ${esc(track.title)}</strong>`);
          } catch (err) {
            console.error(err);
            toast('error', `Download failed: ${err.message}`);
          } finally {
            btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>`;
            btn.disabled = false;
          }
        });
      });
    }

    function findTrackInDiscography(trackId) {
      if (!currentDiscography) return null;
      let found = currentDiscography.top_songs.find(t => t.track_id === trackId);
      if (found) return found;
      for (const alb of currentDiscography.albums) {
        if (alb.tracks) {
          found = alb.tracks.find(t => t.track_id === trackId);
          if (found) return found;
        }
      }
      return null;
    }

    // ── Multi-Select & Batch Actions ──────────────────────────

    function toggleTrackSelection(track, forceVal = null) {
      const isSelected = forceVal !== null ? forceVal : !selectedTracks.has(track.track_id);
      if (isSelected) {
        selectedTracks.set(track.track_id, track);
      } else {
        selectedTracks.delete(track.track_id);
      }

      document.querySelectorAll(`.track-row[data-id="${track.track_id}"]`).forEach(row => {
        row.classList.toggle('selected', isSelected);
        const cb = row.querySelector('.track-checkbox');
        if (cb) cb.checked = isSelected;
      });

      updateBatchActionBar();
      updateSelectAllTopButton();
    }

    function clearSelection() {
      selectedTracks.clear();
      document.querySelectorAll('.track-row.selected').forEach(r => r.classList.remove('selected'));
      document.querySelectorAll('.track-checkbox:checked').forEach(c => c.checked = false);
      if ($batchActionBar) $batchActionBar.style.display = 'none';
      updateSelectAllTopButton();
    }

    function updateBatchActionBar() {
      const count = selectedTracks.size;
      if (count > 0 && !isBatchDownloading) {
        $batchActionBar.style.display = 'flex';
        $batchCount.textContent = count;
        $btnBatchDlText.textContent = `Download Selected (${count})`;
      } else {
        $batchActionBar.style.display = 'none';
      }
    }

    if ($btnBatchClear) {
      $btnBatchClear.addEventListener('click', clearSelection);
    }

    // ── Sequential Batch Downloader (Option A) ────────────────

    if ($btnBatchDownload) {
      $btnBatchDownload.addEventListener('click', startBatchDownload);
    }

    if ($btnBatchCancel) {
      $btnBatchCancel.addEventListener('click', () => {
        cancelBatchDownload = true;
        $batchProgressStatus.textContent = 'Cancelling...';
      });
    }

    if ($btnBatchRetry) {
      $btnBatchRetry.addEventListener('click', () => {
        if ($batchProgressActions) $batchProgressActions.style.display = 'none';
        startBatchDownload();
      });
    }

    if ($btnBatchDismiss) {
      $btnBatchDismiss.addEventListener('click', () => {
        $batchProgressWidget.style.display = 'none';
        isBatchDownloading = false;
        if (selectedTracks.size > 0 && $batchActionBar) {
          $batchActionBar.style.display = 'flex';
        }
      });
    }

    async function startBatchDownload() {
      if (selectedTracks.size === 0) return;
      if (isBatchDownloading) {
        toast('info', 'Batch download is already in progress!');
        return;
      }

      const queue = Array.from(selectedTracks.values());
      const total = queue.length;
      isBatchDownloading = true;
      cancelBatchDownload = false;

      // Show progress widget & hide bottom bar
      $batchProgressWidget.style.display = 'block';
      if ($batchProgressActions) $batchProgressActions.style.display = 'none';
      if ($batchSpinner) $batchSpinner.style.display = 'inline-block';
      $batchActionBar.style.display = 'none';

      let successCount = 0;
      const failedTracks = [];

      for (let i = 0; i < total; i++) {
        if (cancelBatchDownload) {
          toast('info', 'Batch download cancelled.');
          break;
        }

        const track = queue[i];
        const trackNum = i + 1;

        // Update UI progress
        $batchProgressTitle.textContent = `Downloading (${trackNum}/${total})`;
        $batchProgressSub.textContent = `${track.artist} - ${track.title}`;
        $batchProgressFill.style.width = `${Math.round(((i) / total) * 100)}%`;
        $batchProgressCount.textContent = `${trackNum} / ${total}`;
        $batchProgressStatus.textContent = 'Resolving stream…';

        let attempt = 0;
        let downloaded = false;

        while (attempt < 2 && !downloaded && !cancelBatchDownload) {
          attempt++;
          try {
            const res = await fetch('/api/download', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                url: '',
                title: track.title,
                artist: track.artist,
                album: track.album,
                year: track.year,
                poster_url: track.artwork_url,
                quality: currentPreferredQuality
              })
            });

            let data = null;
            try {
              data = await res.json();
            } catch (_) {}

            if (res.status === 429) {
              $batchProgressStatus.textContent = 'Rate limit hit, waiting 5s before retry…';
              await new Promise(r => setTimeout(r, 5000));
              continue;
            }

            if (!res.ok) throw new Error((data && data.detail) || `Server error (${res.status})`);
            if (!data || !data.download_url) throw new Error('Download URL missing');

            triggerDownload(data.download_url, data.filename);
            downloaded = true;
            successCount++;
            $batchProgressStatus.textContent = 'Stream dispatched!';

            // Automatically uncheck and deselect successful track from selection state
            toggleTrackSelection(track, false);
          } catch (err) {
            console.warn(`[Batch DL Attempt ${attempt}] ${track.title}:`, err);
            if (attempt < 2 && !cancelBatchDownload) {
              $batchProgressStatus.textContent = 'Retrying…';
              await new Promise(r => setTimeout(r, 2000));
            } else {
              failedTracks.push(track);
              $batchProgressStatus.textContent = 'Failed';
            }
          }
        }

        // Safe inter-download delay (3s) to avoid download manager thrashing & socket exhaustion
        if (i < total - 1 && !cancelBatchDownload) {
          $batchProgressStatus.textContent = 'Pacing next download (3s)…';
          await new Promise(r => setTimeout(r, 3000));
        }
      }

      $batchProgressFill.style.width = '100%';
      if ($batchSpinner) $batchSpinner.style.display = 'none';

      if (failedTracks.length === 0) {
        $batchProgressTitle.textContent = 'Completed!';
        $batchProgressSub.textContent = `All ${successCount} track${successCount === 1 ? '' : 's'} downloaded successfully.`;
        $batchProgressStatus.textContent = 'All downloads finished';
        toast('success', `Finished downloading all ${successCount} tracks!`);

        setTimeout(() => {
          $batchProgressWidget.style.display = 'none';
          isBatchDownloading = false;
          clearSelection();
        }, 4000);
      } else {
        // Keep failed tracks selected so the user can see what failed and retry them
        isBatchDownloading = false;
        $batchProgressTitle.textContent = 'Batch Incomplete';
        $batchProgressSub.textContent = `${successCount} downloaded, ${failedTracks.length} failed.`;
        $batchProgressStatus.textContent = 'Failed tracks kept in queue';
        if ($btnBatchRetryText) {
          $btnBatchRetryText.textContent = `Retry Failed Tracks (${failedTracks.length})`;
        }
        if ($batchProgressActions) {
          $batchProgressActions.style.display = 'flex';
        }
        toast('warning', `${failedTracks.length} track${failedTracks.length === 1 ? '' : 's'} failed. Click Retry to re-download.`);
      }
    }

    function triggerDownload(url, filename) {
      const a = document.createElement('a');
      a.href = url;
      if (filename) a.download = filename;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      setTimeout(() => a.remove(), 1000);
    }

    // ── Global Player Setup ───────────────────────────────────
    const audioPlayer = document.getElementById('global-player');
    const $volumeControl = document.getElementById('volume-control');
    const $volumeSlider = document.getElementById('volume-slider');

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
    const savedVol = localStorage.getItem('melodyxx_volume') || localStorage.getItem('listen_now_volume');
    if (savedVol !== null) {
      $volumeSlider.value = savedVol;
    }
    audioPlayer.volume = $volumeSlider.value;
    $volumeSlider.addEventListener('input', (e) => {
      audioPlayer.volume = e.target.value;
      localStorage.setItem('melodyxx_volume', e.target.value);
    });

    // ── Audio events ──────────────────────────────────────────

    audioPlayer.addEventListener('play', () => {
      $volumeControl.classList.add('show');
      setMiniIcon(false); // show pause icon in mini player
      updateCurrentPlayingBtn(true);
    });

    audioPlayer.addEventListener('waiting', () => {
      if (currentPlayingBtn) {
        currentPlayingBtn.classList.add('loading');
        if (currentPlayingBtn.classList.contains('btn-track-play')) {
          currentPlayingBtn.innerHTML = TRACK_ICON_SPIN;
        } else {
          currentPlayingBtn.innerHTML = ICON_SPIN;
        }
      }
    });

    audioPlayer.addEventListener('playing', () => {
      if (currentPlayingBtn) {
        currentPlayingBtn.classList.remove('loading');
      }
      updateCurrentPlayingBtn(true);
    });

    audioPlayer.addEventListener('ended', () => {
      $volumeControl.classList.remove('show');
      hideMiniPlayer();
      resetCurrentPlayingBtn();
    });

    audioPlayer.addEventListener('pause', () => {
      $volumeControl.classList.remove('show');
      setMiniIcon(true); // show play icon in mini player
      if (!audioPlayer.ended) {
        updateCurrentPlayingBtn(false);
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
      const quality = btn.dataset.quality || currentPreferredQuality || '320';
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
        toast('success', `Streaming <strong>${esc(item.title)}</strong> directly to browser!`);

        if (Notification.permission === 'granted') {
          new Notification('Download Started!', {
            body: item.title,
            icon: item.thumbnail || '/static/logo.png',
            badge: '/static/logo.png',
            tag: 'melodyxx-download',
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

    // ── Live Autocomplete & Search Recommendations ─────────────
    const ICON_SUGGEST_SEARCH = `<svg class="suggestion-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>`;
    const ICON_SUGGEST_ARTIST = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
    const ICON_SUGGEST_ARROW = `<svg class="suggestion-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="7" y1="17" x2="17" y2="7"></line><polyline points="7 7 17 7 17 17"></polyline></svg>`;

    const suggestCache = new Map();
    let suggestAbortCtrl = null;
    let suggestDebounceTimer = null;
    let activeSuggestIndex = -1;

    function hideSearchSuggestions() {
      clearTimeout(suggestDebounceTimer);
      if (suggestAbortCtrl) {
        try {
          suggestAbortCtrl.abort();
        } catch (_) {}
        suggestAbortCtrl = null;
      }
      if (!$searchSuggestions) return;
      $searchSuggestions.style.display = 'none';
      $searchSuggestions.innerHTML = '';
      activeSuggestIndex = -1;
      if ($emptyState) {
        $emptyState.style.visibility = '';
      }
    }

    function highlightMatch(text, query) {
      if (!text) return '';
      if (!query || !query.trim()) return esc(text);
      const qClean = query.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(${qClean})`, 'gi');
      const parts = text.split(regex);
      return parts.map(part => {
        if (part.toLowerCase() === query.trim().toLowerCase()) {
          return `<strong class="suggestion-match">${esc(part)}</strong>`;
        }
        return esc(part);
      }).join('');
    }

    function renderSearchSuggestions(data, typedQuery) {
      if (!$searchSuggestions || isSearching) return;

      // ── ARTISTS MODE: strictly render matching artists, never song titles ──
      if (searchMode === 'artists') {
        const artists = (data.artists && data.artists.length > 0)
          ? data.artists
          : (data.top_artist ? [data.top_artist] : []);

        if (artists.length === 0) {
          hideSearchSuggestions();
          return;
        }

        let html = '<div class="suggestion-queries-list">';
        html += artists.map(art => {
          const photoHtml = art.photo
            ? `<img src="${esc(art.photo)}" alt="${esc(art.name)}" class="suggestion-artist-photo" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" /><div class="suggestion-artist-avatar-fallback" style="display:none;">${ICON_SUGGEST_ARTIST}</div>`
            : `<div class="suggestion-artist-avatar-fallback">${ICON_SUGGEST_ARTIST}</div>`;

          const countryLabel = art.country
            ? `<span class="suggestion-artist-country" title="${esc(art.country)}">${art.flag ? `${esc(art.flag)} ` : ''}${esc(art.country)}</span>`
            : (art.flag ? `<span class="suggestion-artist-country">${esc(art.flag)}</span>` : '');

          const metaItems = [];
          if (countryLabel) metaItems.push(countryLabel);
          metaItems.push(esc(art.genre || 'Artist'));

          return `
            <div class="suggestion-artist-item" data-type="artist" data-artist-id="${esc(art.artist_id || '')}" data-name="${esc(art.name)}" role="option" tabindex="-1">
              <div class="suggestion-artist-avatar" aria-hidden="true">
                ${photoHtml}
              </div>
              <div class="suggestion-artist-info">
                <span class="suggestion-artist-name">${highlightMatch(art.name, typedQuery)}</span>
                <div class="suggestion-artist-meta">
                  ${metaItems.join(' • ')}
                </div>
              </div>
              <span class="suggestion-artist-badge">Artist</span>
            </div>
          `;
        }).join('');
        html += '</div>';

        $searchSuggestions.innerHTML = html;
        $searchSuggestions.style.display = 'block';
        if ($emptyState) $emptyState.style.visibility = 'hidden';
        activeSuggestIndex = -1;

        $searchSuggestions.querySelectorAll('.suggestion-artist-item').forEach(el => {
          el.addEventListener('click', () => {
            const name = el.dataset.name;
            $input.value = name;
            syncClearButtonVisibility();
            hideSearchSuggestions();
            // In Artists mode, perform artist search to render artist cards grid (never auto-jump to discography)
            performArtistSearch(name);
          });
        });

        const allItems = Array.from($searchSuggestions.querySelectorAll('.suggestion-artist-item'));
        allItems.forEach((el, idx) => {
          el.addEventListener('mouseenter', () => {
            allItems.forEach(i => i.classList.remove('active'));
            el.classList.add('active');
            activeSuggestIndex = idx;
          });
        });
        return;
      }

      // ── SONGS MODE: render featured top artist (if matched) + YouTube query predictions ──
      const topArtist = data.top_artist;
      const suggestions = (data.suggestions || []).filter(s => s && s.trim().length > 0);

      if (!topArtist && suggestions.length === 0) {
        hideSearchSuggestions();
        return;
      }

      let html = '';

      // 1. Featured Top Artist Entity Recommendation
      if (topArtist && topArtist.name) {
        const photoHtml = topArtist.photo
          ? `<img src="${esc(topArtist.photo)}" alt="${esc(topArtist.name)}" class="suggestion-artist-photo" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" /><div class="suggestion-artist-avatar-fallback" style="display:none;">${ICON_SUGGEST_ARTIST}</div>`
          : `<div class="suggestion-artist-avatar-fallback">${ICON_SUGGEST_ARTIST}</div>`;

        const countryLabel = topArtist.country
          ? `<span class="suggestion-artist-country" title="${esc(topArtist.country)}">${topArtist.flag ? `${esc(topArtist.flag)} ` : ''}${esc(topArtist.country)}</span>`
          : (topArtist.flag ? `<span class="suggestion-artist-country">${esc(topArtist.flag)}</span>` : '');

        const metaItems = [];
        if (countryLabel) metaItems.push(countryLabel);
        metaItems.push(esc(topArtist.genre || 'Artist'));

        html += `
          <div class="suggestion-artist-item" data-type="artist" data-artist-id="${esc(topArtist.artist_id || '')}" data-name="${esc(topArtist.name)}" role="option" tabindex="-1">
            <div class="suggestion-artist-avatar" aria-hidden="true">
              ${photoHtml}
            </div>
            <div class="suggestion-artist-info">
              <span class="suggestion-artist-name">${highlightMatch(topArtist.name, typedQuery)}</span>
              <div class="suggestion-artist-meta">
                ${metaItems.join(' • ')}
              </div>
            </div>
            <span class="suggestion-artist-badge">Artist</span>
          </div>
        `;
      }

      // Divider if both artist and query predictions exist
      if (topArtist && suggestions.length > 0) {
        html += '<div class="suggestion-divider" aria-hidden="true"></div>';
      }

      // 2. Query Autocomplete Predictions
      if (suggestions.length > 0) {
        html += '<div class="suggestion-queries-list">';
        html += suggestions.map((sugg) => `
          <div class="suggestion-item" data-type="query" data-query="${esc(sugg)}" role="option" tabindex="-1">
            ${ICON_SUGGEST_SEARCH}
            <span class="suggestion-item-text">${highlightMatch(sugg, typedQuery)}</span>
            ${ICON_SUGGEST_ARROW}
          </div>
        `).join('');
        html += '</div>';
      }

      $searchSuggestions.innerHTML = html;
      $searchSuggestions.style.display = 'block';
      activeSuggestIndex = -1;

      $searchSuggestions.querySelectorAll('.suggestion-artist-item').forEach(el => {
        el.addEventListener('click', () => {
          const name = el.dataset.name;
          $input.value = name;
          syncClearButtonVisibility();
          hideSearchSuggestions();
          performSearch(name);
        });
      });

      $searchSuggestions.querySelectorAll('.suggestion-item').forEach(el => {
        el.addEventListener('click', () => {
          const q = el.dataset.query;
          $input.value = q;
          syncClearButtonVisibility();
          hideSearchSuggestions();
          performSearch(q);
        });
      });

      const allItems = Array.from($searchSuggestions.querySelectorAll('.suggestion-artist-item, .suggestion-item'));
      allItems.forEach((el, idx) => {
        el.addEventListener('mouseenter', () => {
          allItems.forEach(i => i.classList.remove('active'));
          el.classList.add('active');
          activeSuggestIndex = idx;
        });
      });
    }

    async function fetchSearchSuggestions(query) {
      if (isSearching) return;
      const q = query.trim();
      if (!q || q.startsWith('http://') || q.startsWith('https://')) {
        hideSearchSuggestions();
        return;
      }

      const cacheKey = `${searchMode}:${q.toLowerCase()}`;
      if (suggestCache.has(cacheKey)) {
        if (!isSearching) {
          renderSearchSuggestions(suggestCache.get(cacheKey), q);
        }
        return;
      }

      if (suggestAbortCtrl) {
        suggestAbortCtrl.abort();
      }
      suggestAbortCtrl = new AbortController();

      try {
        const res = await fetch(`/api/suggest?q=${encodeURIComponent(q)}&mode=${searchMode}`, {
          signal: suggestAbortCtrl.signal,
          headers: { 'Accept': 'application/json' }
        });
        if (!res.ok || isSearching) return;
        const data = await res.json();
        suggestCache.set(cacheKey, data);
        if (suggestCache.size > 200) {
          const firstKey = suggestCache.keys().next().value;
          suggestCache.delete(firstKey);
        }
        if (!isSearching && $input.value.trim().toLowerCase() === q.toLowerCase()) {
          renderSearchSuggestions(data, q);
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.debug('[Suggest Error]', err);
        }
      }
    }

    function syncClearButtonVisibility() {
      if (!$searchClearBtn) return;
      if ($input.value.trim().length > 0) {
        $searchClearBtn.style.display = 'inline-flex';
      } else {
        $searchClearBtn.style.display = 'none';
      }
    }

    $input.addEventListener('input', () => {
      syncClearButtonVisibility();
      clearTimeout(suggestDebounceTimer);
      const val = $input.value.trim();
      if (!val || val.startsWith('http://') || val.startsWith('https://')) {
        hideSearchSuggestions();
        return;
      }
      suggestDebounceTimer = setTimeout(() => {
        fetchSearchSuggestions(val);
      }, 90);
    });

    $input.addEventListener('blur', () => {
      setTimeout(() => {
        hideSearchSuggestions();
      }, 150);
    });

    // Dismiss suggestions when clicking anywhere outside search form
    document.addEventListener('click', (e) => {
      if ($form && !$form.contains(e.target)) {
        hideSearchSuggestions();
      }
    });

    if ($searchClearBtn) {
      $searchClearBtn.addEventListener('click', () => {
        $input.value = '';
        syncClearButtonVisibility();
        hideSearchSuggestions();
        $input.focus();
      });
    }

    $form.addEventListener('submit', (e) => {
      e.preventDefault();
      hideSearchSuggestions();
      if ($input) $input.blur();
      const q = $input.value.trim();
      if (q) performSearch(q);
    });

    // Keyboard navigation (ArrowDown, ArrowUp, Enter, Escape)
    $input.addEventListener('keydown', (e) => {
      const isVisible = $searchSuggestions && $searchSuggestions.style.display === 'block';
      const items = isVisible ? Array.from($searchSuggestions.querySelectorAll('.suggestion-artist-item, .suggestion-item')) : [];

      if (e.key === 'ArrowDown') {
        if (!isVisible) {
          const val = $input.value.trim();
          if (val) fetchSearchSuggestions(val);
          return;
        }
        e.preventDefault();
        if (items.length > 0) {
          activeSuggestIndex = (activeSuggestIndex + 1) % items.length;
          items.forEach((it, idx) => {
            if (idx === activeSuggestIndex) {
              it.classList.add('active');
              it.scrollIntoView({ block: 'nearest' });
            } else {
              it.classList.remove('active');
            }
          });
        }
      } else if (e.key === 'ArrowUp') {
        if (isVisible && items.length > 0) {
          e.preventDefault();
          activeSuggestIndex = (activeSuggestIndex - 1 + items.length) % items.length;
          items.forEach((it, idx) => {
            if (idx === activeSuggestIndex) {
              it.classList.add('active');
              it.scrollIntoView({ block: 'nearest' });
            } else {
              it.classList.remove('active');
            }
          });
        }
      } else if (e.key === 'Enter') {
        if (isVisible && activeSuggestIndex >= 0 && items[activeSuggestIndex]) {
          e.preventDefault();
          e.stopPropagation();
          items[activeSuggestIndex].click();
        } else {
          hideSearchSuggestions();
          $form.dispatchEvent(new Event('submit'));
        }
      } else if (e.key === 'Escape') {
        if (isVisible) {
          e.preventDefault();
          e.stopPropagation();
          hideSearchSuggestions();
        } else {
          $input.value = '';
          syncClearButtonVisibility();
        }
      }
    });

    // Close suggestions on click outside
    document.addEventListener('pointerdown', (e) => {
      if ($form && !$form.contains(e.target)) {
        hideSearchSuggestions();
      }
    });

    // ── Keyboard Shortcuts ────────────────────────────────────
    let shortcutTipShown = false;
    document.addEventListener('keydown', (e) => {
      // Don't hijack shortcuts when typing in inputs, textareas, selects, or contenteditable
      const targetTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
      if (['input', 'textarea', 'select'].includes(targetTag) || document.activeElement?.isContentEditable) {
        return;
      }
      // Don't trigger on modifier keys
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === ' ') {
        e.preventDefault();
        if (currentPlayingBtn) {
          if (audioPlayer.paused) {
            audioPlayer.play();
            updateCurrentPlayingBtn(true);
          } else {
            audioPlayer.pause();
          }
        }
      } else if (e.key === 'Escape') {
        resetCurrentPlayingBtn();
        $volumeControl.classList.remove('show');
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        hideMiniPlayer();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const newVol = Math.min(1, parseFloat($volumeSlider.value) + 0.1);
        $volumeSlider.value = newVol;
        audioPlayer.volume = newVol;
        localStorage.setItem('melodyxx_volume', newVol);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const newVol = Math.max(0, parseFloat($volumeSlider.value) - 0.1);
        $volumeSlider.value = newVol;
        audioPlayer.volume = newVol;
        localStorage.setItem('melodyxx_volume', newVol);
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

    // ── In-App Update Notification System ──────────────────────
    const $updateBanner = document.getElementById('update-notification-banner');
    const $updateNewVersion = document.getElementById('update-new-version');
    const $btnUpdateReload = document.getElementById('btn-update-reload');
    const $btnUpdateDismiss = document.getElementById('btn-update-dismiss');

    let currentAppVersion = null;
    let isUpdateBannerShown = false;
    let newWorkerWaiting = null;

    function showUpdateNotification(newVersion) {
      if (isUpdateBannerShown) return;
      isUpdateBannerShown = true;

      if ($updateNewVersion) {
        $updateNewVersion.textContent = newVersion;
      }
      if ($updateBanner) {
        $updateBanner.style.display = 'flex';
      }

      toast('info', `New update available (${newVersion})! Click Refresh to update.`);
    }

    function checkForUpdates() {
      if (isUpdateBannerShown) return;

      fetch(`/api/version?_t=${Date.now()}`, { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then(data => {
          const remoteVersion = (data && data.version) ? String(data.version).trim() : null;
          if (!remoteVersion) return;
          const formattedRemote = remoteVersion.startsWith('v') ? remoteVersion : `v${remoteVersion}`;

          if (!currentAppVersion) {
            currentAppVersion = formattedRemote;
            return;
          }

          if (formattedRemote !== currentAppVersion) {
            showUpdateNotification(formattedRemote);
          }
        })
        .catch(err => {
          console.debug('[Update Check] Silent failure:', err);
        });
    }

    if ($btnUpdateReload) {
      $btnUpdateReload.addEventListener('click', async () => {
        $btnUpdateReload.textContent = 'Updating…';
        $btnUpdateReload.disabled = true;

        const targetVer = $updateNewVersion ? $updateNewVersion.textContent.trim() : '';
        try {
          sessionStorage.setItem('melodyxx_just_updated', targetVer || 'true');
        } catch (_) {}

        if (newWorkerWaiting) {
          try {
            newWorkerWaiting.postMessage({ action: 'skipWaiting' });
          } catch (_) {}
        }

        // Clean out client-side cache storages before reload
        if ('caches' in window) {
          try {
            const keys = await caches.keys();
            await Promise.all(keys.map(k => caches.delete(k)));
          } catch (_) {}
        }

        setTimeout(() => {
          window.location.reload(true);
        }, 200);
      });
    }

    if ($btnUpdateDismiss) {
      $btnUpdateDismiss.addEventListener('click', () => {
        if ($updateBanner) {
          $updateBanner.style.display = 'none';
        }
      });
    }

    // ── PWA / Service Worker Registration ─────────────────────
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
          .then((reg) => {
            console.log('[SW] Registered, scope:', reg.scope);

            // Check if there is already a waiting worker
            if (reg.waiting) {
              newWorkerWaiting = reg.waiting;
              checkForUpdates();
            }

            reg.addEventListener('updatefound', () => {
              const installingWorker = reg.installing;
              if (!installingWorker) return;
              installingWorker.addEventListener('statechange', () => {
                if (installingWorker.state === 'installed' && navigator.serviceWorker.controller) {
                  newWorkerWaiting = installingWorker;
                  checkForUpdates();
                }
              });
            });
          })
          .catch((err) => console.warn('[SW] Registration failed:', err));
      });
    }

    // Periodic check every 60s & on tab refocus
    setInterval(checkForUpdates, 60 * 1000);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        checkForUpdates();
      }
    });
    window.addEventListener('focus', checkForUpdates);

    // ── Focus search on load ──────────────────────────────────
    window.addEventListener('load', () => {
      $input.focus();
      // Request notification permission after a short delay
      setTimeout(requestNotificationPermission, 3000);
    });

    // ── Post-Update Success Feedback ──────────────────────────
    let hasCheckedPostUpdate = false;

    function checkPostUpdateFeedback(currentVer) {
      if (hasCheckedPostUpdate) return;
      hasCheckedPostUpdate = true;

      let justUpdated = null;
      try {
        justUpdated = sessionStorage.getItem('melodyxx_just_updated');
        if (justUpdated) {
          sessionStorage.removeItem('melodyxx_just_updated');
        }
      } catch (_) {}

      let lastSeenVer = null;
      try {
        lastSeenVer = localStorage.getItem('melodyxx_last_seen_ver');
        if (currentVer) {
          localStorage.setItem('melodyxx_last_seen_ver', currentVer);
        }
      } catch (_) {}

      // Show update celebration toast if explicitly reloaded from update banner OR version incremented
      if (justUpdated || (lastSeenVer && currentVer && lastSeenVer !== currentVer)) {
        setTimeout(() => {
          const displayVer = currentVer || (justUpdated && justUpdated !== 'true' ? justUpdated : '');
          const verLabel = displayVer ? ` to <strong>${esc(displayVer)}</strong>` : '';
          toast('success', `Update successful${verLabel}! Melodyxx is running the latest version.`, 5000);

          const $versionBadge = document.getElementById('version-badge');
          if ($versionBadge) {
            $versionBadge.classList.add('badge-highlight-pulse');
            setTimeout(() => $versionBadge.classList.remove('badge-highlight-pulse'), 6000);
          }
        }, 600);
      }
    }

    // ── Release Log & What's New Drawer ────────────────────────
    let cachedChangelog = null;
    let isReleaseLogClosing = false;
    let isChangelogRendered = false;

    function checkReleaseLogBadge(latestVersion) {
      if (!$releaseLogBadge) return;
      try {
        const lastSeen = localStorage.getItem('melodyxx_last_seen_release');
        if (latestVersion && lastSeen !== latestVersion) {
          $releaseLogBadge.style.display = 'block';
        } else {
          $releaseLogBadge.style.display = 'none';
        }
      } catch (_) {}
    }

    function openReleaseLog() {
      if (!$releaseLogModal) return;
      $releaseLogModal.classList.remove('closing');
      $releaseLogModal.style.display = 'flex';
      document.body.style.overflow = 'hidden';

      if ($releaseLogBadge) {
        $releaseLogBadge.style.display = 'none';
      }

      const activeVer = currentAppVersion || 'v1.6.2';
      try {
        localStorage.setItem('melodyxx_last_seen_release', activeVer);
      } catch (_) {}

      if (!isChangelogRendered) {
        if (cachedChangelog) {
          renderChangelog(cachedChangelog);
        } else {
          fetchChangelog();
        }
      }
    }

    function closeReleaseLog() {
      if (!$releaseLogModal || isReleaseLogClosing || $releaseLogModal.style.display === 'none') return;
      isReleaseLogClosing = true;
      $releaseLogModal.classList.add('closing');
      setTimeout(() => {
        $releaseLogModal.style.display = 'none';
        $releaseLogModal.classList.remove('closing');
        document.body.style.overflow = '';
        isReleaseLogClosing = false;
      }, 120);
    }

    async function fetchChangelog() {
      if (!$releaseModalBody) return;
      try {
        const res = await fetch(`/api/changelog?_t=${Date.now()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        cachedChangelog = data;
        renderChangelog(data);
      } catch (err) {
        try {
          const fallbackRes = await fetch(`/static/changelog.json?_t=${Date.now()}`);
          const fallbackData = await fallbackRes.json();
          cachedChangelog = fallbackData;
          renderChangelog(fallbackData);
        } catch (fbErr) {
          if (!isChangelogRendered) {
            $releaseModalBody.innerHTML = `
              <div class="release-loading-state">
                <span>Failed to load release history. Please try again.</span>
              </div>
            `;
          }
        }
      }
    }

    function renderChangelog(items) {
      if (!$releaseModalBody) return;
      if (!items || items.length === 0) {
        $releaseModalBody.innerHTML = `
          <div class="release-loading-state">
            <span>No release notes found.</span>
          </div>
        `;
        return;
      }

      $releaseModalBody.innerHTML = items.map((item, idx) => {
        const isLatest = idx === 0;
        const type = (item.type || 'feature').toLowerCase();
        const typeLabel = type.charAt(0).toUpperCase() + type.slice(1);
        const highlightsHtml = (item.highlights || []).map(hl => `
          <li class="release-highlight-item">
            <span class="release-highlight-bullet" aria-hidden="true"></span>
            <span>${esc(hl)}</span>
          </li>
        `).join('');

        return `
          <article class="release-entry ${isLatest ? 'latest' : ''}">
            <div class="release-entry-header">
              <div class="release-entry-left">
                <span class="release-version-tag">${esc(item.version)}</span>
                <span class="release-type-badge ${esc(type)}">${esc(typeLabel)}</span>
              </div>
              <div class="release-timestamp">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                <span>${esc(item.date)} • ${esc(item.time || '')}</span>
              </div>
            </div>
            <div class="release-entry-title">${esc(item.title)}</div>
            <ul class="release-highlights">
              ${highlightsHtml}
            </ul>
          </article>
        `;
      }).join('');
      isChangelogRendered = true;
    }

    if ($btnReleaseLog) {
      $btnReleaseLog.addEventListener('click', openReleaseLog);
    }
    if ($btnReleaseClose) {
      $btnReleaseClose.addEventListener('click', closeReleaseLog);
    }
    if ($releaseLogModal) {
      $releaseLogModal.addEventListener('click', (e) => {
        if (e.target === $releaseLogModal) closeReleaseLog();
      });
    }
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && $releaseLogModal && $releaseLogModal.style.display === 'flex') {
        closeReleaseLog();
      }
    });

    // ── Bug Reporter & User Feedback ───────────────────────────
    let selectedReportFile = null;
    let selectedReportPreviewUrl = null;
    let isReportModalClosing = false;
    let isReportSubmitting = false;
    let reportCooldownTimer = null;

    function formatFileSize(bytes) {
      if (!bytes || bytes === 0) return '0 B';
      if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
      return `${Math.round(bytes / 1024)} KB`;
    }

    function formatCooldownTime(totalSeconds) {
      const m = Math.floor(totalSeconds / 60);
      const s = totalSeconds % 60;
      if (m > 0) {
        return `${m}m ${s}s`;
      }
      return `${s}s`;
    }

    function getReportRemainingCooldownSec() {
      const lastSent = parseInt(localStorage.getItem('melodyxx_last_report_ts') || '0', 10);
      const now = Date.now();
      const cooldownMs = 5 * 60 * 1000; // 5 minutes
      const remainingSec = Math.ceil((cooldownMs - (now - lastSent)) / 1000);
      return remainingSec > 0 ? remainingSec : 0;
    }

    function syncReportCooldownUI() {
      const remainingSec = getReportRemainingCooldownSec();
      const submitText = $btnReportSubmit ? $btnReportSubmit.querySelector('.submit-text') : null;

      if (remainingSec > 0) {
        const timeStr = formatCooldownTime(remainingSec);
        if (submitText && !isReportSubmitting) {
          submitText.textContent = `Wait ${timeStr}`;
        }
        if ($btnReportSubmit && !isReportSubmitting) {
          $btnReportSubmit.title = `Cooldown active. Please wait ${timeStr}.`;
        }
        if (!reportCooldownTimer) {
          reportCooldownTimer = setInterval(syncReportCooldownUI, 1000);
        }
      } else {
        if (reportCooldownTimer) {
          clearInterval(reportCooldownTimer);
          reportCooldownTimer = null;
        }
        if (submitText && !isReportSubmitting) {
          submitText.textContent = 'Send Report';
        }
        if ($btnReportSubmit && !isReportSubmitting) {
          $btnReportSubmit.title = 'Send bug report or feedback';
        }
      }
    }

    function openBugReportModal() {
      if (!$bugReportModal) return;
      $bugReportModal.classList.remove('closing');
      $bugReportModal.setAttribute('aria-hidden', 'false');
      $bugReportModal.style.display = 'flex';
      document.body.style.overflow = 'hidden';

      // Populate diagnostics
      const activeVer = currentAppVersion || 'v1.10.2';
      if ($diagAppVersion) $diagAppVersion.textContent = activeVer;
      if ($diagPlatform) {
        const platform = navigator.userAgentData?.platform || navigator.platform || 'Unknown';
        const browser = navigator.userAgent.split(' ')[0] || 'Browser';
        $diagPlatform.textContent = `${platform} • ${browser}`;
      }
      if ($diagScreen) $diagScreen.textContent = `${window.screen.width} × ${window.screen.height}`;
      if ($diagPage) $diagPage.textContent = window.location.href;

      syncReportCooldownUI();

      setTimeout(() => {
        if ($reportName && !$reportName.value) {
          $reportName.focus();
        } else if ($reportDescription) {
          $reportDescription.focus();
        }
      }, 100);
    }

    function closeBugReportModal() {
      if (!$bugReportModal || isReportModalClosing || $bugReportModal.style.display === 'none') return;
      isReportModalClosing = true;
      $bugReportModal.classList.add('closing');
      if (reportCooldownTimer) {
        clearInterval(reportCooldownTimer);
        reportCooldownTimer = null;
      }
      setTimeout(() => {
        $bugReportModal.style.display = 'none';
        $bugReportModal.setAttribute('aria-hidden', 'true');
        $bugReportModal.classList.remove('closing');
        document.body.style.overflow = '';
        isReportModalClosing = false;
      }, 120);
    }

    function clearReportFile() {
      selectedReportFile = null;
      if (selectedReportPreviewUrl) {
        URL.revokeObjectURL(selectedReportPreviewUrl);
        selectedReportPreviewUrl = null;
      }
      if ($reportFileInput) $reportFileInput.value = '';
      if ($previewMediaWrap) $previewMediaWrap.innerHTML = '';
      if ($previewFilename) $previewFilename.textContent = '';
      if ($previewFilesize) $previewFilesize.textContent = '';
      if ($dropzonePreview) $dropzonePreview.style.display = 'none';
      if ($dropzoneIdle) $dropzoneIdle.style.display = 'flex';
    }

    function handleReportFileSelect(file) {
      if (!file) return;
      const isImage = file.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name);
      const isVideo = file.type.startsWith('video/') || /\.(mp4|webm|mov)$/i.test(file.name);

      if (!isImage && !isVideo) {
        toast('error', 'Only images (PNG, JPG, WEBP) or videos (MP4, WEBM) are supported.');
        clearReportFile();
        return;
      }

      if (isImage && file.size > 10 * 1024 * 1024) {
        toast('error', 'Image size exceeds 10 MB limit.');
        clearReportFile();
        return;
      }

      if (isVideo && file.size > 30 * 1024 * 1024) {
        toast('error', 'Video size exceeds 30 MB limit.');
        clearReportFile();
        return;
      }

      if (selectedReportPreviewUrl) {
        URL.revokeObjectURL(selectedReportPreviewUrl);
      }

      selectedReportFile = file;
      selectedReportPreviewUrl = URL.createObjectURL(file);

      if ($dropzoneIdle) $dropzoneIdle.style.display = 'none';
      if ($dropzonePreview) $dropzonePreview.style.display = 'flex';
      if ($previewFilename) $previewFilename.textContent = file.name;
      if ($previewFilesize) $previewFilesize.textContent = formatFileSize(file.size);

      if ($previewMediaWrap) {
        if (isImage) {
          $previewMediaWrap.innerHTML = `<img src="${selectedReportPreviewUrl}" alt="Preview thumbnail" />`;
        } else {
          $previewMediaWrap.innerHTML = `<video src="${selectedReportPreviewUrl}" muted playsinline></video>`;
        }
      }
    }

    if ($reportFileInput) {
      $reportFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          handleReportFileSelect(e.target.files[0]);
        }
      });
    }

    if ($reportDropzone) {
      ['dragenter', 'dragover'].forEach(evtName => {
        $reportDropzone.addEventListener(evtName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          $reportDropzone.classList.add('dragover');
        });
      });

      ['dragleave', 'drop'].forEach(evtName => {
        $reportDropzone.addEventListener(evtName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          $reportDropzone.classList.remove('dragover');
        });
      });

      $reportDropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        if (dt && dt.files && dt.files[0]) {
          handleReportFileSelect(dt.files[0]);
        }
      });
    }

    if ($btnPreviewRemove) {
      $btnPreviewRemove.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        clearReportFile();
      });
    }

    if ($reportDescription && $reportCharCount) {
      $reportDescription.addEventListener('input', () => {
        const len = $reportDescription.value.length;
        $reportCharCount.textContent = `${len} / 1000`;
        if (len >= 950) {
          $reportCharCount.style.color = '#f43f5e';
        } else {
          $reportCharCount.style.color = '#64748b';
        }
      });
    }

    if ($reportForm) {
      $reportForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (isReportSubmitting) return;

        // Check local cooldown
        const remainingSec = getReportRemainingCooldownSec();
        if (remainingSec > 0) {
          const timeStr = formatCooldownTime(remainingSec);
          toast('info', `Please wait <strong>${timeStr}</strong> before submitting another report.`);
          syncReportCooldownUI();
          return;
        }

        const desc = ($reportDescription?.value || '').trim();
        if (desc.length < 8) {
          toast('error', 'Please provide a description of at least 8 characters.');
          if ($reportDescription) $reportDescription.focus();
          return;
        }

        isReportSubmitting = true;
        const submitIcon = $btnReportSubmit ? $btnReportSubmit.querySelector('.submit-icon') : null;
        const submitSpinner = $btnReportSubmit ? $btnReportSubmit.querySelector('.submit-spinner') : null;
        const submitText = $btnReportSubmit ? $btnReportSubmit.querySelector('.submit-text') : null;

        if ($btnReportSubmit) $btnReportSubmit.disabled = true;
        if (submitSpinner) submitSpinner.style.display = 'inline-block';
        if (submitIcon) submitIcon.style.display = 'none';
        if (submitText) submitText.textContent = 'Sending…';

        try {
          const formData = new FormData();
          formData.append('name', ($reportName?.value || '').trim());
          formData.append('email', ($reportEmail?.value || '').trim());
          formData.append('category', $reportCategory?.value || 'Bug / Error');
          formData.append('description', desc);
          formData.append('company_website', document.getElementById('report-hp-field')?.value || '');
          formData.append('platform_info', `${navigator.userAgentData?.platform || navigator.platform || 'Unknown'} • ${navigator.userAgent || 'Browser'}`);
          formData.append('screen_res', `${window.screen.width}x${window.screen.height}`);
          formData.append('current_url', window.location.href);
          formData.append('app_version', currentAppVersion || 'v1.10.0');

          if (selectedReportFile) {
            formData.append('media', selectedReportFile, selectedReportFile.name);
          }

          const res = await fetch('/api/report', {
            method: 'POST',
            body: formData,
          });

          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            throw new Error(data.detail || `Server returned error (${res.status})`);
          }

          toast('success', 'Thank you! Your report has been submitted.');
          localStorage.setItem('melodyxx_last_report_ts', String(Date.now()));
          syncReportCooldownUI();

          // Reset form
          $reportForm.reset();
          if ($reportCharCount) $reportCharCount.textContent = '0 / 1000';
          clearReportFile();
          closeBugReportModal();

        } catch (err) {
          toast('error', err.message || 'Failed to submit report. Please try again.');
        } finally {
          isReportSubmitting = false;
          if ($btnReportSubmit) $btnReportSubmit.disabled = false;
          if (submitSpinner) submitSpinner.style.display = 'none';
          if (submitIcon) submitIcon.style.display = 'inline-block';
          if (submitText) submitText.textContent = 'Send Report';
        }
      });
    }

    if ($btnOpenBugReport) {
      $btnOpenBugReport.addEventListener('click', openBugReportModal);
    }
    if ($btnReportClose) {
      $btnReportClose.addEventListener('click', closeBugReportModal);
    }
    if ($btnReportCancel) {
      $btnReportCancel.addEventListener('click', closeBugReportModal);
    }
    if ($bugReportModal) {
      $bugReportModal.addEventListener('click', (e) => {
        if (e.target === $bugReportModal) closeBugReportModal();
      });
    }
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && $bugReportModal && $bugReportModal.style.display === 'flex') {
        closeBugReportModal();
      }
    });

    // ── Load and display version badge ─────────────────────────
    function loadVersion() {
      const $versionLink = document.getElementById('version-link') || document.getElementById('commit-link');
      if (!$versionLink) return;

      fetch(`/api/version?_t=${Date.now()}`, { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then(data => {
          const version = (data && data.version) ? String(data.version).trim() : 'v1.0.0';
          const formatted = version.startsWith('v') ? version : `v${version}`;
          $versionLink.textContent = formatted;
          $versionLink.href = data.version_url || 'https://github.com/iFelzz/melodyxx';
          $versionLink.title = `Melodyxx ${formatted}`;

          checkPostUpdateFeedback(formatted);
          checkReleaseLogBadge(formatted);
          fetchChangelog();

          if (!currentAppVersion) {
            currentAppVersion = formatted;
          } else if (formatted !== currentAppVersion) {
            showUpdateNotification(formatted);
          }
        })
        .catch(err => {
          console.debug('[Version] Could not fetch live version:', err);
        });
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', loadVersion);
    } else {
      loadVersion();
    }
    window.addEventListener('load', loadVersion);
