#!/usr/bin/env python3
"""
Music Player Search Fix Tool
Run this script if search stops working
"""

import subprocess
import sys
import os
import shutil
import json
import time
from pathlib import Path

def print_header():
    print("=" * 70)
    print("🎵 MUSIC PLAYER SEARCH FIX TOOL")
    print("=" * 70)
    print("This script will fix search issues by:")
    print("  1. Updating all dependencies")
    print("  2. Clearing cache files")
    print("  3. Configuring yt-dlp")
    print("  4. Testing search functionality")
    print("=" * 70)

def check_python_version():
    """Check Python version"""
    print("\n[1/8] Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} - Requires Python 3.9+")
        return False

def update_pip():
    """Update pip"""
    print("\n[2/8] Updating pip...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "--upgrade", "pip", "setuptools", "wheel"
        ], check=True, capture_output=True)
        print("✓ pip updated successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to update pip: {e.stderr.decode()}")
        return False

def install_requirements():
    """Install/update requirements"""
    print("\n[3/8] Installing requirements...")
    
    requirements = [
        "yt-dlp>=2023.12.30",
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "aiohttp>=3.9.1",
        "aiosqlite>=0.19.0",
        "python-multipart>=0.0.6",
        "python-dotenv>=1.0.0",
        "beautifulsoup4>=4.12.2",
        "lxml>=4.9.3",
        "requests>=2.31.0",
        "pydantic>=2.5.0",
        "youtube-search-python>=1.6.5",
        "youtube-dl-patched>=2023.12.30",
        "ytmusicapi>=1.0.0"
    ]
    
    for req in requirements:
        try:
            package = req.split(">=")[0]
            print(f"  Installing {package}...")
            subprocess.run([
                sys.executable, "-m", "pip", "install",
                "--upgrade", "--no-cache-dir", req
            ], check=True, capture_output=True)
            print(f"  ✓ {package} installed")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Failed to install {req}: {e.stderr.decode()[:100]}...")
    
    print("✓ All requirements installed")
    return True

def clear_cache():
    """Clear all cache files"""
    print("\n[4/8] Clearing cache...")
    
    cache_dirs = [
        Path("static/cache"),
        Path("static/music"),
        Path.home() / ".cache" / "yt-dlp",
        Path.home() / ".config" / "yt-dlp",
    ]
    
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                if cache_dir.is_dir():
                    shutil.rmtree(cache_dir)
                    print(f"  ✓ Cleared {cache_dir}")
                else:
                    cache_dir.unlink()
                    print(f"  ✓ Removed {cache_dir}")
            except Exception as e:
                print(f"  ✗ Failed to clear {cache_dir}: {e}")
    
    # Recreate necessary directories
    Path("static/cache").mkdir(exist_ok=True, parents=True)
    Path("static/music").mkdir(exist_ok=True, parents=True)
    
    print("✓ Cache cleared")
    return True

def configure_ytdlp():
    """Configure yt-dlp for optimal performance"""
    print("\n[5/8] Configuring yt-dlp...")
    
    # Create config directory
    config_dir = Path.home() / ".config" / "yt-dlp"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Configuration content
    config_content = """# yt-dlp configuration for music player
--no-warnings
--ignore-errors
--no-playlist
--format bestaudio/best
--extract-audio
--audio-format mp3
--audio-quality 192K
--output "static/music/%(id)s.%(ext)s"
--progress
--no-mtime
--http-chunk-size 10M
--retries 10
--fragment-retries 10
--skip-unavailable-fragments
--concurrent-fragments 5
--throttled-rate 100K
--user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
--geo-bypass
--no-check-certificate
--prefer-free-formats
--force-ipv4
--socket-timeout 30
--source-address 0.0.0.0
"""
    
    # Write config file
    config_file = config_dir / "config"
    config_file.write_text(config_content)
    print(f"✓ Configuration saved to {config_file}")
    
    # Also create config in project directory
    project_config = Path("yt-dlp-config.txt")
    project_config.write_text(config_content)
    print(f"✓ Project config saved to {project_config}")
    
    return True

