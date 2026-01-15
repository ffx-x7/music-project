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
import hashlib
import re
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict, Optional
import urllib.parse

# Enhanced imports
import html
from yt_dlp import YoutubeDL
import time
import random

logger = logging.getLogger(__name__)

app = FastAPI(title="Premium Music Player", version="3.0")

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

class SearchEngine:
    """Multiple search strategies for 100% reliability"""
    
    def __init__(self):
        self.session = None
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        ]
    
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def search_youtube_direct(self, query: str, limit: int = 15) -> List[Dict]:
        """Method 1: Direct YouTube search using yt-dlp"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'force_generic_extractor': False,
            }
            
            # Create search URL
            search_query = urllib.parse.quote(query)
            search_url = f"ytsearch{limit}:{search_query}"
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
                
                if not info or 'entries' not in info:
                    return []
                
                results = []
                for entry in info['entries'][:limit]:
                    if not entry:
                        continue
                    
                    results.append({
                        'id': entry.get('id', ''),
                        'title': entry.get('title', 'Unknown'),
                        'duration': self.format_duration(entry.get('duration', 0)),
                        'duration_seconds': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg"),
                        'channel': entry.get('uploader', 'Unknown'),
                        'views': str(entry.get('view_count', 0)),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                        'source': 'youtube'
                    })
                
                return results
        except Exception as e:
            logger.error(f"Direct search error: {e}")
            return []
    
    async def search_ytdlp_api(self, query: str, limit: int = 15) -> List[Dict]:
        """Method 2: yt-dlp with custom extractor"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'skip_download': True,
                'force_generic_extractor': True,
            }
            
            # Search using ytsearch protocol
            with YoutubeDL(ydl_opts) as ydl:
                search_results = ydl.extract_info(
                    f"ytsearch{limit}:{query}",
                    download=False
                )
                
                if not search_results or 'entries' not in search_results:
                    return []
                
                results = []
                for entry in search_results['entries'][:limit]:
                    if not entry:
                        continue
                    
                    # Get best thumbnail
                    thumbnail = entry.get('thumbnail', '')
                    if not thumbnail and entry.get('id'):
                        thumbnail = f"https://i.ytimg.com/vi/{entry['id']}/hqdefault.jpg"
                    
                    results.append({
                        'id': entry.get('id', ''),
                        'title': html.unescape(entry.get('title', 'Unknown')),
                        'duration': self.format_duration(entry.get('duration', 0)),
                        'duration_seconds': entry.get('duration', 0),
                        'thumbnail': thumbnail,
                        'channel': html.unescape(entry.get('uploader', 'Unknown')),
                        'views': self.format_views(entry.get('view_count', 0)),
                        'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                        'source': 'youtube'
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"yt-dlp API search error: {e}")
            return []
    
    async def search_invidious(self, query: str, limit: int = 15) -> List[Dict]:
        """Method 3: Use Invidious API (YouTube alternative)"""
        try:
            invidious_instances = [
                "https://invidious.fdn.fr",
                "https://invidious.weblibre.org",
                "https://invidious.privacydev.net",
                "https://yewtu.be"
            ]
            
            session = await self.get_session()
            
            for instance in invidious_instances:
                try:
                    url = f"{instance}/api/v1/search"
                    params = {
                        'q': query,
                        'type': 'video',
                        'fields': 'videoId,title,published,author,authorId,lengthSeconds,viewCount,thumbnail',
                        'page': 1
                    }
                    
                    async with session.get(url, params=params, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            results = []
                            for item in data[:limit]:
                                results.append({
                                    'id': item.get('videoId', ''),
                                    'title': html.unescape(item.get('title', 'Unknown')),
                                    'duration': self.format_duration(item.get('lengthSeconds', 0)),
                                    'duration_seconds': item.get('lengthSeconds', 0),
                                    'thumbnail': item.get('thumbnail', f"https://i.ytimg.com/vi/{item.get('videoId')}/hqdefault.jpg"),
                                    'channel': html.unescape(item.get('author', 'Unknown')),
                                    'views': self.format_views(item.get('viewCount', 0)),
                                    'url': f"https://www.youtube.com/watch?v={item.get('videoId')}",
                                    'source': 'invidious'
                                })
                            
                            return results
                except Exception as e:
                    logger.error(f"Invidious instance {instance} failed: {e}")
                    continue
            
            return []
        except Exception as e:
            logger.error(f"Invidious search error: {e}")
            return []
    
    async def search_piped(self, query: str, limit: int = 15) -> List[Dict]:
        """Method 4: Use Piped API"""
        try:
            piped_instances = [
                "https://pipedapi.kavin.rocks",
                "https://pipedapi.moomoo.me",
                "https://pipedapi-libre.kavin.rocks"
            ]
            
            session = await self.get_session()
            
            for instance in piped_instances:
                try:
                    url = f"{instance}/search"
                    params = {
                        'q': query,
                        'filter': 'videos'
                    }
                    
                    headers = {
                        'User-Agent': random.choice(self.user_agents)
                    }
                    
                    async with session.get(url, params=params, headers=headers, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            results = []
                            for item in data.get('items', [])[:limit]:
                                if not item.get('url'):
                                    continue
                                    
                                # Extract video ID from URL
                                video_id = item['url'].split('=')[-1] if '=' in item['url'] else item['url'].split('/')[-1]
                                
                                results.append({
                                    'id': video_id,
                                    'title': html.unescape(item.get('title', 'Unknown')),
                                    'duration': self.format_duration(item.get('duration', 0)),
                                    'duration_seconds': item.get('duration', 0),
                                    'thumbnail': item.get('thumbnail', f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"),
                                    'channel': html.unescape(item.get('uploaderName', 'Unknown')),
                                    'views': self.format_views(item.get('views', 0)),
                                    'url': f"https://www.youtube.com/watch?v={video_id}",
                                    'source': 'piped'
                                })
                            
                            return results
                except Exception as e:
                    logger.error(f"Piped instance {instance} failed: {e}")
                    continue
            
            return []
        except Exception as e:
            logger.error(f"Piped search error: {e}")
            return []
    
    async def search_scraping(self, query: str, limit: int = 15) -> List[Dict]:
        """Method 5: Direct HTML scraping (last resort)"""
        try:
            session = await self.get_session()
            search_url = "https://www.youtube.com/results"
            params = {
                'search_query': query
            }
            
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
            
            async with session.get(search_url, params=params, headers=headers, timeout=15) as response:
                if response.status != 200:
                    return []
                
                html_content = await response.text()
                
                # Extract JSON data from ytInitialData
                import re
                pattern = r'var ytInitialData = ({.*?});</script>'
                match = re.search(pattern, html_content, re.DOTALL)
                
                if match:
                    try:
                        data = json.loads(match.group(1))
                        results = self.extract_from_ytinitialdata(data)
                        return results[:limit]
                    except json.JSONDecodeError:
                        pass
                
                # Alternative: Extract from ytInitialPlayerResponse
                pattern2 = r'var ytInitialPlayerResponse = ({.*?});</script>'
                match2 = re.search(pattern2, html_content, re.DOTALL)
                
                if match2:
                    try:
                        data = json.loads(match2.group(1))
                        results = self.extract_from_player_response(data)
                        return results[:limit]
                    except json.JSONDecodeError:
                        pass
                
                # Fallback: Search for video links
                video_ids = re.findall(r'"/watch\?v=([a-zA-Z0-9_-]{11})"', html_content)
                unique_ids = list(dict.fromkeys(video_ids))[:limit]
                
                results = []
                for video_id in unique_ids:
                    results.append({
                        'id': video_id,
                        'title': f"Video {video_id}",
                        'duration': '0:00',
                        'duration_seconds': 0,
                        'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                        'channel': 'Unknown',
                        'views': '0',
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'source': 'scraping'
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Scraping error: {e}")
            return []
    
    def extract_from_ytinitialdata(self, data: Dict) -> List[Dict]:
        """Extract video data from ytInitialData"""
        results = []
        
        try:
            # Navigate through the complex JSON structure
            contents = data.get('contents', {})
            two_column = contents.get('twoColumnSearchResultsRenderer', {})
            primary_contents = two_column.get('primaryContents', {})
            section_list = primary_contents.get('sectionListRenderer', {})
            
            for section in section_list.get('contents', []):
                item_section = section.get('itemSectionRenderer', {})
                for content in item_section.get('contents', []):
                    if 'videoRenderer' in content:
                        video = content['videoRenderer']
                        
                        video_id = video.get('videoId', '')
                        title = video.get('title', {}).get('runs', [{}])[0].get('text', 'Unknown')
                        channel = video.get('ownerText', {}).get('runs', [{}])[0].get('text', 'Unknown')
                        
                        # Duration
                        duration_text = video.get('lengthText', {}).get('simpleText', '0:00')
                        
                        # Views
                        view_count = video.get('viewCountText', {}).get('simpleText', '0')
                        
                        # Thumbnail
                        thumbnails = video.get('thumbnail', {}).get('thumbnails', [])
                        thumbnail = thumbnails[-1]['url'] if thumbnails else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                        
                        results.append({
                            'id': video_id,
                            'title': html.unescape(title),
                            'duration': duration_text,
                            'duration_seconds': self.parse_duration(duration_text),
                            'thumbnail': thumbnail,
                            'channel': html.unescape(channel),
                            'views': view_count,
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'source': 'youtube'
                        })
        except Exception as e:
            logger.error(f"Extraction from ytInitialData failed: {e}")
        
        return results
    
    def extract_from_player_response(self, data: Dict) -> List[Dict]:
        """Extract video data from player response"""
        results = []
        
        try:
            video_details = data.get('videoDetails', {})
            video_id = video_details.get('videoId', '')
            
            if video_id:
                results.append({
                    'id': video_id,
                    'title': html.unescape(video_details.get('title', 'Unknown')),
                    'duration': self.format_duration(int(video_details.get('lengthSeconds', 0))),
                    'duration_seconds': int(video_details.get('lengthSeconds', 0)),
                    'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    'channel': html.unescape(video_details.get('author', 'Unknown')),
                    'views': video_details.get('viewCount', '0'),
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'source': 'youtube'
                })
        except Exception as e:
            logger.error(f"Extraction from player response failed: {e}")
        
        return results
    
    async def search(self, query: str, limit: int = 15) -> List[Dict]:
        """Main search method with fallbacks"""
        if not query or len(query.strip()) < 1:
            return []
        
        logger.info(f"Searching for: {query}")
        
        # Try multiple methods in sequence
        methods = [
            self.search_ytdlp_api,
            self.search_youtube_direct,
            self.search_invidious,
            self.search_piped,
            self.search_scraping
        ]
        
        all_results = []
        seen_ids = set()
        
        for method in methods:
            try:
                logger.info(f"Trying search method: {method.__name__}")
                results = await method(query, limit)
                
                # Deduplicate and add new results
                for result in results:
                    if result['id'] and result['id'] not in seen_ids:
                        seen_ids.add(result['id'])
                        all_results.append(result)
                
                # If we got enough results, break early
                if len(all_results) >= limit:
                    break
                    
                # Small delay between methods
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Search method {method.__name__} failed: {e}")
                continue
        
        # Sort by relevance (simplified)
        if all_results:
            # Prioritize results with titles containing the query
            query_lower = query.lower()
            all_results.sort(
                key=lambda x: (
                    1 if query_lower in x['title'].lower() else 0,
                    x.get('views', 0) if isinstance(x.get('views'), (int, float)) else 0
                ),
                reverse=True
            )
        
        return all_results[:limit]
    
    def format_duration(self, seconds: int) -> str:
        """Format duration in seconds to HH:MM:SS or MM:SS"""
        if not seconds:
            return "0:00"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds"""
        try:
            parts = list(map(int, duration_str.split(':')))
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
            else:
                return 0
        except:
            return 0
    
    def format_views(self, views) -> str:
        """Format view count"""
        if isinstance(views, (int, float)):
            if views >= 1000000:
                return f"{views/1000000:.1f}M"
            elif views >= 1000:
                return f"{views/1000:.1f}K"
            else:
                return str(views)
        elif isinstance(views, str):
            return views
        else:
            return "0"

class AudioStreamer:
    """Handle audio streaming with multiple quality options"""
    
    def __init__(self):
        self.search_engine = SearchEngine()
        self.cache = {}
        self.quality_map = {
            'low': 'worstaudio/worst',
            'medium': 'bestaudio[abr<=128]/best',
            'high': 'bestaudio[abr<=192]/best',
            'premium': 'bestaudio[abr<=320]/best'
        }
    
    async def search_videos(self, query: str, limit: int = 15) -> List[Dict]:
        """Search for videos"""
        return await self.search_engine.search(query, limit)
    
    async def get_video_info(self, video_id: str) -> Optional[Dict]:
        """Get video information"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={video_id}',
                    download=False
                )
                
                if not info:
                    return None
                
                return {
                    'id': video_id,
                    'title': html.unescape(info.get('title', 'Unknown')),
                    'duration': info.get('duration', 0),
                    'duration_formatted': self.search_engine.format_duration(info.get('duration', 0)),
                    'thumbnail': info.get('thumbnail', f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'),
                    'channel': html.unescape(info.get('uploader', 'Unknown')),
                    'description': info.get('description', '')[:200],
                    'views': info.get('view_count', 0),
                    'upload_date': info.get('upload_date', ''),
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    async def get_stream_url(self, video_id: str, quality: str = 'high') -> Optional[str]:
        """Get direct stream URL"""
        try:
            cache_key = f"{video_id}_{quality}"
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if time.time() - cached['timestamp'] < 1800:  # 30 minutes
                    return cached['url']
            
            ydl_opts = {
                'format': self.quality_map.get(quality, 'bestaudio/best'),
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={video_id}',
                    download=False
                )
                
                if not info or 'url' not in info:
                    return None
                
                # Cache the URL
                self.cache[cache_key] = {
                    'url': info['url'],
                    'timestamp': time.time()
                }
                
                return info['url']
                
        except Exception as e:
            logger.error(f"Error getting stream URL: {e}")
            return None
    
    async def download_audio(self, video_id: str, quality: str = 'high') -> Optional[str]:
        """Download audio file"""
        try:
            output_file = MUSIC_DIR / f"{video_id}_{quality}.mp3"
            
            if output_file.exists():
                return str(output_file)
            
            ydl_opts = {
                'format': self.quality_map.get(quality, 'bestaudio/best'),
                'outtmpl': str(MUSIC_DIR / f"{video_id}.%(ext)s"),
                'quiet': False,
                'no_warnings': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            
            # Rename to include quality
            temp_file = MUSIC_DIR / f"{video_id}.mp3"
            if temp_file.exists():
                temp_file.rename(output_file)
            
            if output_file.exists():
                return str(output_file)
            
            return None
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None

# Initialize services
audio_streamer = AudioStreamer()

# Routes
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/player")
async def player_page(request: Request):
    return templates.TemplateResponse("player.html", {"request": request})

@app.get("/api/search")
async def search_videos(
    q: str = Query(..., min_length=1),
    limit: int = Query(15, ge=1, le=50)
):
    """Search for videos - 100% reliable"""
    try:
        results = await audio_streamer.search_videos(q, limit)
        
        if not results:
            # Try alternative search methods
            logger.info("Primary search returned no results, trying alternatives...")
            
            # Try with different query formatting
            modified_queries = [
                q,
                f"{q} official audio",
                f"{q} lyrics",
                f"{q} song",
                f"{q} music video"
            ]
            
            for modified_query in modified_queries:
                if modified_query != q:
                    results = await audio_streamer.search_videos(modified_query, limit)
                    if results:
                        break
        
        if not results:
            return JSONResponse({
                "success": False,
                "message": "No results found. Try a different search term.",
                "results": [],
                "count": 0
            })
        
        return {
            "success": True,
            "query": q,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Search API error: {e}")
        return JSONResponse({
            "success": False,
            "message": f"Search error: {str(e)}",
            "results": [],
            "count": 0
        }, status_code=500)

@app.get("/api/stream/{video_id}")
async def stream_audio(
    video_id: str,
    quality: str = Query("high"),
    seek: float = Query(0.0)
):
    """Stream audio"""
    try:
        stream_url = await audio_streamer.get_stream_url(video_id, quality)
        
        if not stream_url:
            # Fallback: Use yt-dlp to get URL
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={video_id}',
                    download=False
                )
                stream_url = info.get('url')
        
        if not stream_url:
            raise HTTPException(status_code=404, detail="Stream not available")
        
        headers = {}
        if seek > 0:
            headers['Range'] = f'bytes={int(seek)}-'
        
        async def stream_generator():
            async with aiohttp.ClientSession() as session:
                async with session.get(stream_url, headers=headers) as response:
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
        logger.error(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/info/{video_id}")
async def get_video_info(video_id: str):
    """Get video information"""
    try:
        info = await audio_streamer.get_video_info(video_id)
        
        if not info:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {"success": True, **info}
        
    except Exception as e:
        logger.error(f"Info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{video_id}")
async def download_audio(
    video_id: str,
    quality: str = Query("high")
):
    """Download audio"""
    try:
        file_path = await audio_streamer.download_audio(video_id, quality)
        
        if not file_path:
            raise HTTPException(status_code=404, detail="Download failed")
        
        return FileResponse(
            file_path,
            media_type="audio/mpeg",
            filename=f"{video_id}.mp3"
        )
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache_size": len(audio_streamer.cache),
        "search_methods": [
            "yt-dlp API",
            "Direct YouTube",
            "Invidious",
            "Piped",
            "HTML Scraping"
        ]
    }

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        workers=1,  # Single worker for yt-dlp to avoid conflicts
        access_log=True
    )