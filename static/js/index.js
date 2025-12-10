/**
 * Remixify - Two-Phase Remix Selection
 * Phase 1: Preview remixes and let user select
 * Phase 2: Create playlist with selected tracks
 */

// State management
const state = {
    playlistName: '',
    playlistImage: '',
    tracks: [],
    selectedTracks: new Map(), // trackId -> track data
    csrfToken: '',
    currentTaskId: null,
    // Pagination
    currentPage: 1,
    tracksPerPage: 10
};

// DOM Elements
const elements = {
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
    
    // Phase 2
    backBtn: document.getElementById('back-btn'),
    playlistImage: document.getElementById('playlist-image'),
    playlistName: document.getElementById('playlist-name'),
    trackCount: document.getElementById('track-count'),
    summaryStats: document.getElementById('summary-stats'),
    statHigh: document.getElementById('stat-high'),
    statMedium: document.getElementById('stat-medium'),
    statLow: document.getElementById('stat-low'),
    statNone: document.getElementById('stat-none'),
    selectAllHigh: document.getElementById('select-all-high'),
    selectAll: document.getElementById('select-all'),
    deselectAll: document.getElementById('deselect-all'),
    selectedCount: document.getElementById('selected-count'),
    paginationContainer: document.getElementById('pagination'),
    paginationBottom: document.getElementById('pagination-bottom'),
    trackList: document.getElementById('track-list'),
    createBtn: document.getElementById('create-btn'),
    
    // Phase 3
    successMessage: document.getElementById('success-message'),
    spotifyLink: document.getElementById('spotify-link'),
    newPlaylistBtn: document.getElementById('new-playlist-btn')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    state.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    setupEventListeners();
});
function setupEventListeners() {
    // Phase 1: Form submission
    elements.form.addEventListener('submit', handleFormSubmit);
    
    // Phase 2: Selection controls
    elements.backBtn.addEventListener('click', goToPhase1);
    elements.selectAllHigh.addEventListener('click', selectAllHighConfidence);
    elements.selectAll.addEventListener('click', selectAllTracks);
    elements.deselectAll.addEventListener('click', deselectAllTracks);
    elements.createBtn.addEventListener('click', handleCreatePlaylist);
    
    // Phase 3: New playlist
    elements.newPlaylistBtn.addEventListener('click', goToPhase1);
}

// ============ PHASE 1: Preview ============

