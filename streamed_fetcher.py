import asyncio
from playwright.async_api import async_playwright
import json
import os
from datetime import datetime

# Configuration
RAW_JSON_URL = "https://raw.githubusercontent.com/BuddyChewChew/sports/refs/heads/main/live.json"
STREAM_API_BASE = "https://streamed.su/api/stream"
OUTPUT_FILE = 'streamed.m3u'

async def get_m3u8_from_page(context, embed_url):
    """Intercepts the specific strmd.top master playlist."""
    page = await context.new_page()
    m3u8_link = None

    # This is your 'Network' tab automation
    def handle_request(request):
        nonlocal m3u8_link
        url = request.url
        # Target the exact domain and file type from your screenshot
        if ".m3u8" in url and "strmd.top" in url:
            # We want the playlist, not the individual TS segments
            if "playlist.m3u8" in url:
                m3u8_link = url

    page.on("request", handle_request)

    try:
        # Bypass the 'abort-on-property-read' traps you found in DevTools
        await page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")
        
        await page.set_viewport_size({"width": 1280, "height": 720})
        print(f"      Navigating to: {embed_url}")
        
        # Go to the player page
        await page.goto(embed_url, wait_until="load", timeout=60000)
        
        # Wait for the player to initialize and click to trigger the stream
        await asyncio.sleep(6)
        await page.mouse.click(640, 360) 
        
        # Wait for the network request to appear (like in your screenshot)
        await asyncio.sleep(12) 
    except Exception as e:
        print(f"      Error probing page: {e}")
    finally:
        await page.close()
    
    return m3u8_link

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        print("--- Resolving Links from strmd.top ---")
        
        # Fetch the live matches
        response = await context.request.get(f"{RAW_JSON_URL}?t={int(datetime.now().timestamp())}")
        matches = await response.json()

        m3u_content = ["#EXTM3U", ""]
        count = 0

        for match in matches:
            title = match.get('title', 'Match')
            category = match.get('category', 'Sports').title()
            poster = match.get('poster', '')
            if poster.startswith('/'): poster = f"https://streamed.su{poster}"

            for source in match.get('sources', []):
                provider = source.get('source')
                sid = source.get('id')
                
                print(f"Checking: {title} ({provider.upper()})...")
                
                # Fetch the embed URL
                api_url = f"{STREAM_API_BASE}/{provider}/{sid}"
                try:
                    api_resp = await context.request.get(api_url)
                    streams = await api_resp.json()
                    if streams:
                        embed_url = streams[0].get('embedUrl')
                        if embed_url:
                            if embed_url.startswith('//'): embed_url = 'https:' + embed_url
                            
                            # Capture the dynamic link
                            direct_link = await get_m3u8_from_page(context, embed_url)
                            
                            if direct_link:
                                print(f"      ✅ Captured: {direct_link[:50]}...")
                                m3u_content.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="{category}",{title} ({provider.upper()})')
                                m3u_content.append(direct_link)
                                count += 1
                                break
                except:
                    continue

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        print(f"\n✅ Finished! Created playlist with {count} links.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
