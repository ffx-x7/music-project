class PremiumMusicPlayer {
    constructor() {
        // ... existing code ...
        this.searchTimeout = null;
        this.searchDebounce = 500; // 500ms debounce
        this.lastSearchQuery = '';
        this.searchRetryCount = 0;
        this.maxSearchRetries = 3;
    }
    
    // Enhanced search method with retries
    async search(query = null) {
        const searchInput = document.getElementById('search-input');
        const queryText = query || searchInput.value.trim();
        
        if (!queryText || queryText.length < 1) {
            this.showNotification('Please enter a search term', 'warning');
            return;
        }
        
        // Don't search the same query repeatedly
        if (queryText === this.lastSearchQuery && this.searchRetryCount > 0) {
            return;
        }
        
        this.lastSearchQuery = queryText;
        this.showLoading(true);
        this.searchRetryCount = 0;
        
        // Clear previous results
        document.getElementById('search-results').innerHTML = '';
        
        try {
            await this.performSearch(queryText);
        } catch (error) {
            console.error('Search error:', error);
            await this.handleSearchError(queryText, error);
        } finally {
            this.showLoading(false);
        }
    }
    
    async performSearch(queryText, retry = 0) {
        try {
            // Show searching indicator
            const searchBtn = document.getElementById('search-btn');
            const originalHtml = searchBtn.innerHTML;
            searchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            searchBtn.disabled = true;
            
            // Encode query properly
            const encodedQuery = encodeURIComponent(queryText);
            
            // Add cache busting
            const timestamp = Date.now();
            const url = `/api/search?q=${encodedQuery}&limit=15&_=${timestamp}`;
            
            const response = await fetch(url, {
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Restore button
            searchBtn.innerHTML = originalHtml;
            searchBtn.disabled = false;
            
            if (data.success) {
                this.searchRetryCount = 0;
                
                if (data.results && data.results.length > 0) {
                    this.displaySearchResults(data.results);
                    
                    // Show success notification
                    if (data.results.length === 1) {
                        this.showNotification(`Found 1 result for "${queryText}"`, 'success');
                    } else {
                        this.showNotification(`Found ${data.results.length} results for "${queryText}"`, 'success');
                    }
                } else {
                    // No results found
                    this.displayNoResults(queryText);
                }
            } else {
                // API returned error
                throw new Error(data.message || 'Search failed');
            }
            
        } catch (error) {
            // Restore button on error
            const searchBtn = document.getElementById('search-btn');
            searchBtn.innerHTML = '<i class="fas fa-search"></i>';
            searchBtn.disabled = false;
            
            throw error;
        }
    }
    
    async handleSearchError(queryText, error) {
        this.searchRetryCount++;
        
        if (this.searchRetryCount <= this.maxSearchRetries) {
            // Show retry notification
            this.showNotification(`Search failed, retrying... (${this.searchRetryCount}/${this.maxSearchRetries})`, 'warning');
            
            // Wait before retrying with exponential backoff
            const delay = Math.min(1000 * Math.pow(2, this.searchRetryCount - 1), 5000);
            
            await new Promise(resolve => setTimeout(resolve, delay));
            
            // Try alternative search methods
            const alternativeQueries = this.generateAlternativeQueries(queryText);
            
            for (const altQuery of alternativeQueries) {
                try {
                    await this.performSearch(altQuery, this.searchRetryCount);
                    return; // Success
                } catch (e) {
                    continue; // Try next alternative
                }
            }
        }
        
        // All retries failed
        this.displaySearchError(queryText, error);
    }
    
    generateAlternativeQueries(query) {
        const alternatives = [];
        
        // Original query
        alternatives.push(query);
        
        // Add common suffixes
        const suffixes = ['song', 'audio', 'lyrics', 'music video', 'official audio', 'official video'];
        
        for (const suffix of suffixes) {
            if (!query.toLowerCase().includes(suffix.toLowerCase())) {
                alternatives.push(`${query} ${suffix}`);
            }
        }
        
        // Try without common prefixes
        const prefixes = ['song', 'audio', 'lyrics', 'music', 'video'];
        let cleanedQuery = query;
        
        for (const prefix of prefixes) {
            if (query.toLowerCase().startsWith(prefix.toLowerCase() + ' ')) {
                cleanedQuery = query.substring(prefix.length + 1).trim();
                break;
            }
        }
        
        if (cleanedQuery !== query) {
            alternatives.push(cleanedQuery);
        }
        
        // Remove featured artists in parentheses
        const withoutFeatured = query.replace(/\(feat\..*?\)/gi, '').replace(/\(with.*?\)/gi, '').trim();
        if (withoutFeatured !== query) {
            alternatives.push(withoutFeatured);
        }
        
        return [...new Set(alternatives)]; // Remove duplicates
    }
    
    displaySearchResults(results) {
        const container = document.getElementById('search-results');
        container.innerHTML = '';
        
        if (!results || results.length === 0) {
            this.displayNoResults();
            return;
        }
        
        results.forEach((song, index) => {
            const col = document.createElement('div');
            col.className = 'col-md-4 col-lg-3 mb-4 fade-in';
            col.style.animationDelay = `${index * 0.1}s`;
            
            // Format duration
            let durationText = song.duration;
            if (song.duration_seconds) {
                const mins = Math.floor(song.duration_seconds / 60);
                const secs = song.duration_seconds % 60;
                durationText = `${mins}:${secs.toString().padStart(2, '0')}`;
            }
            
            // Format views
            let viewsText = song.views || 'N/A';
            if (typeof song.views === 'number') {
                if (song.views > 1000000) {
                    viewsText = `${(song.views / 1000000).toFixed(1)}M`;
                } else if (song.views > 1000) {
                    viewsText = `${(song.views / 1000).toFixed(1)}K`;
                }
            }
            
            col.innerHTML = `
                <div class="song-card" onclick="player.playSong('${song.id}', '${this.escapeHtml(song.title)}', '${song.thumbnail}')">
                    <div class="card-image">
                        <img src="${song.thumbnail}" alt="${this.escapeHtml(song.title)}" loading="lazy">
                        <div class="card-overlay">
                            <button class="play-overlay-btn">
                                <i class="fas fa-play"></i>
                            </button>
                        </div>
                        <div class="card-badge">
                            <span>${durationText}</span>
                        </div>
                    </div>
                    <div class="card-content">
                        <h6 title="${this.escapeHtml(song.title)}">${this.truncateText(song.title, 50)}</h6>
                        <p class="channel">${this.truncateText(song.channel, 30)}</p>
                        <div class="card-meta">
                            <span><i class="fas fa-eye"></i> ${viewsText}</span>
                            <div class="card-actions">
                                <button class="icon-btn small" onclick="event.stopPropagation(); player.addToQueue(${JSON.stringify(song)})">
                                    <i class="fas fa-plus"></i>
                                </button>
                                <button class="icon-btn small" onclick="event.stopPropagation(); player.downloadSong('${song.id}')">
                                    <i class="fas fa-download"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            container.appendChild(col);
        });
    }
    
    displayNoResults(query = '') {
        const container = document.getElementById('search-results');
        container.innerHTML = `
            <div class="no-results">
                <i class="fas fa-search"></i>
                <h4>No results found</h4>
                <p>We couldn't find any songs matching "${query}"</p>
                <div class="suggestions">
                    <p><strong>Try:</strong></p>
                    <ul>
                        <li>Check your spelling</li>
                        <li>Try different keywords</li>
                        <li>Be less specific</li>
                        <li>Search for the artist name</li>
                    </ul>
                </div>
                <button class="btn-primary" onclick="player.searchTrending()">
                    <i class="fas fa-fire"></i> Show Trending Songs
                </button>
            </div>
        `;
        
        this.showNotification('No results found. Try a different search term.', 'warning');
    }
    
    displaySearchError(query, error) {
        const container = document.getElementById('search-results');
        container.innerHTML = `
            <div class="search-error">
                <i class="fas fa-exclamation-triangle"></i>
                <h4>Search Failed</h4>
                <p>Error: ${error.message || 'Unknown error'}</p>
                <div class="error-actions">
                    <button class="btn-secondary" onclick="player.retrySearch('${this.escapeHtml(query)}')">
                        <i class="fas fa-redo"></i> Retry Search
                    </button>
                    <button class="btn-secondary" onclick="player.searchTrending()">
                        <i class="fas fa-fire"></i> Show Trending
                    </button>
                    <button class="btn-secondary" onclick="player.clearSearch()">
                        <i class="fas fa-times"></i> Clear
                    </button>
                </div>
            </div>
        `;
        
        this.showNotification('Search failed. Please try again.', 'error');
    }
    
    async searchTrending() {
        const trendingQueries = [
            'top songs 2024',
            'latest music',
            'popular songs',
            'trending music',
            'billboard top 100',
            'viral songs',
            'new releases'
        ];
        
        const randomQuery = trendingQueries[Math.floor(Math.random() * trendingQueries.length)];
        document.getElementById('search-input').value = randomQuery;
        await this.search(randomQuery);
    }
    
    async retrySearch(query) {
        document.getElementById('search-input').value = query;
        await this.search(query);
    }
    
    clearSearch() {
        document.getElementById('search-input').value = '';
        document.getElementById('search-results').innerHTML = '';
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
    
    // Setup enhanced search event listeners
    setupSearchListeners() {
        const searchInput = document.getElementById('search-input');
        const searchBtn = document.getElementById('search-btn');
        
        // Real-time search with debounce
        searchInput.addEventListener('input', () => {
            clearTimeout(this.searchTimeout);
            
            const query = searchInput.value.trim();
            if (query.length >= 2) { // Start searching after 2 characters
                this.searchTimeout = setTimeout(() => {
                    this.search();
                }, this.searchDebounce);
            } else if (query.length === 0) {
                // Clear results when input is empty
                document.getElementById('search-results').innerHTML = '';
            }
        });
        
        // Search on button click
        searchBtn.addEventListener('click', () => this.search());
        
        // Voice search (if supported)
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const voiceBtn = document.getElementById('voice-search');
            if (voiceBtn) {
                voiceBtn.style.display = 'block';
                voiceBtn.addEventListener('click', () => this.startVoiceSearch());
            }
        }
        
        // Keyboard shortcut: Ctrl/Cmd + K
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
        });
    }
    
    startVoiceSearch() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            this.showNotification('Voice search not supported in your browser', 'warning');
            return;
        }
        
        const recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.continuous = false;
        recognition.interimResults = false;
        
        recognition.onstart = () => {
            this.showNotification('Listening... Speak now', 'info');
            document.getElementById('voice-search').innerHTML = '<i class="fas fa-microphone-slash"></i>';
        };
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            document.getElementById('search-input').value = transcript;
            this.search(transcript);
        };
        
        recognition.onerror = (event) => {
            this.showNotification('Voice recognition error: ' + event.error, 'error');
            document.getElementById('voice-search').innerHTML = '<i class="fas fa-microphone"></i>';
        };
        
        recognition.onend = () => {
            document.getElementById('voice-search').innerHTML = '<i class="fas fa-microphone"></i>';
        };
        
        recognition.start();
    }
}