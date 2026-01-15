class LyricsManager {
    constructor() {
        this.lyrics = [];
        this.syncedLyrics = [];
        this.currentLine = -1;
        this.lyricsContainer = null;
        this.isSynced = false;
        this.lyricsOffset = 0; // Offset in seconds for sync adjustment
        this.lyricsProviders = [
            'https://api.lyrics.ovh/v1/{artist}/{title}',
            'https://some-random-api.com/lyrics?title={title}',
            'https://lrclib.net/api/search?q={title}+{artist}'
        ];
    }
    
    async fetchLyrics(title, artist = '') {
        if (!title) {
            this.setLyricsText('No song selected');
            return false;
        }
        
        this.setLyricsText('Loading lyrics...');
        
        try {
            // Try multiple providers
            for (const provider of this.lyricsProviders) {
                const url = this.buildLyricsUrl(provider, title, artist);
                
                try {
                    const lyrics = await this.fetchFromProvider(url, provider);
                    if (lyrics) {
                        this.processLyrics(lyrics);
                        return true;
                    }
                } catch (error) {
                    console.warn(`Failed to fetch from ${provider}:`, error);
                    continue;
                }
            }
            
            // If all providers fail, try to search
            this.setLyricsText('Lyrics not found. Searching alternatives...');
            const fallbackLyrics = await this.searchLyrics(title, artist);
            
            if (fallbackLyrics) {
                this.processLyrics(fallbackLyrics);
                return true;
            }
            
            this.setLyricsText('Lyrics not available for this song');
            return false;
            
        } catch (error) {
            console.error('Lyrics fetch error:', error);
            this.setLyricsText('Error loading lyrics');
            return false;
        }
    }
    
    buildLyricsUrl(provider, title, artist) {
        const encodedTitle = encodeURIComponent(title);
        const encodedArtist = encodeURIComponent(artist);
        
        return provider
            .replace('{title}', encodedTitle)
            .replace('{artist}', encodedArtist);
    }
    
    async fetchFromProvider(url, providerType) {
        const response = await fetch(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Parse based on provider
        if (providerType.includes('lyrics.ovh')) {
            return data.lyrics || null;
        } else if (providerType.includes('some-random-api')) {
            return data.lyrics || null;
        } else if (providerType.includes('lrclib.net')) {
            if (data.data && data.data.length > 0) {
                // LRC format lyrics
                return this.parseLRCLyrics(data.data[0].syncedLyrics);
            }
        }
        
        return null;
    }
    
    async searchLyrics(title, artist) {
        // Use a search approach
        const searchQuery = `${title} ${artist} lyrics`;
        const searchUrl = `https://www.googleapis.com/customsearch/v1?q=${encodeURIComponent(searchQuery)}&key=YOUR_API_KEY&cx=YOUR_CX`;
        
        // Note: This requires Google Custom Search API
        // For now, return null
        return null;
    }
    
    parseLRCLyrics(lrcText) {
        if (!lrcText) return 'Lyrics not available';
        
        // Parse LRC format with timestamps
        this.syncedLyrics = [];
        const lines = lrcText.split('\n');
        
        for (const line of lines) {
            const match = line.match(/\[(\d+):(\d+\.\d+)\](.*)/);
            if (match) {
                const minutes = parseInt(match[1]);
                const seconds = parseFloat(match[2]);
                const text = match[3].trim();
                
                if (text) {
                    this.syncedLyrics.push({
                        time: minutes * 60 + seconds,
                        text: text
                    });
                }
            }
        }
        
        // Sort by time
        this.syncedLyrics.sort((a, b) => a.time - b.time);
        this.isSynced = this.syncedLyrics.length > 0;
        
        // Return plain text if no sync
        if (!this.isSynced) {
            return lrcText.replace(/\[\d+:\d+\.\d+\]/g, '').trim();
        }
        
        return this.syncedLyrics.map(l => l.text).join('\n');
    }
    
    processLyrics(lyricsText) {
        if (this.isSynced) {
            // Already processed in parseLRCLyrics
            this.displaySyncedLyrics();
        } else {
            // Plain text lyrics
            this.lyrics = lyricsText.split('\n').filter(line => line.trim());
            this.displayPlainLyrics();
        }
    }
    
    displayPlainLyrics() {
        if (!this.lyricsContainer) {
            this.lyricsContainer = document.getElementById('lyrics-content');
        }
        
        if (this.lyricsContainer) {
            this.lyricsContainer.innerHTML = this.lyrics
                .map(line => `<div class="lyrics-line">${this.escapeHtml(line)}</div>`)
                .join('');
        }
    }
    
    displaySyncedLyrics() {
        if (!this.lyricsContainer) {
            this.lyricsContainer = document.getElementById('lyrics-content');
        }
        
        if (this.lyricsContainer && this.syncedLyrics.length > 0) {
            this.lyricsContainer.innerHTML = this.syncedLyrics
                .map((line, index) => `
                    <div class="lyrics-line ${index === 0 ? 'active' : ''}" 
                         data-time="${line.time}" 
                         data-index="${index}">
                        ${this.escapeHtml(line.text)}
                    </div>
                `)
                .join('');
        }
    }
    
    setLyricsText(text) {
        if (!this.lyricsContainer) {
            this.lyricsContainer = document.getElementById('lyrics-content');
        }
        
        if (this.lyricsContainer) {
            this.lyricsContainer.textContent = text;
        }
    }
    
    updateSyncedLyrics(currentTime) {
        if (!this.isSynced || this.syncedLyrics.length === 0) {
            return;
        }
        
        const adjustedTime = currentTime + this.lyricsOffset;
        let newLineIndex = -1;
        
        // Find current line based on time
        for (let i = this.syncedLyrics.length - 1; i >= 0; i--) {
            if (adjustedTime >= this.syncedLyrics[i].time) {
                newLineIndex = i;
                break;
            }
        }
        
        // Update active line
        if (newLineIndex !== this.currentLine) {
            // Remove active class from all lines
            document.querySelectorAll('.lyrics-line').forEach(line => {
                line.classList.remove('active');
            });
            
            // Add active class to current line
            if (newLineIndex >= 0) {
                const currentLineEl = document.querySelector(`.lyrics-line[data-index="${newLineIndex}"]`);
                if (currentLineEl) {
                    currentLineEl.classList.add('active');
                    
                    // Scroll to active line
                    currentLineEl.scrollIntoView({
                        behavior: 'smooth',
                        block: 'center'
                    });
                }
            }
            
            this.currentLine = newLineIndex;
        }
    }
    
    adjustOffset(seconds) {
        this.lyricsOffset += seconds;
        
        // Show offset notification
        this.showOffsetNotification();
        
        return this.lyricsOffset;
    }
    
    showOffsetNotification() {
        const offset = this.lyricsOffset.toFixed(1);
        const direction = this.lyricsOffset >= 0 ? 'ahead' : 'behind';
        
        // Create or update notification
        let notification = document.getElementById('lyrics-offset-notification');
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'lyrics-offset-notification';
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(139, 92, 246, 0.9);
                color: white;
                padding: 10px 20px;
                border-radius: 10px;
                font-size: 14px;
                z-index: 1000;
                backdrop-filter: blur(10px);
            `;
            document.body.appendChild(notification);
        }
        
        notification.textContent = `Lyrics ${Math.abs(offset)}s ${direction}`;
        notification.style.display = 'block';
        
        // Hide after 3 seconds
        setTimeout(() => {
            notification.style.display = 'none';
        }, 3000);
    }
    
    resetOffset() {
        this.lyricsOffset = 0;
        this.showOffsetNotification();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Keyboard shortcuts for offset adjustment
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            if (e.altKey && e.key === 'ArrowUp') {
                e.preventDefault();
                this.adjustOffset(0.1); // +100ms
            } else if (e.altKey && e.key === 'ArrowDown') {
                e.preventDefault();
                this.adjustOffset(-0.1); // -100ms
            } else if (e.altKey && e.key === '0') {
                e.preventDefault();
                this.resetOffset();
            }
        });
    }
    
    // Save lyrics to local storage
    saveLyricsToCache(title, artist, lyrics) {
        const cacheKey = `lyrics_${title}_${artist}`;
        const cacheData = {
            lyrics: lyrics,
            timestamp: Date.now(),
            isSynced: this.isSynced,
            syncedLyrics: this.syncedLyrics
        };
        
        localStorage.setItem(cacheKey, JSON.stringify(cacheData));
    }
    
    // Load lyrics from cache
    loadLyricsFromCache(title, artist) {
        const cacheKey = `lyrics_${title}_${artist}`;
        const cached = localStorage.getItem(cacheKey);
        
        if (cached) {
            try {
                const data = JSON.parse(cached);
                
                // Check if cache is less than 30 days old
                if (Date.now() - data.timestamp < 30 * 24 * 60 * 60 * 1000) {
                    this.lyrics = data.lyrics.split('\n');
                    this.isSynced = data.isSynced;
                    this.syncedLyrics = data.syncedLyrics || [];
                    
                    if (this.isSynced) {
                        this.displaySyncedLyrics();
                    } else {
                        this.displayPlainLyrics();
                    }
                    
                    return true;
                }
            } catch (error) {
                console.warn('Failed to parse cached lyrics:', error);
            }
        }
        
        return false;
    }
}

// Create global instance
window.lyricsManager = new LyricsManager();
window.lyricsManager.setupKeyboardShortcuts();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LyricsManager;
}