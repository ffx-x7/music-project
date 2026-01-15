import asyncio
import os
import json
import yt_dlp
import aiohttp
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor
import subprocess
import tempfile

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, cache_dir: str = "static/cache", music_dir: str = "static/music"):
        self.cache_dir = Path(cache_dir)
        self.music_dir = Path(music_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for metadata
        self.metadata_cache = {}
        self.stream_cache = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Quality presets
        self.quality_presets = {
            'low': {
                'format': 'worstaudio/worst',
                'abr': 64,
                'ext': 'mp3'
            },
            'medium': {
                'format': 'bestaudio[abr<=128]/best',
                'abr': 128,
                'ext': 'mp3'
            },
            'high': {
                'format': 'bestaudio[abr<=192]/best',
                'abr': 192,
                'ext': 'mp3'
            },
            'premium': {
                'format': 'bestaudio[abr<=320]/best',
                'abr': 320,
                'ext': 'mp3'
            }
        }
        
        # Thread pool for blocking operations
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Initialize cache cleaner
        self.clean_cache_periodically()
    
    def get_cache_key(self, video_id: str, quality: str = None) -> str:
        """Generate cache key for video"""
        key = f"video_{video_id}"
        if quality:
            key += f"_{quality}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def get_cached_metadata(self, video_id: str) -> Optional[Dict]:
        """Get cached metadata"""
        cache_key = self.get_cache_key(video_id)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
                if datetime.now().timestamp() - cache_data['timestamp'] < self.cache_ttl:
                    return cache_data['data']
        return None
    
    def cache_metadata(self, video_id: str, metadata: Dict):
        """Cache video metadata"""
        cache_key = self.get_cache_key(video_id)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        cache_data = {
            'timestamp': datetime.now().timestamp(),
            'data': metadata,
            'video_id': video_id
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
    
    async def get_video_info(self, video_id: str, use_cache: bool = True) -> Dict:
        """Get detailed video information"""
        if use_cache:
            cached = self.get_cached_metadata(video_id)
            if cached:
                return cached
        
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,
            }
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                self.executor,
                lambda: self._extract_info(f'https://www.youtube.com/watch?v={video_id}', ydl_opts)
            )
            
            if not info:
                raise Exception("Failed to extract video info")
            
            # Format metadata
            metadata = {
                'id': video_id,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'description': info.get('description', '')[:200],
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'upload_date': info.get('upload_date', ''),
                'categories': info.get('categories', []),
                'tags': info.get('tags', [])[:10],
                'formats': []
            }
            
            # Extract audio formats
            if 'formats' in info:
                audio_formats = []
                for fmt in info['formats']:
                    if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                        audio_formats.append({
                            'format_id': fmt.get('format_id', ''),
                            'ext': fmt.get('ext', ''),
                            'abr': fmt.get('abr', 0),
                            'filesize': fmt.get('filesize', 0),
                            'url': fmt.get('url', '')
                        })
                
                # Sort by bitrate
                audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
                metadata['formats'] = audio_formats
            
            # Cache the metadata
            self.cache_metadata(video_id, metadata)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting video info for {video_id}: {str(e)}")
            raise
    
    def _extract_info(self, url: str, ydl_opts: Dict) -> Optional[Dict]:
        """Extract video info using yt-dlp (blocking)"""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"yt-dlp extraction error: {str(e)}")
            return None
    
    async def get_stream_url(self, video_id: str, quality: str = 'high') -> Optional[str]:
        """Get direct stream URL for audio"""
        try:
            # Check stream cache first
            cache_key = f"stream_{video_id}_{quality}"
            if cache_key in self.stream_cache:
                cached_data = self.stream_cache[cache_key]
                if datetime.now().timestamp() - cached_data['timestamp'] < 1800:  # 30 minutes
                    return cached_data['url']
            
            info = await self.get_video_info(video_id)
            
            # Find suitable format
            target_abr = self.quality_presets.get(quality, {}).get('abr', 192)
            
            if info.get('formats'):
                # Try to find exact match
                for fmt in info['formats']:
                    if fmt.get('abr', 0) >= target_abr and fmt.get('url'):
                        # Cache the URL
                        self.stream_cache[cache_key] = {
                            'url': fmt['url'],
                            'timestamp': datetime.now().timestamp()
                        }
                        return fmt['url']
                
                # Fallback to best available
                for fmt in info['formats']:
                    if fmt.get('url'):
                        self.stream_cache[cache_key] = {
                            'url': fmt['url'],
                            'timestamp': datetime.now().timestamp()
                        }
                        return fmt['url']
            
            # If no format found, use yt-dlp to extract
            ydl_opts = {
                'format': self.quality_presets.get(quality, {}).get('format', 'bestaudio/best'),
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': False,
            }
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                self.executor,
                lambda: self._extract_info(f'https://www.youtube.com/watch?v={video_id}', ydl_opts)
            )
            
            if info and 'url' in info:
                self.stream_cache[cache_key] = {
                    'url': info['url'],
                    'timestamp': datetime.now().timestamp()
                }
                return info['url']
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting stream URL for {video_id}: {str(e)}")
            return None
    
    async def download_audio(self, video_id: str, quality: str = 'high') -> Tuple[bool, str]:
        """Download audio file with specified quality"""
        output_file = self.music_dir / f"{video_id}_{quality}.mp3"
        
        # Check if already exists
        if output_file.exists():
            return True, str(output_file)
        
        try:
            preset = self.quality_presets.get(quality, self.quality_presets['high'])
            
            ydl_opts = {
                'format': preset['format'],
                'outtmpl': str(output_file.with_suffix('.%(ext)s')),
                'quiet': False,
                'no_warnings': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': str(preset['abr']),
                }],
                'progress_hooks': [self._download_progress_hook],
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            }
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                lambda: self._download_with_ytdlp(f'https://www.youtube.com/watch?v={video_id}', ydl_opts)
            )
            
            if output_file.exists():
                # Optimize file if needed
                await self.optimize_audio_file(str(output_file))
                return True, str(output_file)
            else:
                return False, "Download failed"
                
        except Exception as e:
            logger.error(f"Download error for {video_id}: {str(e)}")
            return False, str(e)
    
    def _download_with_ytdlp(self, url: str, ydl_opts: Dict):
        """Download using yt-dlp (blocking)"""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            logger.error(f"yt-dlp download error: {str(e)}")
            raise
    
    def _download_progress_hook(self, d: Dict):
        """Progress hook for downloads"""
        if d['status'] == 'downloading':
            filename = d.get('filename', '')
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            
            if total > 0:
                percent = (downloaded / total) * 100
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                logger.info(f"Downloading: {percent:.1f}% - Speed: {speed/1024:.1f}KB/s - ETA: {eta}s")
    
    async def optimize_audio_file(self, filepath: str):
        """Optimize audio file using ffmpeg"""
        try:
            # Check if ffmpeg is available
            if not self._check_ffmpeg():
                return False
            
            temp_file = f"{filepath}.tmp"
            
            # Normalize audio and optimize
            cmd = [
                'ffmpeg', '-i', filepath,
                '-af', 'loudnorm=I=-16:LRA=11:TP=-1.5',
                '-c:a', 'libmp3lame',
                '-q:a', '2',
                '-y', temp_file
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0 and os.path.exists(temp_file):
                os.replace(temp_file, filepath)
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Audio optimization error: {str(e)}")
            return False
    
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE,
                         check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    async def convert_to_mp3(self, input_file: str, output_file: str = None) -> Optional[str]:
        """Convert any audio file to MP3"""
        if not output_file:
            output_file = input_file.rsplit('.', 1)[0] + '.mp3'
        
        try:
            cmd = [
                'ffmpeg', '-i', input_file,
                '-c:a', 'libmp3lame',
                '-q:a', '2',
                '-y', output_file
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_file):
                return output_file
                
            return None
            
        except Exception as e:
            logger.error(f"Conversion error: {str(e)}")
            return None
    
    async def extract_audio_segment(self, input_file: str, start: float, duration: float) -> Optional[str]:
        """Extract a segment of audio"""
        try:
            output_file = tempfile.mktemp(suffix='.mp3')
            
            cmd = [
                'ffmpeg', '-i', input_file,
                '-ss', str(start),
                '-t', str(duration),
                '-c:a', 'libmp3lame',
                '-q:a', '2',
                '-y', output_file
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_file):
                return output_file
                
            return None
            
        except Exception as e:
            logger.error(f"Segment extraction error: {str(e)}")
            return None
    
    def get_downloaded_songs(self) -> List[Dict]:
        """Get list of downloaded songs"""
        songs = []
        
        for file in self.music_dir.glob('*.mp3'):
            stat = file.stat()
            video_id = file.stem.split('_')[0]
            quality = file.stem.split('_')[1] if '_' in file.stem else 'high'
            
            songs.append({
                'id': video_id,
                'quality': quality,
                'filename': file.name,
                'path': str(file),
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'duration': 0  # Would need to extract from file
            })
        
        return sorted(songs, key=lambda x: x['modified'], reverse=True)
    
    def clean_cache_periodically(self):
        """Clean old cache files periodically"""
        try:
            now = datetime.now().timestamp()
            for cache_file in self.cache_dir.glob('*.json'):
                try:
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                        if now - data.get('timestamp', 0) > self.cache_ttl:
                            cache_file.unlink()
                except:
                    continue
                    
            # Clean stream cache
            expired_keys = [
                k for k, v in self.stream_cache.items()
                if now - v['timestamp'] > 1800
            ]
            for key in expired_keys:
                del self.stream_cache[key]
                
        except Exception as e:
            logger.error(f"Cache cleanup error: {str(e)}")
    
    async def get_audio_analysis(self, filepath: str) -> Optional[Dict]:
        """Analyze audio file (basic info)"""
        try:
            if not os.path.exists(filepath):
                return None
            
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                filepath
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await process.communicate()
            
            if process.returncode == 0:
                data = json.loads(stdout.decode())
                
                # Extract audio stream info
                audio_streams = [
                    stream for stream in data.get('streams', [])
                    if stream.get('codec_type') == 'audio'
                ]
                
                if audio_streams:
                    audio_info = audio_streams[0]
                    return {
                        'duration': float(data.get('format', {}).get('duration', 0)),
                        'bitrate': int(data.get('format', {}).get('bit_rate', 0)),
                        'codec': audio_info.get('codec_name', ''),
                        'sample_rate': audio_info.get('sample_rate', ''),
                        'channels': audio_info.get('channels', 1)
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Audio analysis error: {str(e)}")
            return None

# Singleton instance
audio_processor = AudioProcessor()