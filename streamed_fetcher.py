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
    """Uses stealth tactics and interaction to force the stream to reveal itself."""
    page = await context.new_page()
    m3u8_link = None

    # Listen for the hidden stream link in the background traffic
    def handle_request(request):
        nonlocal m3u8_link
        url = request.url.lower()
        if ".m3u8" in url and ("strmd" in url or "secure" in url or "playlist" in url):
            if not m3u8_link: # Capture the first valid master playlist
                m3u8_link = request.url

    page.on("request", handle_request)

    try:
        # 1. Set a realistic viewport
        await page.set_viewport_size({"width": 1280, "height": 720})
        
        # 2. Navigate and wait for the "Play" button/overlay
        print(f"      Navigating to: {embed_url}")
        await page.goto(embed_url, wait_until="domcontentloaded", timeout=45000)
        
        # 3. Forced Interaction: Many players won't load the m3u8 until a click happens
        # We wait a few seconds, then click the center of the screen
        await asyncio.sleep(5)
        print("      Simulating User Interaction (Clicking Player)...")
        await page.mouse.click(640, 360) 
        
        # 4. Wait for the handshake to complete
        await asyncio.sleep(10) 
    except Exception as e:
        print(f"      Status: Timeout or Page Error (Continuing...)")
    finally:
        await page.close()
    
    return m3u8_link

async def main():
    async with async_playwright() as p:
        # Launching with arguments to disable headless tell-tales
        browser = await p.chromium.launch(headless=True, args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox'
        ])
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York"
        )

        print("--- Starting Stealth Playwright Resolver ---")
        
        # Fetch initial match data
        try:
            response = await context.request.get(f"{RAW_JSON_URL}?t={int(datetime.now().timestamp())}")
            matches = await response.json()
        except Exception as e:
            print(f"❌ Failed to fetch live.json: {e}")
            return

        m3u_content = ["#EXTM3U", ""]
        count = 0

        for match in matches:
            title = match.get('title', 'Live Match')
            category = match.get('category', 'Sports').replace('-', ' ').title()
            poster = match.get('poster', '')
            if poster.startswith('/'): poster = f"https://streamed.su{poster}"

            for source in match.get('sources', []):
                provider = source.get('source')
                sid = source.get('id')
                
                print(f"Resolving: {title} ({provider.upper()})...")
                
                # Get the player page link from API
                api_url = f"{STREAM_API_BASE}/{provider}/{sid}"
                try:
                    api_resp = await context.request.get(f"{api_url}?t={int(datetime.now().timestamp())}")
                    streams = await api_resp.json()
                    
                    if streams and len(streams) > 0:
                        embed_url = streams[0].get('embedUrl')
                        if embed_url:
                            if embed_url.startswith('//'): embed_url = 'https:' + embed_url
                            
                            # Perform the deep resolve
                            direct_link = await get_m3u8_from_page(context, embed_url)
                            
                            if direct_link:
                                print(f"      ✅ Link Caught: {direct_link[:60]}...")
                                m3u_content.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="{category}",{title} ({provider.upper()})')
                                m3u_content.append(direct_link)
                                count += 1
                                break
                except:
                    continue

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        print(f"\n✅ Finished: Created playlist with {count} playable links.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
