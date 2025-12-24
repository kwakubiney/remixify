/**
 * Remixify - Two-Phase Remix Selection
 * Phase 1: Preview remixes and let user select
 * Phase 2: Create playlist with selected tracks
 */

// State management
const state = {
    playlistName: '',
    playlistImage: '',
    originalUrl: '',
    tracks: [],
    selectedTracks: new Map(), // trackId -> track data
    csrfToken: '',
    currentTaskId: null,
    // Search & Progressive Reveal
    searchQuery: '',
    filteredTracks: [],
    visibleTracksCount: 20,
    tracksPerBatch: 20,
    // Filter by confidence
    activeFilter: null, // 'high', 'medium', 'none', or null for all
    // Audio preview
    audioPlayer: null,
    currentlyPlayingBtn: null,
    previewTimeout: null
};

const MANUAL_CONFIDENCE_LEVEL = 'manual';

// DOM Elements
let elements = {};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    elements = {
        // Phases
        phaseInput: document.getElementById('phase-input'),
        phaseSelection: document.getElementById('phase-selection'),
        phaseSuccess: document.getElementById('phase-success'),

        // Phase 1
        form: document.getElementById('playlist-form'),
        urlInput: document.getElementById('input_url'),
        submitBtn: document.getElementById('submit_btn'),
        progressSection: document.getElementById('progress-section'),
        progressBar: document.getElementById('progress-bar'),
        progressMessage: document.getElementById('progress-message'),
        recentPlaylists: document.getElementById('recent-playlists'),
        recentList: document.getElementById('recent-list'),

        // Phase 2
        backBtn: document.getElementById('back-btn'),
        playlistImage: document.getElementById('playlist-image'),
        playlistName: document.getElementById('playlist-name'),
        trackCount: document.getElementById('track-count'),
        summaryStats: document.getElementById('summary-stats'),
        statHigh: document.getElementById('stat-high'),
        statMedium: document.getElementById('stat-medium'),
        statNone: document.getElementById('stat-none'),
        selectAllHigh: document.getElementById('select-all-high'),
        selectAll: document.getElementById('select-all'),
        deselectAll: document.getElementById('deselect-all'),
        selectedCount: document.getElementById('selected-count'),
        trackSearch: document.getElementById('track-search'),
        trackList: document.getElementById('track-list'),
        showMoreWrapper: document.getElementById('show-more-wrapper'),
        showMoreBtn: document.getElementById('show-more-btn'),
        createBtn: document.getElementById('create-btn'),
        stickyBar: document.getElementById('sticky-bar'),
        stickySelectedCount: document.getElementById('sticky-selected-count'),

        // Phase 3
        successMessage: document.getElementById('success-message'),
        spotifyLink: document.getElementById('spotify-link'),
        newPlaylistBtn: document.getElementById('new-playlist-btn')
    };

    state.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    setupEventListeners();
    loadRecentPlaylists();
    loadPlaylistCount();
});

// Animated counter with rolling effect
function animateCounter(element, targetValue, duration = 1500) {
    const startValue = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Easing function for smooth deceleration
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const currentValue = Math.floor(startValue + (targetValue - startValue) * easeOutQuart);

        element.textContent = currentValue.toLocaleString();

        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = targetValue.toLocaleString();
        }
    }

    requestAnimationFrame(update);
}

// Load playlist count
async function loadPlaylistCount() {
    try {
        const response = await fetch('/playlist-count/');
        const data = await response.json();

        if (data.count > 0) {
            const counterEl = document.getElementById('playlist-counter');
            const numberEl = document.getElementById('counter-number');

            counterEl.style.display = 'inline-flex';

            // Start the rolling animation
            animateCounter(numberEl, data.count);
        }
    } catch (error) {
        console.log('Could not load playlist count:', error);
    }
}

// Load recent playlists
async function loadRecentPlaylists() {
    try {
        const response = await fetch('/recent-playlists/');
        const data = await response.json();

        if (data.playlists && data.playlists.length > 0) {
            renderRecentPlaylists(data.playlists);
        } else {
            // Hide section if no playlists
            elements.recentPlaylists.style.display = 'none';
        }
    } catch (error) {
        console.log('Could not load recent playlists:', error);
        // Hide section on error
        elements.recentPlaylists.style.display = 'none';
    }
}

