from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import asyncio
import os
import json
import yt_dlp
import aiohttp
import aiofiles
from youtubesearchpython import VideosSearch, CustomSearch
import hashlib
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Premium Music Player", version="2.0")

# Templates
templates = Jinja2Templates(directory="templates")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
CACHE_DIR = Path("static/cache")
MUSIC_DIR = Path("static/music")
CACHE_DIR.mkdir(exist_ok=True)
MUSIC_DIR.mkdir(exist_ok=True)

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=10)

class PremiumAudioProcessor:
    def __init__(self):
        self.cache = {}
        self.processing = {}
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(MUSIC_DIR / '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
    
    async def search_videos(self, query: str, limit: int = 15):
        """Premium search with multiple sources"""
        try:
            # YouTube Search
            videos_search = VideosSearch(query, limit=limit)
            results = videos_search.result()
            
            formatted = []
            for video in results['result']:
                formatted.append({
                    'id': video['id'],
                    'title': video['title'],
                    'duration': self._format_duration(video.get('duration', '0:00')),
                    'duration_seconds': self._duration_to_seconds(video.get('duration', '0:00')),
                    'thumbnail': self._get_best_thumbnail(video.get('thumbnails', [])),
                    'channel': video.get('channel', {}).get('name', 'Unknown'),
                    'views': video.get('viewCount', {}).get('short', 'N/A'),
                    'url': video['link'],
                    'source': 'youtube'
                })
            
            return formatted
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    async def get_audio_stream(self, video_id: str, quality: str = "high"):
        """Get audio stream with multiple quality options"""
        cache_key = f"{video_id}_{quality}"
        
        # Check cache
        cache_file = CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists():
            async with aiofiles.open(cache_file, 'r') as f:
                cached = json.loads(await f.read())
                if datetime.now().timestamp() - cached['timestamp'] < 3600:  # 1 hour cache
                    return cached['url']
        
        # Get fresh URL
        format_map = {
            "low": "worstaudio/worst",
            "medium": "bestaudio[abr<=128]/best",
            "high": "bestaudio[abr<=192]/best",
            "premium": "bestaudio[abr<=320]/best"
        }
        
        ydl_opts = self.ydl_opts.copy()
        ydl_opts['format'] = format_map.get(quality, "bestaudio/best")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
                
                # Get direct URL
                if 'url' in info:
                    audio_url = info['url']
                elif 'formats' in info:
                    # Find best audio format
                    audio_formats = [f for f in info['formats'] 
                                   if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                    if audio_formats:
                        best = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
                        audio_url = best['url']
                    else:
                        raise Exception("No audio formats found")
                else:
                    raise Exception("No stream URL found")
                
                # Cache the URL
                cache_data = {
                    'url': audio_url,
                    'timestamp': datetime.now().timestamp(),
                    'quality': quality
                }
                async with aiofiles.open(cache_file, 'w') as f:
                    await f.write(json.dumps(cache_data))
                
                return audio_url
                
        except Exception as e:
            logger.error(f"Stream error: {e}")
            raise
    
    async def download_audio(self, video_id: str, background: bool = False):
        """Download audio with progress tracking"""
        file_path = MUSIC_DIR / f"{video_id}.mp3"
        
        if file_path.exists():
            return str(file_path)
        
        # Create a lock for this video_id
        if video_id in self.processing:
            while self.processing[video_id]:
                await asyncio.sleep(1)
            if file_path.exists():
                return str(file_path)
        
        self.processing[video_id] = True
        progress_file = CACHE_DIR / f"{video_id}_progress.json"
        
        try:
            def download_task():
                with yt_dlp.YoutubeDL({
                    **self.ydl_opts,
                    'progress_hooks': [lambda d: self._progress_hook(d, str(progress_file))]
                }) as ydl:
                    ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            
            if background:
                threading.Thread(target=download_task).start()
                return "downloading"
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(executor, download_task)
                return str(file_path)
                
        finally:
            self.processing[video_id] = False
            if progress_file.exists():
                progress_file.unlink()
    
    async def get_lyrics(self, title: str, artist: str = ""):
        """Fetch lyrics for a song"""
        try:
            async with aiohttp.ClientSession() as session:
                # Try multiple lyric sources
                sources = [
                    f"https://api.lyrics.ovh/v1/{artist}/{title}",
                    f"https://some-random-api.com/lyrics?title={title}"
                ]
                
                for url in sources:
                    try:
                        async with session.get(url, timeout=5) as response:
                            if response.status == 200:
                                data = await response.json()
                                return data.get('lyrics', 'Lyrics not found')
                    except:
                        continue
                
                return "Lyrics not available"
        except:
            return "Lyrics not available"
    
    def _progress_hook(self, d, progress_file):
        """Update download progress"""
        if d['status'] == 'downloading':
            progress = {
                'status': 'downloading',
                'downloaded': d.get('downloaded_bytes', 0),
                'total': d.get('total_bytes', 0),
                'speed': d.get('speed', 0),
                'eta': d.get('eta', 0),
                'timestamp': datetime.now().timestamp()
            }
            try:
                with open(progress_file, 'w') as f:
                    json.dump(progress, f)
            except:
                pass
    
    def _format_duration(self, duration_str: str):
        """Format duration string"""
        if not duration_str or duration_str == "0:00":
            return "0:00"
        
        if ":" in duration_str:
            parts = duration_str.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            elif len(parts) == 2:
                minutes, seconds = parts
                return f"{int(minutes):02d}:{int(seconds):02d}"
        
        return duration_str
    
    def _duration_to_seconds(self, duration_str: str):
        """Convert duration to seconds"""
        if not duration_str:
            return 0
        
        try:
            parts = list(map(int, duration_str.split(":")))
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
            else:
                return int(duration_str)
        except:
            return 0
    
    def _get_best_thumbnail(self, thumbnails):
        """Get the best quality thumbnail"""
        if not thumbnails:
            return "https://via.placeholder.com/480x360"
        
        # Prefer higher resolution
        for quality in ['maxresdefault', 'sddefault', 'hqdefault', 'mqdefault']:
            for thumb in thumbnails:
                if quality in thumb['url']:
                    return thumb['url']
        
        return thumbnails[0]['url']

# Initialize processor
audio_processor = PremiumAudioProcessor()

# Routes
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = 15,
    type: str = "video"
):
    """Enhanced search with filters"""
    results = await audio_processor.search_videos(q, limit)
    return {
        "success": True,
        "query": q,
        "results": results,
        "count": len(results)
    }

@app.get("/api/stream/{video_id}")
async def stream_audio(
    video_id: str,
    quality: str = "high",
    seek: float = 0.0
):
    """Stream audio with seek support"""
    try:
        audio_url = await audio_processor.get_audio_stream(video_id, quality)
        
        headers = {}
        if seek > 0:
            headers['Range'] = f'bytes={int(seek)}-'
        
        async def stream_generator():
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url, headers=headers) as response:
                    async for chunk in response.content.iter_chunked(8192):
                        yield chunk
        
        return StreamingResponse(
            stream_generator(),
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Type": "audio/mpeg",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except Exception as e:
        logger.error(f"Stream error for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/info/{video_id}")
async def get_video_info(video_id: str):
    """Get detailed video information"""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
            
            return {
                "success": True,
                "id": video_id,
                "title": info.get('title', 'Unknown'),
                "duration": info.get('duration', 0),
                "duration_formatted": audio_processor._format_duration(str(info.get('duration', 0))),
                "thumbnail": info.get('thumbnail', ''),
                "channel": info.get('channel', 'Unknown'),
                "description": info.get('description', '')[:200] + '...',
                "views": info.get('view_count', 0),
                "upload_date": info.get('upload_date', ''),
                "categories": info.get('categories', []),
                "tags": info.get('tags', [])[:10]
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/lyrics")
async def get_lyrics(title: str, artist: str = ""):
    """Get lyrics for a song"""
    lyrics = await audio_processor.get_lyrics(title, artist)
    return {"success": True, "lyrics": lyrics}

@app.get("/api/download/{video_id}")
async def download_audio(video_id: str, background: bool = False):
    """Download audio file"""
    try:
        result = await audio_processor.download_audio(video_id, background)
        
        if result == "downloading":
            return {"success": True, "status": "downloading", "message": "Download started in background"}
        else:
            if Path(result).exists():
                return FileResponse(
                    result,
                    media_type="audio/mpeg",
                    filename=f"{video_id}.mp3"
                )
            else:
                raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/progress/{video_id}")
async def get_download_progress(video_id: str):
    """Get download progress"""
    progress_file = CACHE_DIR / f"{video_id}_progress.json"
    if progress_file.exists():
        async with aiofiles.open(progress_file, 'r') as f:
            return json.loads(await f.read())
    return {"status": "unknown"}

@app.get("/api/playlist")
async def get_playlist():
    """Get all downloaded songs"""
    playlist = []
    for file in MUSIC_DIR.glob("*.mp3"):
        stat = file.stat()
        playlist.append({
            "id": file.stem,
            "title": file.stem.replace('_', ' '),
            "file": f"/static/music/{file.name}",
            "size": stat.st_size,
            "modified": stat.st_mtime
        })
    
    return {
        "success": True,
        "playlist": sorted(playlist, key=lambda x: x['modified'], reverse=True),
        "total": len(playlist)
    }

@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    music_files = list(MUSIC_DIR.glob("*"))
    cache_files = list(CACHE_DIR.glob("*"))
    
    total_music_size = sum(f.stat().st_size for f in music_files)
    total_cache_size = sum(f.stat().st_size for f in cache_files)
    
    return {
        "music_files": len(music_files),
        "cache_files": len(cache_files),
        "total_music_size": total_music_size,
        "total_cache_size": total_cache_size,
        "uptime": datetime.now().isoformat()
    }

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        workers=2,
        access_log=True
    )