async function handleFormSubmit(e) {
    e.preventDefault();
    
    const url = elements.urlInput.value.trim();
    if (!url) return;
    
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
        onProgress: function(progressBarElement, progressBarMessageElement, progress) {
            elements.progressBar.style.width = `${progress.percent}%`;
            elements.progressMessage.textContent = `Finding remixes... ${progress.current}/${progress.total} tracks`;
        },
        onSuccess: async function() {
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
        onError: function(error) {
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

// ============ PHASE 2: Selection ============

function renderTrackSelection(result) {
    // Update header
    if (result.playlist_image) {
        elements.playlistImage.src = result.playlist_image;
        elements.playlistImage.style.display = 'block';
    } else {
        elements.playlistImage.style.display = 'none';
    }
    elements.playlistName.textContent = result.playlist_name;
    elements.trackCount.textContent = `${result.total_tracks} tracks found`;
    
    // Update stats
    elements.statHigh.textContent = result.summary.high_confidence;
    elements.statMedium.textContent = result.summary.medium_confidence;
    elements.statLow.textContent = result.summary.low_confidence;
    elements.statNone.textContent = result.summary.no_match;
    
    // Store tracks and auto-select high confidence
    state.selectedTracks.clear();
    result.tracks.forEach((track) => {
        if (track.best_match && track.best_match.confidence_level === 'high') {
            state.selectedTracks.set(track.best_match.id, track.best_match);
        }
    });
    
    // Reset pagination and render
    state.currentPage = 1;
    renderCurrentPage();
    renderPagination();
    updateSelectedCount();
}

function renderCurrentPage() {
    const startIndex = (state.currentPage - 1) * state.tracksPerPage;
    const endIndex = startIndex + state.tracksPerPage;
    const tracksToRender = state.tracks.slice(startIndex, endIndex);
    
    elements.trackList.innerHTML = '';
    
    tracksToRender.forEach((track, localIndex) => {
        const globalIndex = startIndex + localIndex;
        const card = createTrackCard(track, globalIndex);
        elements.trackList.appendChild(card);
    });
    
    // Scroll to top of track list
    elements.trackList.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderPagination() {
    const totalPages = Math.ceil(state.tracks.length / state.tracksPerPage);
    
    if (totalPages <= 1) {
        elements.paginationContainer.style.display = 'none';
        elements.paginationBottom.style.display = 'none';
        return;
    }
    
    elements.paginationContainer.style.display = 'flex';
    elements.paginationBottom.style.display = 'flex';
    
    let html = '';
    
    // Previous button
    html += `
        <button class="pagination-btn nav-btn" ${state.currentPage === 1 ? 'disabled' : ''} data-page="${state.currentPage - 1}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M15 18l-6-6 6-6"/>
            </svg>
            Prev
        </button>
    `;
    
    // Page numbers
    const maxVisiblePages = 5;
    let startPage = Math.max(1, state.currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    // Adjust start if we're near the end
    if (endPage - startPage < maxVisiblePages - 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    if (startPage > 1) {
        html += `<button class="pagination-btn" data-page="1">1</button>`;
        if (startPage > 2) {
            html += `<span class="pagination-info">...</span>`;
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `
            <button class="pagination-btn ${i === state.currentPage ? 'active' : ''}" data-page="${i}">
                ${i}
            </button>
        `;
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += `<span class="pagination-info">...</span>`;
        }
        html += `<button class="pagination-btn" data-page="${totalPages}">${totalPages}</button>`;
    }
    
    // Next button
    html += `
        <button class="pagination-btn nav-btn" ${state.currentPage === totalPages ? 'disabled' : ''} data-page="${state.currentPage + 1}">
            Next
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 18l6-6-6-6"/>
            </svg>
        </button>
    `;
    
    // Apply to both pagination containers
    elements.paginationContainer.innerHTML = html;
    elements.paginationBottom.innerHTML = html;
    
    // Add event listeners to both
    const addPaginationListeners = (container) => {
        container.querySelectorAll('.pagination-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const page = parseInt(btn.dataset.page);
                if (page && page !== state.currentPage && page >= 1 && page <= totalPages) {
                    state.currentPage = page;
                    renderCurrentPage();
                    renderPagination();
                }
            });
        });
    };
    
    addPaginationListeners(elements.paginationContainer);
    addPaginationListeners(elements.paginationBottom);
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
    
    card.innerHTML = `
        <div class="track-original">
            <img src="${track.original.album_art || '/static/img/placeholder.png'}" alt="" class="track-art">
            <div class="track-info">
                <span class="track-name">${escapeHtml(track.original.name)}</span>
                <span class="track-artists">${escapeHtml(track.original.artists.join(', '))}</span>
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
                                <input type="radio" 
                                       name="track-${index}" 
                                       class="remix-radio" 
                                       id="remix-${index}-${cidx + 1}"
                                       data-track-id="${candidate.id}"
                                       data-track-data='${JSON.stringify(candidate).replace(/'/g, "&apos;")}'>
                                <img src="${candidate.album_art || '/static/img/placeholder.png'}" alt="" class="track-art-small">
                                <div class="track-info">
                                    <span class="track-name">${escapeHtml(candidate.name)}</span>
                                    <span class="track-artists">${escapeHtml(candidate.artists.join(', '))}</span>
                                </div>
                                <span class="confidence-badge confidence-${candidate.confidence_level}">
                                    ${candidate.confidence}%
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
    const radios = card.querySelectorAll('.remix-radio');
    radios.forEach(radio => {
        radio.addEventListener('change', (e) => handleAlternateSelection(e, track, index, card));
    });
    
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
        card.classList.remove('selected');
        remixOption.classList.remove('selected');
    }
    
    updateSelectedCount();
}

function handleAlternateSelection(e, track, index, card) {
    const trackData = JSON.parse(e.target.dataset.trackData.replace(/&apos;/g, "'"));
    const mainCheckbox = card.querySelector('.remix-checkbox');
    const mainOption = card.querySelector('.remix-option');
    
    // Remove old selection
    if (mainCheckbox.checked) {
        const oldId = mainCheckbox.dataset.trackId;
        state.selectedTracks.delete(oldId);
    }
    
    // Update main checkbox with new selection
    mainCheckbox.dataset.trackId = trackData.id;
    mainCheckbox.dataset.trackData = JSON.stringify(trackData);
    mainCheckbox.checked = true;
    
    // Update visual
    mainOption.querySelector('.track-art').src = trackData.album_art;
    mainOption.querySelector('.track-name').textContent = trackData.name;
    mainOption.querySelector('.track-artists').textContent = trackData.artists.join(', ');
    mainOption.querySelector('.confidence-badge').className = `confidence-badge confidence-${trackData.confidence_level}`;
    mainOption.querySelector('.confidence-badge').innerHTML = `${getConfidenceEmoji(trackData.confidence_level)} ${trackData.confidence}%`;
    
    // Add to selected
    state.selectedTracks.set(trackData.id, trackData);
    card.classList.add('selected');
    mainOption.classList.add('selected');
    
    // Hide options
    toggleMoreOptions(index);
    
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
    // Select all high confidence across ALL tracks, not just current page
    state.tracks.forEach((track) => {
        if (track.best_match && track.best_match.confidence_level === 'high') {
            state.selectedTracks.set(track.best_match.id, track.best_match);
        }
    });
    renderCurrentPage(); // Re-render to update checkboxes
    updateSelectedCount();
}

function selectAllTracks() {
    // Select all tracks with matches across ALL tracks
    state.tracks.forEach((track) => {
        if (track.best_match) {
            state.selectedTracks.set(track.best_match.id, track.best_match);
        }
    });
    renderCurrentPage();
    updateSelectedCount();
}

function deselectAllTracks() {
    state.selectedTracks.clear();
    renderCurrentPage();
    updateSelectedCount();
}

function updateSelectedCount() {
    const count = state.selectedTracks.size;
    elements.selectedCount.textContent = count;
    elements.createBtn.disabled = count === 0;
    elements.createBtn.querySelector('span').textContent = count === 0 
        ? 'Select tracks to continue' 
        : `Create Playlist (${count} tracks)`;
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
                selected_tracks: selectedIds
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
                showSuccess(data.result);
            } else if (data.status === 'error') {
                throw new Error(data.error);
            } else {
                // Still pending, check again
                setTimeout(checkResult, 1000);
            }
        } catch (error) {
            showError(error.message);
        }
    };
    
    checkResult();
}

function showSuccess(result) {
    elements.successMessage.textContent = `"${result.name}" with ${result.track_count} tracks is ready!`;
    elements.spotifyLink.href = result.url;
    goToPhase3();
}

// ============ Navigation ============

function goToPhase1() {
    elements.phaseInput.style.display = 'flex';
    elements.phaseSelection.style.display = 'none';
    elements.phaseSuccess.style.display = 'none';
    resetPhase1();
    elements.urlInput.value = '';
    state.tracks = [];
    state.selectedTracks.clear();
}

function goToPhase2() {
    elements.phaseInput.style.display = 'none';
    elements.phaseSelection.style.display = 'block';
    elements.phaseSuccess.style.display = 'none';
    
    // Scroll to top
    window.scrollTo(0, 0);
}

function goToPhase3() {
    elements.phaseInput.style.display = 'none';
    elements.phaseSelection.style.display = 'none';
    elements.phaseSuccess.style.display = 'flex';
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
    // Simple alert for now - could be replaced with toast notification
    alert(`Error: ${message}`);
}