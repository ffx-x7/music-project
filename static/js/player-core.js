// Core player functionality that works with both pages
class CorePlayer {
    constructor() {
        this.audio = new Audio();
        this.isPlaying = false;
        this.currentSong = null;
        this.volume = 80;
        
        this.setupAudio();
    }
    
    setupAudio() {
        // Enable cross-origin for visualizer
        this.audio.crossOrigin = 'anonymous';
        
        // Preload metadata
        this.audio.preload = 'metadata';
        
        // Event listeners
        this.audio.addEventListener('canplay', () => {
            console.log('Audio can play');
        });
        
        this.audio.addEventListener('error', (e) => {
            console.error('Audio error:', e);
        });
    }
    
    async playStream(url) {
        this.audio.src = url;
        
        try {
            await this.audio.play();
            this.isPlaying = true;
            return true;
        } catch (error) {
            console.error('Play error:', error);
            return false;
        }
    }
    
    pause() {
        this.audio.pause();
        this.isPlaying = false;
    }
    
    setVolume(level) {
        this.volume = Math.max(0, Math.min(100, level));
        this.audio.volume = this.volume / 100;
    }
    
    getCurrentTime() {
        return this.audio.currentTime;
    }
    
    getDuration() {
        return this.audio.duration;
    }
    
    seekTo(time) {
        this.audio.currentTime = time;
    }
    
    // Format time helper
    static formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}

// Export for use in other files
window.CorePlayer = CorePlayer;