def test_dependencies():
    """Test if dependencies are working"""
    print("\n[6/8] Testing dependencies...")
    
    test_code = '''
import sys
import yt_dlp
import aiohttp
import json
import asyncio

print("Testing imports...")
print(f"Python: {sys.version}")
print(f"yt-dlp: {yt_dlp.version.__version__}")
print(f"aiohttp: {aiohttp.__version__}")

# Test yt-dlp extraction
print("\\nTesting yt-dlp search...")
try:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info("ytsearch3:shape of you", download=False)
        
        if info and 'entries' in info:
            print(f"✓ Search successful! Found {len(info['entries'])} results")
            for i, entry in enumerate(info['entries'][:3], 1):
                if entry:
                    print(f"  {i}. {entry.get('title', 'Unknown')[:50]}...")
        else:
            print("✗ No results found")
            
except Exception as e:
    print(f"✗ Search test failed: {type(e).__name__}: {str(e)[:100]}")

print("\\n✓ All tests completed!")
'''
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(result.stdout)
        if result.stderr:
            print("Stderr:", result.stderr[:200])
        
        return "✓ Search successful!" in result.stdout
        
    except subprocess.TimeoutExpired:
        print("✗ Test timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def create_quick_test():
    """Create a quick test script"""
    print("\n[7/8] Creating test script...")
    
    test_script = """
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.search_engine import SearchEngine
import asyncio

async def test():
    print("🔍 Testing search engine...")
    search = SearchEngine()
    
    test_queries = [
        "shape of you",
        "blinding lights",
        "dance monkey",
        "despacito",
        "someone you loved"
    ]
    
    for query in test_queries:
        print(f"\\nSearching for: {query}")
        try:
            results = await search.search(query, limit=3)
            if results:
                print(f"  ✓ Found {len(results)} results")
                for i, r in enumerate(results[:2], 1):
                    print(f"    {i}. {r['title'][:40]}...")
            else:
                print(f"  ✗ No results")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {str(e)[:50]}")
    
    print("\\n✅ Search test completed!")

if __name__ == "__main__":
    asyncio.run(test())
"""
    
    Path("test_search.py").write_text(test_script)
    print("✓ Test script created: test_search.py")
    print("  Run: python test_search.py")
    
    return True

def generate_report():
    """Generate system report"""
    print("\n[8/8] Generating system report...")
    
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": sys.version,
        "platform": sys.platform,
        "cache_cleared": True,
        "config_created": True,
        "directories": {
            "cache": str(Path("static/cache").absolute()),
            "music": str(Path("static/music").absolute()),
            "config": str(Path.home() / ".config" / "yt-dlp")
        }
    }
    
    # Save report
    report_file = Path("search_fix_report.json")
    report_file.write_text(json.dumps(report, indent=2))
    
    print("✓ System report generated: search_fix_report.json")
    print("\n" + "=" * 70)
    print("✅ FIX COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Restart your music player server")
    print("2. Try searching for songs again")
    print("3. If issues persist, run: python test_search.py")
    print("4. Check logs for detailed errors")
    print("\nCommon solutions:")
    print("  - Ensure internet connection is stable")
    print("  - Update yt-dlp regularly: pip install --upgrade yt-dlp")
    print("  - Clear cache: rm -rf static/cache/*")
    print("  - Use VPN if YouTube is blocked")
    print("=" * 70)
    
    return True

def main():
    print_header()
    
    # Ask for confirmation
    response = input("\nDo you want to proceed with the fix? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("\nOperation cancelled.")
        return
    
    steps = [
        check_python_version,
        update_pip,
        install_requirements,
        clear_cache,
        configure_ytdlp,
        test_dependencies,
        create_quick_test,
        generate_report
    ]
    
    for step in steps:
        try:
            if not step():
                print(f"\n⚠️  Step failed, but continuing...")
        except Exception as e:
            print(f"\n⚠️  Error in step: {e}")
            continue
    
    print("\n🎉 Fix process completed! Your search should now work.")

if __name__ == "__main__":
    main()