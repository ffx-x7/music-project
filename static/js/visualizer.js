class AudioVisualizer {
    constructor(canvasId = 'visualizer-canvas') {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.audioContext = null;
        this.analyser = null;
        this.source = null;
        this.dataArray = null;
        this.bufferLength = null;
        this.isPlaying = false;
        this.animationId = null;
        this.visualizerType = 'bars'; // 'bars', 'wave', 'circle', 'particles'
        this.colorScheme = 'rainbow';
        this.smoothing = 0.8;
        this.fftSize = 2048;
        
        this.init();
    }
    
    init() {
        this.setupCanvas();
        this.setupEventListeners();
    }
    
    setupCanvas() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
    }
    
    resizeCanvas() {
        this.canvas.width = this.canvas.clientWidth;
        this.canvas.height = this.canvas.clientHeight;
        this.drawBackground();
    }
    
    drawBackground() {
        this.ctx.fillStyle = 'rgba(15, 23, 42, 0.3)';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
    
    setupEventListeners() {
        // Type selector
        document.addEventListener('visualizerTypeChange', (e) => {
            this.visualizerType = e.detail.type;
        });
        
        // Color scheme selector
        document.addEventListener('visualizerColorChange', (e) => {
            this.colorScheme = e.detail.scheme;
        });
    }
    
    connect(audioElement) {
        if (!audioElement) {
            console.error('No audio element provided');
            return;
        }
        
        // Create audio context if not exists
        if (!this.audioContext) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContext();
        }
        
        // Resume context if suspended
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }
        
        // Create analyser
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = this.fftSize;
        this.analyser.smoothingTimeConstant = this.smoothing;
        
        // Create source from audio element
        this.source = this.audioContext.createMediaElementSource(audioElement);
        
        // Connect nodes
        this.source.connect(this.analyser);
        this.analyser.connect(this.audioContext.destination);
        
        // Setup data array
        this.bufferLength = this.analyser.frequencyBinCount;
        this.dataArray = new Uint8Array(this.bufferLength);
        
        // Start visualization
        this.startVisualization();
    }
    
    disconnect() {
        if (this.source) {
            this.source.disconnect();
        }
        if (this.analyser) {
            this.analyser.disconnect();
        }
        this.stopVisualization();
    }
    
    startVisualization() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        this.isPlaying = true;
        this.visualize();
    }
    
    stopVisualization() {
        this.isPlaying = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        this.drawBackground();
    }
    
    visualize() {
        if (!this.isPlaying || !this.analyser) {
            return;
        }
        
        this.animationId = requestAnimationFrame(() => this.visualize());
        
        // Clear canvas with fade effect
        this.ctx.fillStyle = 'rgba(15, 23, 42, 0.1)';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Get frequency data
        this.analyser.getByteFrequencyData(this.dataArray);
        
        // Draw based on selected type
        switch (this.visualizerType) {
            case 'bars':
                this.drawBars();
                break;
            case 'wave':
                this.drawWave();
                break;
            case 'circle':
                this.drawCircle();
                break;
            case 'particles':
                this.drawParticles();
                break;
            default:
                this.drawBars();
        }
    }
    
    drawBars() {
        const barWidth = (this.canvas.width / this.bufferLength) * 2.5;
        let barHeight;
        let x = 0;
        
        for (let i = 0; i < this.bufferLength; i++) {
            barHeight = this.dataArray[i] * (this.canvas.height / 256);
            
            // Get color based on scheme
            const color = this.getColor(i, this.bufferLength);
            
            this.ctx.fillStyle = color;
            this.ctx.fillRect(
                x,
                this.canvas.height - barHeight,
                barWidth,
                barHeight
            );
            
            x += barWidth + 1;
        }
    }
    
    drawWave() {
        this.analyser.getByteTimeDomainData(this.dataArray);
        
        this.ctx.lineWidth = 2;
        this.ctx.strokeStyle = this.getColor(0, 1);
        this.ctx.beginPath();
        
        const sliceWidth = this.canvas.width * 1.0 / this.bufferLength;
        let x = 0;
        
        for (let i = 0; i < this.bufferLength; i++) {
            const v = this.dataArray[i] / 128.0;
            const y = v * this.canvas.height / 2;
            
            if (i === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
            
            x += sliceWidth;
        }
        
        this.ctx.lineTo(this.canvas.width, this.canvas.height / 2);
        this.ctx.stroke();
    }
    
    drawCircle() {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        const radius = Math.min(centerX, centerY) * 0.8;
        
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        
        for (let i = 0; i < this.bufferLength; i++) {
            const amplitude = this.dataArray[i] / 256;
            const angle = (i * 2 * Math.PI) / this.bufferLength;
            const pointRadius = radius + (amplitude * radius * 0.5);
            
            const x = centerX + pointRadius * Math.cos(angle);
            const y = centerY + pointRadius * Math.sin(angle);
            
            if (i === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        }
        
        this.ctx.closePath();
        this.ctx.strokeStyle = this.getGradient();
        this.ctx.stroke();
    }
    
    drawParticles() {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        
        for (let i = 0; i < this.bufferLength; i += 4) {
            const amplitude = this.dataArray[i] / 256;
            
            if (amplitude > 0.1) {
                const angle = (i * 2 * Math.PI) / this.bufferLength;
                const distance = 50 + (amplitude * 200);
                
                const x = centerX + distance * Math.cos(angle);
                const y = centerY + distance * Math.sin(angle);
                
                // Particle size based on amplitude
                const size = 2 + (amplitude * 8);
                
                // Draw particle
                this.ctx.beginPath();
                this.ctx.arc(x, y, size, 0, 2 * Math.PI);
                this.ctx.fillStyle = this.getColor(i, this.bufferLength);
                this.ctx.fill();
                
                // Draw trail
                this.ctx.beginPath();
                this.ctx.moveTo(centerX, centerY);
                this.ctx.lineTo(x, y);
                this.ctx.strokeStyle = this.getColor(i, this.bufferLength, 0.3);
                this.ctx.lineWidth = 1;
                this.ctx.stroke();
            }
        }
    }
    
    getColor(index, total, alpha = 1.0) {
        switch (this.colorScheme) {
            case 'rainbow':
                const hue = (index / total) * 360;
                return `hsla(${hue}, 100%, 60%, ${alpha})`;
                
            case 'purple':
                const intensity = index / total;
                return `rgba(139, 92, 246, ${intensity * alpha})`;
                
            case 'green':
                const greenIntensity = index / total;
                return `rgba(16, 185, 129, ${greenIntensity * alpha})`;
                
            case 'fire':
                const fireValue = index / total;
                const r = 255;
                const g = Math.floor(fireValue * 100);
                const b = 0;
                return `rgba(${r}, ${g}, ${b}, ${alpha})`;
                
            case 'ocean':
                const oceanValue = index / total;
                const blueR = 0;
                const blueG = Math.floor(oceanValue * 150);
                const blueB = 255;
                return `rgba(${blueR}, ${blueG}, ${blueB}, ${alpha})`;
                
            default:
                return `rgba(139, 92, 246, ${alpha})`;
        }
    }
    
    getGradient() {
        const gradient = this.ctx.createLinearGradient(
            0, 0, this.canvas.width, this.canvas.height
        );
        
        switch (this.colorScheme) {
            case 'rainbow':
                gradient.addColorStop(0, '#FF0000');
                gradient.addColorStop(0.2, '#FFFF00');
                gradient.addColorStop(0.4, '#00FF00');
                gradient.addColorStop(0.6, '#00FFFF');
                gradient.addColorStop(0.8, '#0000FF');
                gradient.addColorStop(1, '#FF00FF');
                break;
                
            case 'purple':
                gradient.addColorStop(0, '#8B5CF6');
                gradient.addColorStop(1, '#EC4899');
                break;
                
            case 'green':
                gradient.addColorStop(0, '#10B981');
                gradient.addColorStop(1, '#84CC16');
                break;
                
            default:
                gradient.addColorStop(0, '#8B5CF6');
                gradient.addColorStop(1, '#3B82F6');
        }
        
        return gradient;
    }
    
    setType(type) {
        if (['bars', 'wave', 'circle', 'particles'].includes(type)) {
            this.visualizerType = type;
        }
    }
    
    setColorScheme(scheme) {
        if (['rainbow', 'purple', 'green', 'fire', 'ocean'].includes(scheme)) {
            this.colorScheme = scheme;
        }
    }
    
    setSmoothing(value) {
        if (this.analyser) {
            this.analyser.smoothingTimeConstant = Math.max(0, Math.min(1, value));
        }
    }
    
    toggle() {
        if (this.isPlaying) {
            this.stopVisualization();
        } else {
            this.startVisualization();
        }
    }
    
    // Utility function to get frequency range
    getFrequencyRange() {
        if (!this.audioContext) return { min: 0, max: 0 };
        
        const nyquist = this.audioContext.sampleRate / 2;
        return {
            min: 0,
            max: nyquist,
            bands: this.bufferLength
        };
    }
    
    // Get current volume level
    getVolumeLevel() {
        if (!this.dataArray) return 0;
        
        let sum = 0;
        for (let i = 0; i < this.dataArray.length; i++) {
            sum += this.dataArray[i];
        }
        return sum / this.dataArray.length / 256;
    }
    
    // Get peak frequency
    getPeakFrequency() {
        if (!this.dataArray) return 0;
        
        let maxIndex = 0;
        let maxValue = 0;
        
        for (let i = 0; i < this.dataArray.length; i++) {
            if (this.dataArray[i] > maxValue) {
                maxValue = this.dataArray[i];
                maxIndex = i;
            }
        }
        
        const nyquist = this.audioContext ? this.audioContext.sampleRate / 2 : 24000;
        return (maxIndex / this.bufferLength) * nyquist;
    }
}

// Create global instance
window.audioVisualizer = new AudioVisualizer();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AudioVisualizer;
}