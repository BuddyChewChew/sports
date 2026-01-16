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
    """Launches a page, listens for .m3u8 requests, and returns the link."""
    page = await context.new_page()
    m3u8_link = None

    # Intercept network requests to find the secret .m3u8 link
    def handle_request(request):
        nonlocal m3u8_link
        # We look for the strmd.top master playlist
        if ".m3u8" in request.url and ("strmd.top" in request.url or "secure" in request.url):
            m3u8_link = request.url

    page.on("request", handle_request)

    try:
        print(f"      Navigating to: {embed_url}")
        # Wait for the player to actually start loading the stream
        await page.goto(embed_url, wait_until="load", timeout=30000)
        await asyncio.sleep(7) # Wait for JS to trigger the stream request
    except Exception as e:
        print(f"      Page Error: {e}")
    finally:
        await page.close()
    
    return m3u8_link

async def main():
    async with async_playwright() as p:
        # Launch browser with specific args to bypass headless detection
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        print("--- Starting Playwright Deep Scraper ---")
        
        # Correctly fetching the initial JSON
        response = await context.request.get(f"{RAW_JSON_URL}?t={int(datetime.now().timestamp())}")
        matches = await response.json()

        m3u_content = ["#EXTM3U", ""]
        count = 0

        for match in matches:
            title = match.get('title', 'Live Match')
            category = match.get('category', 'Sports').replace('-', ' ').title()
            poster = match.get('poster', '')
            if poster.startswith('/'):
                poster = f"https://streamed.su{poster}"

            for source in match.get('sources', []):
                provider = source.get('source')
                sid = source.get('id')
                
                print(f"Resolving: {title} ({provider.upper()})...")
                
                # Get the embed URL from the Stream API
                api_url = f"{STREAM_API_BASE}/{provider}/{sid}"
                api_resp = await context.request.get(f"{api_url}?t={int(datetime.now().timestamp())}")
                streams = await api_resp.json()
                
                if streams and len(streams) > 0:
                    embed_url = streams[0].get('embedUrl')
                    if embed_url:
                        if embed_url.startswith('//'):
                            embed_url = 'https:' + embed_url
                        
                        # Catch the link via network interception
                        direct_link = await get_m3u8_from_page(context, embed_url)
                        
                        if direct_link:
                            m3u_content.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="{category}",{title} ({provider.upper()})')
                            m3u_content.append(direct_link)
                            count += 1
                            print(f"      ✅ Resolved: {direct_link[:60]}...")
                            break # Only need one working source per match

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        print(f"\n✅ Finished: Created playlist with {count} playable links.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
