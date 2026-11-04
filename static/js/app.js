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

    // Artist & Mode DOM refs
    const $tabModeSongs = document.getElementById('tab-mode-songs');
    const $tabModeArtists = document.getElementById('tab-mode-artists');
    const $artistSearchResults = document.getElementById('artist-search-results');
    const $artistResultsGrid = document.getElementById('artist-results-grid');
    const $artistResultsCount = document.getElementById('artist-results-count');

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

    // Global state
    let searchMode = 'songs'; // 'songs' | 'artists'
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

    const TRACK_ICON_PLAY = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
    const TRACK_ICON_PAUSE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;

    function resetCurrentPlayingBtn() {
      if (!currentPlayingBtn) return;
      if (currentPlayingBtn.classList.contains('btn-track-play')) {
        currentPlayingBtn.innerHTML = TRACK_ICON_PLAY;
      } else {
        currentPlayingBtn.innerHTML = ICON_PLAY;
        currentPlayingBtn.classList.remove('playing');
      }
      currentPlayingBtn = null;
    }

    function updateCurrentPlayingBtn(isPlaying) {
      if (!currentPlayingBtn) return;
      if (currentPlayingBtn.classList.contains('btn-track-play')) {
        currentPlayingBtn.innerHTML = isPlaying ? TRACK_ICON_PAUSE : TRACK_ICON_PLAY;
      } else {
        currentPlayingBtn.innerHTML = isPlaying ? ICON_PAUSE : ICON_PLAY;
        currentPlayingBtn.classList.toggle('playing', isPlaying);
      }
    }

    // ── Build card HTML ───────────────────────────────────────

    function buildCard(item, index) {
      const views = formatViews(item.views);
      const cardId = `card-${index}`;
      const btnId = `btn-dl-${index}`;

      const is128 = currentPreferredQuality === '128';
      const is192 = currentPreferredQuality === '192';
      const is320 = currentPreferredQuality === '320';

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
          <button class="quality-btn ${is128 ? 'active' : ''}" data-card="${index}" data-q="128" aria-pressed="${is128}">128k</button>
          <button class="quality-btn ${is192 ? 'active' : ''}" data-card="${index}" data-q="192" aria-pressed="${is192}">192k</button>
          <button class="quality-btn ${is320 ? 'active' : ''}" data-card="${index}" data-q="320" aria-pressed="${is320}">320k</button>
        </div>
        <button
          class="btn-download"
          id="${btnId}"
          data-url="${esc(item.url)}"
          data-title="${esc(item.title)}"
          data-quality="${currentPreferredQuality}"
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

      // Attach quality selector handlers (Smart sync: clicking any card syncs all cards + header)
      document.querySelectorAll('.quality-btn').forEach(qBtn => {
        qBtn.addEventListener('click', () => {
          setGlobalQuality(qBtn.dataset.q);
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

      // 2. Sync all card quality buttons
      document.querySelectorAll('.quality-btn').forEach(btn => {
        const isActive = btn.dataset.q === currentPreferredQuality;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });

      // 3. Update all card download buttons
      document.querySelectorAll('.btn-download').forEach(dlBtn => {
        dlBtn.dataset.quality = currentPreferredQuality;
      });
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
        } else if (lastArtistSearchResults.length > 0) {
          showState('artists');
        } else {
          showState('empty');
        }
      });
    }

    // ── Search ───────────────────────────────────────────────

    async function performSearch(query) {
      if (!query || !query.trim()) return;
      const q = query.trim();

      if (searchMode === 'artists') {
        await performArtistSearch(q);
        return;
      }

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
      }
    }

    // ── Artist Search & Discography ───────────────────────────

    async function performArtistSearch(query) {
      showState('loading');
      $loadingText.textContent = `Searching discography for ${query}…`;
      $searchBtn.disabled = true;

      try {
        const res = await fetch(`/api/artist/search?q=${encodeURIComponent(query)}&limit=8`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

        const artists = data.results || [];
        lastArtistSearchResults = artists;

        if (artists.length === 0) {
          showState('no-results');
          return;
        }

        const normQ = query.trim().toLowerCase();
        // If only 1 artist found OR if the top artist is an exact match (e.g. "Alan Walker"),
        // jump straight into their discography page!
        if (artists.length === 1 || (artists[0] && artists[0].name.trim().toLowerCase() === normQ)) {
          await loadArtistDiscography(artists[0].artist_id);
          return;
        }

        renderArtistResults(artists);
      } catch (err) {
        console.error('[Artist Search Error]', err);
        $errorMsg.textContent = err.message || 'Failed to search artists. Please try again.';
        showState('error');
      } finally {
        $searchBtn.disabled = false;
      }
    }

    function renderArtistResults(artists) {
      $artistResultsCount.textContent = `${artists.length} artist${artists.length === 1 ? '' : 's'} found`;
      $artistResultsGrid.innerHTML = artists.map(art => `
        <div class="artist-card" data-artist-id="${art.artist_id}">
          <div class="artist-card-avatar" style="display:flex;align-items:center;justify-content:center;font-size:1.6rem;">🎤</div>
          <div class="artist-card-info">
            <div class="artist-card-name" title="${esc(art.name)}">${esc(art.name)}</div>
            <div class="artist-card-genre">${esc(art.genre)}</div>
          </div>
        </div>
      `).join('');

      $artistResultsGrid.querySelectorAll('.artist-card').forEach(card => {
        card.addEventListener('click', () => {
          loadArtistDiscography(card.dataset.artistId);
        });
      });

      showState('artists');
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
        if (lastArtistSearchResults.length > 1) {
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
      $artistAvatar.src = disco.artwork_url || '/static/logo.png';
      $artistAvatar.onerror = () => { $artistAvatar.src = '/static/logo.png'; };

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
              audioPlayer.play();
            } else {
              audioPlayer.pause();
            }
            return;
          }

          // Different button clicked: reset previous active button icon back to PLAY
          resetCurrentPlayingBtn();

          audioPlayer.src = prevUrl;
          await audioPlayer.play();
          showMiniPlayer(btn.dataset.title, btn.dataset.artist, btn.dataset.art);
          btn.innerHTML = TRACK_ICON_PAUSE;
          currentPlayingBtn = btn;
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

        // Safe inter-download delay (2.5s) to avoid download manager thrashing & socket exhaustion
        if (i < total - 1 && !cancelBatchDownload) {
          $batchProgressStatus.textContent = 'Waiting for next track (2.5s)…';
          await new Promise(r => setTimeout(r, 2500));
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
        toast('success', `🎵 Mengalirkan <strong>${esc(item.title)}</strong> langsung ke browser!`);

        if (Notification.permission === 'granted') {
          new Notification('✅ Download Started!', {
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
      const $commitLink = document.getElementById('commit-link');
      if (!$commitLink) return;

      fetch(`/api/version?_t=${Date.now()}`, { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then(data => {
          const commit = (data && data.commit) ? String(data.commit).trim() : '';
          if (commit && commit !== 'latest' && commit !== 'unknown') {
            $commitLink.textContent = `#${commit}`;
            $commitLink.href = data.commit_url || `https://github.com/iFelzz/listen-now/commit/${commit}`;
            $commitLink.title = `Commit ${commit} on GitHub`;
          }
        })
        .catch(err => {
          console.debug('[Version] Could not fetch live commit hash:', err);
        });
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', loadCommitHash);
    } else {
      loadCommitHash();
    }
    window.addEventListener('load', loadCommitHash);
