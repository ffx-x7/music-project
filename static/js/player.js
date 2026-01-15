class PremiumMusicPlayer {
    constructor() {
        this.audio = document.getElementById('audio-player');
        this.currentSong = null;
        this.queue = [];
        this.playlist = [];
        this.currentIndex = -1;
        this.isPlaying = false;
        this.isShuffled = false;
        this.repeatMode = 'none'; // 'none', 'one', 'all'
        this.volume = 80;
        this.quality = 'high';
        this.currentTime = 0;
        this.duration = 0;
        
        this.init();
    }
    
    init() {
        this.loadSettings();
        this.setupEventListeners();
        this.loadPlaylist();
        this.setupAudioContext();
        this.checkConnectivity();
    }
    
    setupEventListeners() {
        // Player controls
        document.getElementById('play-btn').addEventListener('click', () => this.togglePlay());
        document.getElementById('prev-btn').addEventListener('click', () => this.prev());
        document.getElementById('next-btn').addEventListener('click', () => this.next());
        document.getElementById('shuffle-btn').addEventListener('click', () => this.toggleShuffle());
        document.getElementById('repeat-btn').addEventListener('click', () => this.toggleRepeat());
        
        // Volume
        document.getElementById('volume-btn').addEventListener('click', () => this.toggleMute());
        document.getElementById('volume-slider').addEventListener('input', (e) => {
            this.volume = e.target.value;
            this.audio.volume = this.volume / 100;
            this.saveSettings();
        });
        
        // Seek
        document.getElementById('seek-slider').addEventListener('input', (e) => {
            if (this.duration) {
                const seekTime = (e.target.value / 100) * this.duration;
                this.audio.currentTime = seekTime;
            }
        });
        
        // Audio events
        this.audio.addEventListener('timeupdate', () => this.updateProgress());
        this.audio.addEventListener('loadedmetadata', () => {
            this.duration = this.audio.duration;
            this.updateDurationDisplay();
        });
        this.audio.addEventListener('ended', () => this.onSongEnd());
        this.audio.addEventListener('error', (e) => this.handleError(e));
        this.audio.addEventListener('canplay', () => {
            document.getElementById('loading-spinner').style.display = 'none';
            if (this.isPlaying) {
                this.audio.play().catch(e => {
                    console.error('Play error:', e);
                    this.showNotification('Playback error', 'error');
                });
            }
        });
        
        this.audio.addEventListener('waiting', () => {
            document.getElementById('loading-spinner').style.display = 'flex';
        });
        
        // Search
        document.getElementById('search-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.search();
        });
        document.getElementById('search-btn').addEventListener('click', () => this.search());
        
        // Theme toggle
        document.getElementById('theme-toggle').addEventListener('click', () => this.toggleTheme());
        
        // Download
        document.getElementById('download-btn').addEventListener('click', () => this.downloadCurrent());
        
        // Favorite
        document.getElementById('favorite-btn').addEventListener('click', () => this.toggleFavorite());
        
        // Quality
        document.getElementById('quality-select').addEventListener('change', (e) => {
            this.quality = e.target.value;
            this.saveSettings();
        });
        
        // Visualizer
        if (window.audioVisualizer) {
            document.getElementById('visualizer-toggle').addEventListener('click', () => {
                window.audioVisualizer.toggle();
            });
        }
        
        // Lyrics
        document.getElementById('lyrics-toggle').addEventListener('click', () => {
            if (this.currentSong) {
                this.fetchLyrics();
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT') return;
            
            switch(e.key) {
                case ' ':
                    e.preventDefault();
                    this.togglePlay();
                    break;
                case 'ArrowLeft':
                    this.seek(-5);
                    break;
                case 'ArrowRight':
                    this.seek(5);
                    break;
                case 'ArrowUp':
                    this.changeVolume(10);
                    break;
                case 'ArrowDown':
                    this.changeVolume(-10);
                    break;
                case 'm':
                    this.toggleMute();
                    break;
            }
        });
        
        // Offline support
        window.addEventListener('online', () => this.showNotification('Back online', 'success'));
        window.addEventListener('offline', () => this.showNotification('You are offline', 'warning'));
    }
    
    async search(query = null) {
        const searchInput = document.getElementById('search-input');
        const queryText = query || searchInput.value.trim();
        
        if (!queryText) return;
        
        this.showLoading(true);
        
        try {
            const response = await fetch(`/api/search?q=${encodeURIComponent(queryText)}&limit=15`);
            const data = await response.json();
            
            if (data.success) {
                this.displaySearchResults(data.results);
                this.showNotification(`Found ${data.count} results`, 'success');
            } else {
                throw new Error('Search failed');
            }
        } catch (error) {
            console.error('Search error:', error);
            this.showNotification('Search failed', 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    displaySearchResults(results) {
        const container = document.getElementById('search-results');
        container.innerHTML = '';
        
        results.forEach(song => {
            const card = this.createSongCard(song);
            container.appendChild(card);
        });
    }
    
    createSongCard(song) {
        const div = document.createElement('div');
        div.className = 'song-card fade-in';
        div.innerHTML = `
            <img src="${song.thumbnail}" alt="${song.title}" loading="lazy">
            <div class="card-content">
                <h4 title="${song.title}">${song.title}</h4>
                <p>${song.channel} • ${song.duration}</p>
                <div class="card-actions">
                    <button class="icon-btn play-song" data-id="${song.id}">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="icon-btn queue-song" data-id="${song.id}" data-title="${song.title}">
                        <i class="fas fa-plus"></i>
                    </button>
                    <button class="icon-btn download-song" data-id="${song.id}">
                        <i class="fas fa-download"></i>
                    </button>
                </div>
            </div>
        `;
        
        // Add event listeners
        div.querySelector('.play-song').addEventListener('click', () => this.playSong(song));
        div.querySelector('.queue-song').addEventListener('click', () => this.addToQueue(song));
        div.querySelector('.download-song').addEventListener('click', () => this.downloadSong(song.id));
        
        return div;
    }
    
    async playSong(song, addToQueue = false) {
        if (!addToQueue) {
            this.queue = [song];
            this.currentIndex = 0;
        }
        
        this.currentSong = song;
        this.showLoading(true);
        
        // Update UI
        document.getElementById('current-title').textContent = song.title;
        document.getElementById('current-artist').textContent = song.channel;
        document.getElementById('current-album-art').src = song.thumbnail;
        
        // Start vinyl animation
        document.querySelector('.album-art').classList.add('playing');
        
        try {
            // Get stream URL
            const streamUrl = `/api/stream/${song.id}?quality=${this.quality}`;
            this.audio.src = streamUrl;
            this.audio.load();
            
            // Preload next song
            if (this.queue.length > this.currentIndex + 1) {
                const nextSong = this.queue[this.currentIndex + 1];
                this.preloadSong(nextSong.id);
            }
            
            this.isPlaying = true;
            this.updatePlayButton();
            
            this.showNotification(`Now playing: ${song.title}`, 'success');
            
            // Start visualizer if available
            if (window.audioVisualizer) {
                window.audioVisualizer.connect(this.audio);
            }
            
        } catch (error) {
            console.error('Play error:', error);
            this.showNotification('Failed to play song', 'error');
            this.showLoading(false);
        }
    }
    
    async preloadSong(videoId) {
        // Preload song in background
        fetch(`/api/info/${videoId}`).catch(() => {});
    }
    
    togglePlay() {
        if (!this.currentSong) {
            if (this.queue.length > 0) {
                this.playSong(this.queue[0]);
            }
            return;
        }
        
        if (this.isPlaying) {
            this.audio.pause();
            document.querySelector('.album-art').classList.remove('playing');
        } else {
            this.audio.play().catch(e => {
                console.error('Play error:', e);
                this.showNotification('Playback error', 'error');
            });
            document.querySelector('.album-art').classList.add('playing');
        }
        
        this.isPlaying = !this.isPlaying;
        this.updatePlayButton();
    }
    
    updatePlayButton() {
        const playBtn = document.getElementById('play-btn');
        playBtn.innerHTML = this.isPlaying ? 
            '<i class="fas fa-pause"></i>' : 
            '<i class="fas fa-play"></i>';
    }
    
    async next() {
        if (this.queue.length === 0) return;
        
        if (this.repeatMode === 'one') {
            this.audio.currentTime = 0;
            this.audio.play();
            return;
        }
        
        this.currentIndex++;
        
        if (this.currentIndex >= this.queue.length) {
            if (this.repeatMode === 'all') {
                this.currentIndex = 0;
            } else {
                this.currentIndex = this.queue.length - 1;
                return;
            }
        }
        
        await this.playSong(this.queue[this.currentIndex]);
    }
    
    async prev() {
        if (this.queue.length === 0) return;
        
        if (this.audio.currentTime > 5) {
            this.audio.currentTime = 0;
            return;
        }
        
        this.currentIndex--;
        
        if (this.currentIndex < 0) {
            if (this.repeatMode === 'all') {
                this.currentIndex = this.queue.length - 1;
            } else {
                this.currentIndex = 0;
                return;
            }
        }
        
        await this.playSong(this.queue[this.currentIndex]);
    }
    
    toggleShuffle() {
        this.isShuffled = !this.isShuffled;
        const btn = document.getElementById('shuffle-btn');
        btn.style.color = this.isShuffled ? 'var(--primary)' : 'var(--light)';
        
        if (this.isShuffled && this.queue.length > 1) {
            this.shuffleQueue();
        }
        
        this.showNotification(this.isShuffled ? 'Shuffle: ON' : 'Shuffle: OFF', 'info');
    }
    
    shuffleQueue() {
        const current = this.queue[this.currentIndex];
        const others = this.queue.filter((_, i) => i !== this.currentIndex);
        
        // Fisher-Yates shuffle
        for (let i = others.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [others[i], others[j]] = [others[j], others[i]];
        }
        
        this.queue = [current, ...others];
        this.updateQueueDisplay();
    }
    
    toggleRepeat() {
        const modes = ['none', 'one', 'all'];
        const currentIndex = modes.indexOf(this.repeatMode);
        this.repeatMode = modes[(currentIndex + 1) % modes.length];
        
        const btn = document.getElementById('repeat-btn');
        const icons = ['fa-redo', 'fa-redo', 'fa-infinity'];
        btn.innerHTML = `<i class="fas ${icons[currentIndex + 1]}"></i>`;
        btn.style.color = this.repeatMode === 'none' ? 'var(--light)' : 'var(--primary)';
        
        this.showNotification(`Repeat: ${this.repeatMode.toUpperCase()}`, 'info');
    }
    
    addToQueue(song) {
        this.queue.push(song);
        this.updateQueueDisplay();
        this.showNotification(`Added to queue: ${song.title}`, 'success');
    }
    
    updateQueueDisplay() {
        const container = document.getElementById('queue-list');
        container.innerHTML = '';
        
        this.queue.forEach((song, index) => {
            const item = document.createElement('div');
            item.className = `queue-item ${index === this.currentIndex ? 'active' : ''}`;
            item.innerHTML = `
                <img src="${song.thumbnail}" alt="${song.title}">
                <div class="queue-info">
                    <h6>${song.title}</h6>
                    <p>${song.channel}</p>
                </div>
                <span>${song.duration}</span>
            `;
            
            item.addEventListener('click', () => {
                this.currentIndex = index;
                this.playSong(song);
            });
            
            container.appendChild(item);
        });
        
        // Update stats
        const totalDuration = this.queue.reduce((sum, song) => {
            const [min, sec] = song.duration.split(':').map(Number);
            return sum + (min * 60) + (sec || 0);
        }, 0);
        
        const hours = Math.floor(totalDuration / 3600);
        const minutes = Math.floor((totalDuration % 3600) / 60);
        
        document.getElementById('queue-count').textContent = this.queue.length;
        document.getElementById('queue-total').textContent = 
            hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
    }
    
    updateProgress() {
        if (!this.audio.duration) return;
        
        this.currentTime = this.audio.currentTime;
        this.duration = this.audio.duration;
        
        // Update progress bar
        const progressPercent = (this.currentTime / this.duration) * 100;
        document.getElementById('song-progress').style.width = `${progressPercent}%`;
        document.getElementById('seek-slider').value = progressPercent;
        
        // Update time display
        document.getElementById('current-time').textContent = this.formatTime(this.currentTime);
        document.getElementById('total-time').textContent = this.formatTime(this.duration);
    }
    
    updateDurationDisplay() {
        document.getElementById('total-time').textContent = this.formatTime(this.duration);
    }
    
    formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
    
    seek(seconds) {
        this.audio.currentTime = Math.max(0, Math.min(this.audio.currentTime + seconds, this.duration));
    }
    
    changeVolume(delta) {
        this.volume = Math.max(0, Math.min(100, this.volume + delta));
        this.audio.volume = this.volume / 100;
        document.getElementById('volume-slider').value = this.volume;
        this.saveSettings();
    }
    
    toggleMute() {
        const isMuted = this.audio.volume === 0;
        this.audio.volume = isMuted ? this.volume / 100 : 0;
        document.getElementById('volume-btn').innerHTML = isMuted ? 
            '<i class="fas fa-volume-up"></i>' : 
            '<i class="fas fa-volume-mute"></i>';
    }
    
    async downloadSong(videoId) {
        try {
            this.showNotification('Starting download...', 'info');
            
            const response = await fetch(`/api/download/${videoId}`);
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${videoId}.mp3`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                this.showNotification('Download complete!', 'success');
            } else {
                throw new Error('Download failed');
            }
        } catch (error) {
            console.error('Download error:', error);
            this.showNotification('Download failed', 'error');
        }
    }
    
    async downloadCurrent() {
        if (this.currentSong) {
            await this.downloadSong(this.currentSong.id);
        }
    }
    
    toggleFavorite() {
        if (!this.currentSong) return;
        
        const favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
        const isFavorite = favorites.some(f => f.id === this.currentSong.id);
        
        if (isFavorite) {
            const index = favorites.findIndex(f => f.id === this.currentSong.id);
            favorites.splice(index, 1);
            this.showNotification('Removed from favorites', 'info');
        } else {
            favorites.push(this.currentSong);
            this.showNotification('Added to favorites!', 'success');
            
            // Confetti effect
            if (typeof confetti === 'function') {
                confetti({
                    particleCount: 100,
                    spread: 70,
                    origin: { y: 0.6 }
                });
            }
        }
        
        localStorage.setItem('favorites', JSON.stringify(favorites));
        
        // Update button
        const btn = document.getElementById('favorite-btn');
        btn.innerHTML = isFavorite ? 
            '<i class="far fa-heart"></i>' : 
            '<i class="fas fa-heart" style="color: #ef4444"></i>';
    }
    
    async fetchLyrics() {
        if (!this.currentSong) return;
        
        try {
            const response = await fetch(`/api/lyrics?title=${encodeURIComponent(this.currentSong.title)}&artist=${encodeURIComponent(this.currentSong.channel)}`);
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('lyrics-content').textContent = data.lyrics;
                document.getElementById('lyrics-panel').classList.add('show');
            }
        } catch (error) {
            console.error('Lyrics error:', error);
            document.getElementById('lyrics-content').textContent = 'Lyrics not available';
        }
    }
    
    loadPlaylist() {
        fetch('/api/playlist')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    this.playlist = data.playlist;
                    this.updatePlaylistCount();
                }
            })
            .catch(console.error);
    }
    
    updatePlaylistCount() {
        document.getElementById('download-count').textContent = this.playlist.length;
    }
    
    loadSettings() {
        const settings = JSON.parse(localStorage.getItem('playerSettings') || '{}');
        this.volume = settings.volume || 80;
        this.quality = settings.quality || 'high';
        this.theme = settings.theme || 'dark';
        
        this.audio.volume = this.volume / 100;
        document.getElementById('volume-slider').value = this.volume;
        document.getElementById('quality-select').value = this.quality;
        
        this.applyTheme();
    }
    
    saveSettings() {
        const settings = {
            volume: this.volume,
            quality: this.quality,
            theme: this.theme
        };
        localStorage.setItem('playerSettings', JSON.stringify(settings));
    }
    
    toggleTheme() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        this.applyTheme();
        this.saveSettings();
        
        const btn = document.getElementById('theme-toggle');
        btn.innerHTML = this.theme === 'dark' ? 
            '<i class="fas fa-moon"></i>' : 
            '<i class="fas fa-sun"></i>';
    }
    
    applyTheme() {
        const themeStyle = document.getElementById('theme-style');
        themeStyle.href = this.theme === 'dark' ? 
            '/static/css/dark-theme.css' : 
            '/static/css/light-theme.css';
    }
    
    setupAudioContext() {
        // Setup for visualizer
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                this.audioContext = new AudioContext();
            }
        } catch (e) {
            console.warn('Web Audio API not supported');
        }
    }
    
    checkConnectivity() {
        if (!navigator.onLine) {
            this.showNotification('You are offline', 'warning');
        }
    }
    
    onSongEnd() {
        switch(this.repeatMode) {
            case 'one':
                this.audio.currentTime = 0;
                this.audio.play();
                break;
            case 'all':
            case 'none':
            default:
                this.next();
                break;
        }
    }
    
    handleError(error) {
        console.error('Audio error:', error);
        this.showNotification('Playback error. Trying next song...', 'error');
        setTimeout(() => this.next(), 2000);
    }
    
    showLoading(show) {
        const spinner = document.getElementById('loading-spinner');
        spinner.style.display = show ? 'flex' : 'none';
    }
    
    showNotification(message, type = 'info') {
        const container = document.getElementById('notifications');
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <i class="fas fa-${this.getNotificationIcon(type)}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
    
    getNotificationIcon(type) {
        switch(type) {
            case 'success': return 'check-circle';
            case 'error': return 'exclamation-circle';
            case 'warning': return 'exclamation-triangle';
            default: return 'info-circle';
        }
    }
}

// Add fadeOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(100%); }
    }
    
    .lyrics-panel.show {
        display: block !important;
        animation: slideIn 0.3s ease-out;
    }
`;
document.head.appendChild(style);

// Initialize when ready
document.addEventListener('DOMContentLoaded', () => {
    window.player = new PremiumMusicPlayer();
});