function renderRecentPlaylists(playlists) {
    elements.recentList.innerHTML = playlists.map(playlist => `
        <a href="${playlist.url}" target="_blank" rel="noopener noreferrer" class="recent-card">
            <div class="recent-image">
                ${playlist.image
            ? `<img src="${playlist.image}" alt="${playlist.name}">`
            : `<div class="recent-placeholder">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <circle cx="12" cy="12" r="10"/>
                            <path d="M8 15C8.5 12 10.5 10 14 9"/>
                            <path d="M8 12C8.5 10 10 8.5 13 8"/>
                        </svg>
                       </div>`
        }
            </div>
            <div class="recent-info">
                <span class="recent-name">${playlist.name}</span>
                ${playlist.original_author && playlist.original_author !== 'Unknown' ? `<span class="recent-tracks">by ${playlist.original_author}</span>` : ''}
            </div>
        </a>
    `).join('');
}

function setupEventListeners() {
    // Phase 1: Form submission
    elements.form.addEventListener('submit', handleFormSubmit);

    // Phase 2: Selection controls
    elements.backBtn.addEventListener('click', goToPhase1);
    elements.selectAllHigh.addEventListener('click', selectAllHighConfidence);
    elements.selectAll.addEventListener('click', selectAllTracks);
    elements.deselectAll.addEventListener('click', deselectAllTracks);
    elements.createBtn.addEventListener('click', handleCreatePlaylist);

    // Search
    if (elements.trackSearch) {
        elements.trackSearch.addEventListener('input', (e) => {
            state.searchQuery = e.target.value;
            filterTracks();
        });
    }

    // Stat card filters
    setupStatCardFilters();

    // Show more button
    if (elements.showMoreBtn) {
        elements.showMoreBtn.addEventListener('click', loadMoreTracks);
    }

    // Phase 3: New playlist
    elements.newPlaylistBtn.addEventListener('click', goToPhase1);
}

function setupStatCardFilters() {
    const statCards = document.querySelectorAll('.stat-card');
    statCards.forEach(card => {
        card.addEventListener('click', () => {
            const filterType = card.classList.contains('stat-high') ? 'high' :
                card.classList.contains('stat-medium') ? 'medium' :
                    card.classList.contains('stat-none') ? 'none' : null;

            // Toggle filter
            if (state.activeFilter === filterType) {
                state.activeFilter = null;
                card.classList.remove('active');
            } else {
                // Remove active from all cards
                statCards.forEach(c => c.classList.remove('active'));
                state.activeFilter = filterType;
                card.classList.add('active');
            }

            filterTracks();
        });
    });
}

// ============ PHASE 1: Preview ============

async function handleFormSubmit(e) {
    e.preventDefault();

    const url = elements.urlInput.value.trim();
    state.originalUrl = url;
    if (!url) {
        // Shake the input to indicate error
        elements.urlInput.classList.add('shake');
        elements.urlInput.focus();
        setTimeout(() => elements.urlInput.classList.remove('shake'), 500);
        return;
    }

    // Show progress
    elements.progressSection.style.display = 'block';
    elements.submitBtn.disabled = true;
    elements.submitBtn.innerHTML = `
        <span class="btn-text">Searching...</span>
        <svg class="btn-icon spinning" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
        </svg>
    `;

    try {
        // Start preview task
        const formData = new FormData();
        formData.append('url', url);
        formData.append('csrfmiddlewaretoken', state.csrfToken);

        const response = await fetch('/preview/', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (data.error) throw new Error(data.error);

        state.currentTaskId = data.task_id;
        pollPreviewResult(data.task_id);

    } catch (error) {
        showError(error.message);
        resetPhase1();
    }
}

async function pollPreviewResult(taskId) {
    const progressUrl = `/celery-progress/${taskId}/`;

    // Use CeleryProgressBar for visual progress
    CeleryProgressBar.initProgressBar(progressUrl, {
        onProgress: function (progressBarElement, progressBarMessageElement, progress) {
            elements.progressBar.style.width = `${progress.percent}%`;
            elements.progressMessage.textContent = `Finding remixes... ${progress.current}/${progress.total} tracks`;
        },
        onSuccess: async function () {
            // Fetch the actual result
            try {
                const response = await fetch(`/preview/${taskId}/`);
                const data = await response.json();

                if (data.status === 'complete') {
                    state.playlistName = data.result.playlist_name;
                    state.playlistImage = data.result.playlist_image;
                    state.tracks = data.result.tracks;

                    renderTrackSelection(data.result);
                    goToPhase2();
                } else if (data.status === 'error') {
                    throw new Error(data.error);
                }
            } catch (error) {
                showError(error.message);
                resetPhase1();
            }
        },
        onTaskError: function (progressBarElement, progressBarMessageElement, excMessage) {
            // Extract the clean error message from backend exceptions
            let errorMessage = 'Failed to find remixes. Please try again.';

            if (excMessage) {
                // Check for ValueError (our user-facing errors)
                if (excMessage.includes('ValueError:')) {
                    const parts = excMessage.split('ValueError:');
                    if (parts.length > 1) {
                        let msg = parts[parts.length - 1].trim();
                        msg = msg.split('\n')[0];
                        if ((msg.startsWith('"') && msg.endsWith('"')) || (msg.startsWith("'") && msg.endsWith("'"))) {
                            msg = msg.slice(1, -1);
                        }
                        errorMessage = msg;
                    }
                }
                // Handle raw SpotifyException (http status: 404, ...)
                else if (excMessage.includes('http status: 404')) {
                    errorMessage = "This playlist is private or doesn't exist. Please use a public playlist.";
                }
                else if (excMessage.includes('http status: 429')) {
                    errorMessage = "Too many requests. Please try again in a moment.";
                }
                else if (excMessage.includes('http status:')) {
                    errorMessage = "Unable to load this playlist. Please check the link and try again.";
                }
                else if (!excMessage.includes('Traceback')) {
                    errorMessage = excMessage;
                }
            }

            showError(errorMessage);
            resetPhase1();
        },
        onError: function (progressBarElement, progressBarMessageElement, excMessage) {
            // Generic error handler for network/parsing errors
            showError('Failed to find remixes. Please try again.');
            resetPhase1();
        }
    });
}

function resetPhase1() {
    elements.submitBtn.disabled = false;
    elements.submitBtn.innerHTML = `
        <span class="btn-text">Find Remixes</span>
        <svg class="btn-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M5 12h14M12 5l7 7-7 7"/>
        </svg>
    `;
    elements.progressSection.style.display = 'none';
    elements.progressBar.style.width = '0%';
}

function resetCreateButton() {
    elements.createBtn.disabled = false;
    elements.createBtn.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12h14"/>
        </svg>
        <span>Create Playlist</span>
    `;
}

// ============ PHASE 2: Selection ============

function renderTrackSelection(result) {
    // Update header
    if (elements.playlistImage) {
        if (result.playlist_image) {
            elements.playlistImage.src = result.playlist_image;
            elements.playlistImage.style.display = 'block';
        } else {
            elements.playlistImage.style.display = 'none';
        }
    }
    elements.playlistName.textContent = result.playlist_name;
    elements.trackCount.textContent = `${result.total_tracks} tracks found`;

    // Update stats
    elements.statHigh.textContent = result.summary.high_confidence;
    elements.statMedium.textContent = result.summary.medium_confidence;
    elements.statNone.textContent = result.summary.no_match;

    // Store tracks and auto-select high confidence
    state.selectedTracks.clear();
    state.tracks = result.tracks || [];
    result.tracks.forEach((track) => {
        if (track.best_match && track.best_match.confidence_level === 'high') {
            state.selectedTracks.set(track.best_match.id, track.best_match);
        }
    });

    // Initialize search and progressive reveal
    state.searchQuery = '';
    state.filteredTracks = [...state.tracks];
    state.visibleTracksCount = state.tracksPerBatch;

    // Clear search input
    if (elements.trackSearch) {
        elements.trackSearch.value = '';
    }

    renderTrackList();
    updateShowMoreButton();
    updateSelectedCount();
}

function filterTracks() {
    const query = state.searchQuery.toLowerCase().trim();

    // Start with all tracks
    let filtered = [...state.tracks];

    // Apply confidence filter
    if (state.activeFilter) {
        filtered = filtered.filter(track => {
            if (state.activeFilter === 'high') {
                return track.best_match && track.best_match.confidence_level === 'high';
            } else if (state.activeFilter === 'medium') {
                return track.best_match && track.best_match.confidence_level === 'medium';
            } else if (state.activeFilter === 'none') {
                return !track.best_match;
            }
            return true;
        });
    }

    // Apply search filter
    if (query) {
        filtered = filtered.filter(track => {
            const originalName = (track.original.name || '').toLowerCase();
            const originalArtist = (track.original.artists.join(' ') || '').toLowerCase();
            const remixName = track.best_match ? (track.best_match.name || '').toLowerCase() : '';
            const remixArtist = track.best_match ? (track.best_match.artists.join(' ') || '').toLowerCase() : '';

            return originalName.includes(query) ||
                originalArtist.includes(query) ||
                remixName.includes(query) ||
                remixArtist.includes(query);
        });
    }

    state.filteredTracks = filtered;

    // Reset visible count when filter changes
    state.visibleTracksCount = state.tracksPerBatch;
    renderTrackList();
    updateShowMoreButton();
}

function renderTrackList() {
    const tracksToRender = state.filteredTracks.slice(0, state.visibleTracksCount);

    elements.trackList.innerHTML = '';

    if (state.filteredTracks.length === 0) {
        elements.trackList.innerHTML = `
            <div class="no-results">
                <p>No tracks found${state.searchQuery ? ` matching "${state.searchQuery}"` : ''}</p>
            </div>
        `;
        return;
    }

    const fragment = document.createDocumentFragment();
    tracksToRender.forEach((track) => {
        const realIndex = state.tracks.indexOf(track);
        const card = createTrackCard(track, realIndex);
        fragment.appendChild(card);
    });
    elements.trackList.appendChild(fragment);
}

function updateShowMoreButton() {
    if (!elements.showMoreWrapper || !elements.showMoreBtn) return;

    const remaining = state.filteredTracks.length - state.visibleTracksCount;

    if (remaining > 0) {
        elements.showMoreWrapper.style.display = 'flex';
        const countSpan = elements.showMoreBtn.querySelector('.show-more-count');
        if (countSpan) {
            const toShow = Math.min(remaining, state.tracksPerBatch);
            countSpan.textContent = `(${toShow} of ${remaining} remaining)`;
        }
    } else {
        elements.showMoreWrapper.style.display = 'none';
    }
}

function loadMoreTracks() {
    if (state.visibleTracksCount >= state.filteredTracks.length) return;

    const currentCount = state.visibleTracksCount;
    const nextCount = Math.min(currentCount + state.tracksPerBatch, state.filteredTracks.length);
    const newTracks = state.filteredTracks.slice(currentCount, nextCount);

    const fragment = document.createDocumentFragment();
    newTracks.forEach((track) => {
        const realIndex = state.tracks.indexOf(track);
        const card = createTrackCard(track, realIndex);
        fragment.appendChild(card);
    });
    elements.trackList.appendChild(fragment);

    state.visibleTracksCount = nextCount;
    updateShowMoreButton();
}

function attachManualAddHandlers(card, trackIndex) {
    const btn = card.querySelector('.btn-add-link');
    const panel = card.querySelector('.manual-add');
    const input = card.querySelector('.manual-add-input');
    const saveBtn = card.querySelector('.manual-add-save');
    const cancelBtn = card.querySelector('.manual-add-cancel');
    const status = card.querySelector('.manual-add-status');

    if (!btn || !panel || !input || !saveBtn || !cancelBtn || !status) return;

    const setLoading = (isLoading) => {
        saveBtn.disabled = isLoading;
        cancelBtn.disabled = isLoading;
        input.disabled = isLoading;
        btn.disabled = isLoading;
        if (isLoading) {
            saveBtn.dataset.originalText = saveBtn.textContent;
            saveBtn.textContent = 'Resolving…';
        } else {
            saveBtn.textContent = saveBtn.dataset.originalText || 'Add';
        }
    };

    const openPanel = () => {
        panel.style.display = 'flex';
        btn.setAttribute('aria-expanded', 'true');
        input.focus();
    };

    const closePanel = () => {
        panel.style.display = 'none';
        btn.setAttribute('aria-expanded', 'false');
        status.textContent = '';
        status.classList.remove('error');
        input.value = '';
    };

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (panel.style.display === 'flex') {
            closePanel();
        } else {
            openPanel();
        }
    });

    cancelBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closePanel();
    });

    const resolveAndInsert = async () => {
        const value = (input.value || '').trim();
        if (!value) return;

        setLoading(true);
        status.textContent = '';
        status.classList.remove('error');

        try {
            const wasPanelOpen = panel.style.display === 'flex';
            const wasMoreOptionsOpen = (() => {
                const optionsEl = card.querySelector('.more-options');
                return !!optionsEl && optionsEl.style.display !== 'none';
            })();

            const response = await fetch('/resolve-track/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': state.csrfToken
                },
                body: JSON.stringify({ url: value })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Could not resolve track');
            }

            const resolved = data.track;
            if (!resolved || !resolved.id) {
                throw new Error('Could not resolve track');
            }

            const track = state.tracks[trackIndex];
            if (!track) throw new Error('Track not found');

            const candidate = {
                id: resolved.id,
                name: resolved.name,
                artists: resolved.artists || [],
                album_art: resolved.album_art,
                preview_url: resolved.preview_url,
                spotify_url: resolved.spotify_url,
                confidence: 100,
                confidence_level: MANUAL_CONFIDENCE_LEVEL,
                source: 'manual'
            };

            const exists = (track.candidates || []).some(c => c && c.id === candidate.id);
            if (!exists) {
                // Keep ordering stable: append to the end so we don't "promote" it visually.
                track.candidates = [...(track.candidates || []), candidate];
            }

            const didPromoteToMain = !track.best_match;

            // If there was no match at all, the first manual add should become the main selection.
            // Any subsequent manual additions become options.
            if (didPromoteToMain) {
                track.best_match = candidate;
                if (Array.isArray(track.candidates)) {
                    track.candidates = track.candidates.filter(c => c && c.id !== candidate.id);
                    track.candidates = [candidate, ...track.candidates];
                } else {
                    track.candidates = [candidate];
                }

                // Auto-select it so it immediately participates in playlist creation.
                state.selectedTracks.set(candidate.id, candidate);

                status.textContent = 'Added to selection';
            } else {
                status.textContent = 'Added to options';
            }
            status.classList.remove('error');
            status.classList.add('success');

            // Keep the panel open for rapid consecutive adds.
            // Clear the input and gently fade the status after a moment.
            input.value = '';
            input.focus();
            window.setTimeout(() => {
                status.textContent = '';
                status.classList.remove('success');
            }, 1200);

            // Rebuild the card so the new option appears under "more options".
            const newCard = createTrackCard(track, trackIndex);
            card.replaceWith(newCard);

            // Preserve UX state (keep things open) to avoid a jarring "collapse" feeling.
            if (wasPanelOpen) {
                const newPanel = newCard.querySelector('.manual-add');
                const newBtn = newCard.querySelector('.btn-add-link');
                const newInput = newCard.querySelector('.manual-add-input');
                if (newPanel && newBtn && newInput) {
                    newPanel.style.display = 'flex';
                    newBtn.setAttribute('aria-expanded', 'true');
                    newInput.focus();
                }
            }

            if (wasMoreOptionsOpen) {
                const moreOptionsEl = newCard.querySelector('.more-options');
                const moreBtnEl = newCard.querySelector('.btn-more-options');
                if (moreOptionsEl && moreBtnEl) {
                    moreOptionsEl.style.display = 'block';
                    moreBtnEl.classList.add('expanded');
                }
            }

            updateSelectedCount();
        } catch (err) {
            status.textContent = err.message || 'Could not add link';
            status.classList.add('error');
        } finally {
            setLoading(false);
        }
    };

    saveBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        resolveAndInsert();
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            resolveAndInsert();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            closePanel();
        }
    });
}



function createTrackCard(track, index) {
    const card = document.createElement('div');
    card.className = 'track-card';
    card.dataset.index = index;

    const hasMatch = track.best_match !== null;
    const bestMatch = track.best_match;

    // Check if this track is currently selected (from state, not just default)
    const isSelected = hasMatch && state.selectedTracks.has(bestMatch.id);
    if (isSelected) {
        card.classList.add('selected');
    }

    const originalSpotifyUrl = (track.original && track.original.spotify_url) ? track.original.spotify_url : '';

    card.innerHTML = `
        <div class="track-original">
            <div class="track-art-wrapper">
                <img src="${track.original.album_art || '/static/img/placeholder.png'}" alt="" class="track-art">
                ${originalSpotifyUrl ? `
                    <a class="track-spotify-overlay" href="${originalSpotifyUrl}" target="_blank" rel="noopener noreferrer" title="Play on Spotify">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
                        </svg>
                    </a>
                ` : ''}
            </div>
            <div class="track-info">
                <span class="track-name">${escapeHtml(track.original.name)}</span>
                <span class="track-artists">${escapeHtml(track.original.artists.join(', '))}</span>
                <div class="track-actions">
                    <a class="track-action-link" 
                       href="https://open.spotify.com/search/${encodeURIComponent(track.original.artists[0] + ' ' + track.original.name)}" 
                       target="_blank" 
                       rel="noopener noreferrer"
                       title="Search for remixes on Spotify">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="11" cy="11" r="8"/>
                            <path d="m21 21-4.35-4.35"/>
                        </svg>
                        Search
                    </a>
                    <button type="button" class="track-action-btn btn-add-link" aria-expanded="false" title="Add a custom remix link">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 5v14M5 12h14"/>
                        </svg>
                        Add link
                    </button>
                </div>
                <div class="manual-add" style="display: none;">
                    <input class="manual-add-input" type="text" placeholder="Paste Spotify track link" inputmode="url" autocomplete="off">
                    <button type="button" class="manual-add-save">Add</button>
                    <button type="button" class="manual-add-cancel">Cancel</button>
                    <div class="manual-add-status" aria-live="polite"></div>
                </div>
            </div>
        </div>
        
        <div class="track-arrow">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
        </div>
        
        <div class="track-remix">
            ${hasMatch ? `
                <div class="remix-option ${isSelected ? 'selected' : ''}" data-track-id="${bestMatch.id}">
                    <input type="checkbox" 
                           class="remix-checkbox" 
                           id="remix-${index}" 
                           ${isSelected ? 'checked' : ''}
                           data-track-id="${bestMatch.id}"
                           data-track-data='${JSON.stringify(bestMatch).replace(/'/g, "&apos;")}'>
                    ${bestMatch.preview_url ? `
                        <button class="btn-preview" 
                                data-preview-url="${bestMatch.preview_url}" 
                                title="Preview track">
                            <svg class="icon-play" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <polygon points="5,3 19,12 5,21"/>
                            </svg>
                            <svg class="icon-pause" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="display:none;">
                                <rect x="6" y="4" width="4" height="16"/>
                                <rect x="14" y="4" width="4" height="16"/>
                            </svg>
                        </button>
                    ` : `
                        <a class="btn-preview btn-spotify-link" 
                           href="${bestMatch.spotify_url}" 
                           target="_blank" 
                           title="Listen on Spotify">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
                            </svg>
                        </a>
                    `}
                    <img src="${bestMatch.album_art || '/static/img/placeholder.png'}" alt="" class="track-art">
                    <div class="track-info">
                        <span class="track-name">${escapeHtml(bestMatch.name)}</span>
                        <span class="track-artists">${escapeHtml(bestMatch.artists.join(', '))}</span>
                    </div>
                    <span class="confidence-badge confidence-${bestMatch.confidence_level}">
                        ${getConfidenceEmoji(bestMatch.confidence_level)} ${bestMatch.confidence}%
                    </span>
                </div>
                ${track.candidates.length > 1 ? `
                    <button class="btn-more-options" data-index="${index}">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6,9 12,15 18,9"/>
                        </svg>
                        ${track.candidates.length - 1} more option${track.candidates.length > 2 ? 's' : ''}
                    </button>
                    <div class="more-options" id="more-options-${index}" style="display: none;">
                        ${track.candidates.slice(1).map((candidate, cidx) => `
                            <div class="remix-option" data-track-id="${candidate.id}">
                                <input type="checkbox" 
                                       class="remix-alt-checkbox" 
                                       id="remix-alt-${index}-${cidx + 1}"
                                       data-track-id="${candidate.id}"
                                       ${state.selectedTracks.has(candidate.id) ? 'checked' : ''}
                                       data-track-data='${JSON.stringify(candidate).replace(/'/g, "&apos;")}'>
                                ${candidate.preview_url ? `
                                    <button class="btn-preview btn-preview-small" 
                                            data-preview-url="${candidate.preview_url}" 
                                            title="Preview track">
                                        <svg class="icon-play" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                                            <polygon points="5,3 19,12 5,21"/>
                                        </svg>
                                        <svg class="icon-pause" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="display:none;">
                                            <rect x="6" y="4" width="4" height="16"/>
                                            <rect x="14" y="4" width="4" height="16"/>
                                        </svg>
                                    </button>
                                ` : `
                                    <a class="btn-preview btn-preview-small btn-spotify-link" 
                                       href="${candidate.spotify_url}" 
                                       target="_blank" 
                                       title="Listen on Spotify">
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
                                        </svg>
                                    </a>
                                `}
                                <img src="${candidate.album_art || '/static/img/placeholder.png'}" alt="" class="track-art-small">
                                <div class="track-info">
                                    <span class="track-name">${escapeHtml(candidate.name)}</span>
                                    <span class="track-artists">${escapeHtml(candidate.artists.join(', '))}</span>
                                </div>
                                <span class="confidence-badge confidence-${candidate.confidence_level}">
                                    ${candidate.confidence_level === MANUAL_CONFIDENCE_LEVEL ? 'Manual' : `${candidate.confidence}%`}
                                </span>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            ` : `
                <div class="no-match">
                    <span class="no-match-icon">--</span>
                    <span>No remix found</span>
                </div>
            `}
        </div>
    `;

    // Event listeners
    const checkbox = card.querySelector('.remix-checkbox');
    if (checkbox) {
        checkbox.addEventListener('change', (e) => handleTrackToggle(e, track, bestMatch));
    }

    const moreBtn = card.querySelector('.btn-more-options');
    if (moreBtn) {
        moreBtn.addEventListener('click', () => toggleMoreOptions(index));
    }

    // Radio buttons for alternate options
    const altCheckboxes = card.querySelectorAll('.remix-alt-checkbox');
    altCheckboxes.forEach(cb => {
        cb.addEventListener('change', (e) => handleAlternateToggle(e, track, index, card));
    });

    // Preview buttons
    const previewBtns = card.querySelectorAll('.btn-preview');
    previewBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            handlePreviewClick(btn);
        });
    });

    attachManualAddHandlers(card, index);

    return card;
}

function handleTrackToggle(e, track, matchData) {
    const card = e.target.closest('.track-card');
    const remixOption = e.target.closest('.remix-option');

    if (e.target.checked) {
        state.selectedTracks.set(matchData.id, matchData);
        card.classList.add('selected');
        remixOption.classList.add('selected');
    } else {
        state.selectedTracks.delete(matchData.id);
        const hasAnyAltSelected = !!card.querySelector('.remix-alt-checkbox:checked');
        if (!hasAnyAltSelected) {
            card.classList.remove('selected');
        }
        remixOption.classList.remove('selected');
    }

    updateSelectedCount();
}

function handleAlternateToggle(e, track, index, card) {
    const trackData = JSON.parse(e.target.dataset.trackData.replace(/&apos;/g, "'"));
    const remixOption = e.target.closest('.remix-option');

    if (e.target.checked) {
        state.selectedTracks.set(trackData.id, trackData);
        remixOption.classList.add('selected');
        card.classList.add('selected');
    } else {
        state.selectedTracks.delete(trackData.id);
        remixOption.classList.remove('selected');

        const hasAnySelectedInCard = !!card.querySelector(
            '.remix-checkbox:checked, .remix-alt-checkbox:checked'
        );
        if (!hasAnySelectedInCard) {
            card.classList.remove('selected');
        }
    }

    updateSelectedCount();
}

function toggleMoreOptions(index) {
    const options = document.getElementById(`more-options-${index}`);
    const btn = document.querySelector(`.btn-more-options[data-index="${index}"]`);

    if (options.style.display === 'none') {
        options.style.display = 'block';
        btn.classList.add('expanded');
    } else {
        options.style.display = 'none';
        btn.classList.remove('expanded');
    }
}

function selectAllHighConfidence() {
    // Select all high confidence across ALL tracks
    state.tracks.forEach((track) => {
        if (track.best_match && track.best_match.confidence_level === 'high') {
            state.selectedTracks.set(track.best_match.id, track.best_match);
        }
    });
    updateVisibleTracksSelection();
    updateSelectedCount();
}

function selectAllTracks() {
    // Select all tracks with matches across ALL tracks
    state.tracks.forEach((track) => {
        if (track.best_match) {
            state.selectedTracks.set(track.best_match.id, track.best_match);
        }
    });
    updateVisibleTracksSelection();
    updateSelectedCount();
}

function deselectAllTracks() {
    state.selectedTracks.clear();
    updateVisibleTracksSelection();
    updateSelectedCount();
}

function updateVisibleTracksSelection() {
    // Re-render the track list to update selections
    renderTrackList();
}

function updateSelectedCount() {
    const count = state.selectedTracks.size;
    elements.selectedCount.textContent = count;
    elements.createBtn.disabled = count === 0;
    elements.createBtn.querySelector('span').textContent = count === 0
        ? 'Select tracks'
        : `Create Playlist (${count})`;

    // Update sticky bar
    if (elements.stickySelectedCount) {
        elements.stickySelectedCount.textContent = count;
    }

    // Show/hide sticky bar based on selection
    if (elements.stickyBar) {
        if (count > 0) {
            elements.stickyBar.classList.add('visible');
        } else {
            elements.stickyBar.classList.remove('visible');
        }
    }
}

// ============ PHASE 3: Create Playlist ============

async function handleCreatePlaylist() {
    const selectedIds = Array.from(state.selectedTracks.keys());

    if (selectedIds.length === 0) return;

    elements.createBtn.disabled = true;
    elements.createBtn.innerHTML = `
        <svg class="spinning" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
        </svg>
        <span>Creating...</span>
    `;

    try {
        const response = await fetch('/create-playlist/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': state.csrfToken
            },
            body: JSON.stringify({
                playlist_name: state.playlistName,
                selected_tracks: selectedIds,
                original_url: state.originalUrl
            })
        });

        const data = await response.json();
        if (data.error) throw new Error(data.error);

        // Poll for completion
        pollCreateResult(data.task_id);

    } catch (error) {
        showError(error.message);
        elements.createBtn.disabled = false;
        elements.createBtn.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 5v14M5 12h14"/>
            </svg>
            <span>Create Playlist</span>
        `;
    }
}

async function pollCreateResult(taskId) {
    const checkResult = async () => {
        try {
            const response = await fetch(`/create-playlist/${taskId}/`);
            const data = await response.json();

            if (data.status === 'complete') {
                showPhase3Success(data.result);
            } else if (data.status === 'error') {
                throw new Error(data.error);
            } else {
                // Still pending, check again
                setTimeout(checkResult, 1000);
            }
        } catch (error) {
            showError(error.message);
            resetCreateButton();
        }
    };

    checkResult();
}

function showPhase3Success(result) {
    elements.successMessage.textContent = `"${result.name}" with ${result.track_count} tracks is ready!`;
    elements.spotifyLink.href = result.url;
    goToPhase3();
}

// ============ Audio Preview ============

function handlePreviewClick(btn) {
    const previewUrl = btn.dataset.previewUrl;

    // Don't do anything if no preview URL
    if (!previewUrl) {
        return;
    }

    // If clicking the same button that's playing, stop it
    if (state.currentlyPlayingBtn === btn) {
        stopPreview();
        return;
    }

    // Stop any currently playing preview
    stopPreview();

    // Create audio player if it doesn't exist
    if (!state.audioPlayer) {
        state.audioPlayer = new Audio();
        state.audioPlayer.volume = 0.5;

        // When audio ends, reset the button
        state.audioPlayer.addEventListener('ended', () => {
            stopPreview();
        });

        // Handle errors
        state.audioPlayer.addEventListener('error', () => {
            stopPreview();
        });
    }

    // Start playing
    state.audioPlayer.src = previewUrl;
    state.audioPlayer.play();

    // Update button state
    state.currentlyPlayingBtn = btn;
    btn.classList.add('playing');
    btn.querySelector('.icon-play').style.display = 'none';
    btn.querySelector('.icon-pause').style.display = 'block';

    // Auto-stop after 15 seconds (Spotify previews are ~30s)
    state.previewTimeout = setTimeout(() => {
        stopPreview();
    }, 15000);
}

function stopPreview() {
    if (state.audioPlayer) {
        state.audioPlayer.pause();
        state.audioPlayer.currentTime = 0;
    }

    if (state.previewTimeout) {
        clearTimeout(state.previewTimeout);
        state.previewTimeout = null;
    }

    if (state.currentlyPlayingBtn) {
        state.currentlyPlayingBtn.classList.remove('playing');
        state.currentlyPlayingBtn.querySelector('.icon-play').style.display = 'block';
        state.currentlyPlayingBtn.querySelector('.icon-pause').style.display = 'none';
        state.currentlyPlayingBtn = null;
    }
}

// ============ Navigation ============

function goToPhase1() {
    stopPreview(); // Stop any playing audio
    if (elements.phaseInput) elements.phaseInput.style.display = 'flex';
    if (elements.phaseSelection) elements.phaseSelection.style.display = 'none';
    if (elements.phaseSuccess) elements.phaseSuccess.style.display = 'none';
    resetPhase1();
    resetCreateButton();
    if (elements.urlInput) elements.urlInput.value = '';
    state.tracks = [];
    state.selectedTracks.clear();
    state.activeFilter = null;

    // Hide sticky bar
    if (elements.stickyBar) {
        elements.stickyBar.classList.remove('visible');
    }

    // Reset stat card active states
    document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('active'));
}

function goToPhase2() {
    if (elements.phaseInput) elements.phaseInput.style.display = 'none';
    if (elements.phaseSelection) elements.phaseSelection.style.display = 'block';
    if (elements.phaseSuccess) elements.phaseSuccess.style.display = 'none';

    // Scroll to top
    window.scrollTo(0, 0);
}

function goToPhase3() {
    if (elements.phaseInput) elements.phaseInput.style.display = 'none';
    if (elements.phaseSelection) elements.phaseSelection.style.display = 'none';
    if (elements.phaseSuccess) elements.phaseSuccess.style.display = 'flex';

    // Hide sticky bar
    if (elements.stickyBar) {
        elements.stickyBar.classList.remove('visible');
    }
}

// ============ Utilities ============

function getConfidenceEmoji(level) {
    switch (level) {
        case 'high': return '';
        case 'medium': return '';
        case 'low': return '';
        default: return '';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError(message) {
    Toastify({
        text: message,
        duration: 5000,
        gravity: "top",
        position: "center",
        stopOnFocus: true,
        style: {
            background: "#dc2626",
            borderRadius: "12px",
            padding: "16px 24px",
            fontSize: "15px",
            fontFamily: "'Nunito', sans-serif"
        }
    }).showToast();
}

function showSuccess(message) {
    Toastify({
        text: message,
        duration: 3000,
        gravity: "top",
        position: "center",
        stopOnFocus: true,
        style: {
            background: "#1DB954",
            borderRadius: "12px",
            padding: "16px 24px",
            fontSize: "15px",
            fontFamily: "'Nunito', sans-serif"
        }
    }).showToast();
}
