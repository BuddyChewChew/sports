import requests
import zstandard as zstd
import io
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import datetime
import sys

# --- 1.1. IstPlay: Error-tolerant decompression function ---
def decompress_content_istplay(response):
    try:
        if response.headers.get("content-encoding") == "zstd":
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(io.BytesIO(response.content)) as reader:
                return reader.read()
        else:
            return response.content
    except zstd.ZstdError:
        return response.content

# --- 1.2. IstPlay: Function to fetch m3u8 link ---
def get_m3u8_istplay(stream_id, headers):
    try:
        url = f"https://istplay.xyz/tv/?stream_id={stream_id}"
        response = requests.get(url, headers=headers, timeout=10)
        data = decompress_content_istplay(response)
        html_text = data.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html_text, "html.parser")
        source = soup.find("source", {"type": "application/x-mpegURL"})
        if source and source.get("src"):
            return stream_id, source["src"]
    except Exception as e:
        print(f"⚠️ Error (istplay stream_id={stream_id}): {e}", file=sys.stderr)
    return stream_id, None

# --- 1.3. IstPlay: Sport names, logos, and EPG Tags ---
DEFAULT_LOGO = "https://cdn-icons-png.flaticon.com/512/531/531313.png"
FALLBACK_EPG = "Sports.Dummy.us"

SPORT_TRANSLATION_ISTPLAY = {
    "HORSE_RACING": {"name": "HORSE RACING", "logo": "https://medya-cdn.tjk.org/haberftp/2022/ayyd12082022.jpg", "epg": "Racing.Dummy.us"},
    "FOOTBALL"    : {"name": "FOOTBALL", "logo": "https://thepfsa.co.uk/wp-content/uploads/2022/06/Playing-Football.jpg", "epg": "Football.Dummy.us"},
    "BASKETBALL"  : {"name": "BASKETBALL", "logo": "https://minio.yalispor.com.tr/sneakscloud/blog/basketbol-hakkinda-bilmen-gereken-kurallar_5e53ae3fdd3fc.jpg", "epg": "Basketball.Dummy.us"},
    "TENNIS"      : {"name": "TENNIS", "logo": "https://calista.com.tr/media/c2sl3pug/calista-resort-hotel-blog-tenis-banner.jpg", "epg": "Tennis.Dummy.us"},
    "ICE_HOCKEY"  : {"name": "ICE HOCKEY", "logo": "https://istanbulbbsk.org/uploads/medias/public-4b3b1703-c744-4631-8c42-8bab9be542bc.jpg", "epg": "NHL.Hockey.Dummy.us"},
    "TABLE_TENNIS": {"name": "TABLE TENNIS", "logo": "https://tossfed.gov.tr/storage/2022/03/1399486-masa-tenisinde-3-lig-2-nisan-da-baslayacak-60642719b43dd.jpg", "epg": "Sports.Dummy.us"},
    "VOLLEYBALL"  : {"name": "VOLLEYBALL", "logo": "https://www.sidasturkiye.com/images/aktiviteler/alt-aktiviteler_voleybol4.jpg", "epg": "Volleyball.Dummy.us"},
    "BADMINTON"   : {"name": "BADMINTON", "logo": "https://sporium.net/wp-content/uploads/2017/12/badminton-malatya-il-sampiyonasi-9178452_8314_o.jpg", "epg": "Sports.Dummy.us"},
    "CRICKET"     : {"name": "CRICKET", "logo": "https://storage.acerapps.io/app-1358/kriket-nedir-nasil-oynanir-kriket-kurallari-nelerdir-sporsepeti-sportsfly-spor-kutuphanesi.jpg", "epg": "Cricket.Dummy.us"},
    "HANDBALL"    : {"name": "HANDBALL", "logo": "https://image.fanatik.com.tr/i/fanatik/75/0x410/6282949745d2a051587ed23b.jpg", "epg": "Sports.Dummy.us"},
    "BASEBALL"    : {"name": "BASEBALL", "logo": "https://seyler.ekstat.com/img/max/800/d/dqOJz5N8jLORqVaA-636783298725804088.jpg", "epg": "Baseball.Dummy.us"},
    "SNOOKER"     : {"name": "SNOOKER", "logo": "https://cdn.shopify.com/s/files/1/0644/5685/1685/files/pool-table-graphic-1.jpg", "epg": "BilliardTV.Dummy.us"},
    "BILLIARDS"   : {"name": "BILLIARDS", "logo": "https://www.bilardo.org.tr/image/be2a4809f1c796e4453b45ccf0d9740c.jpg", "epg": "BilliardTV.Dummy.us"},
    "BICYCLE"     : {"name": "CYCLING", "logo": "https://www.gazetekadikoy.com.tr/Uploads/gazetekadikoy.com.tr/202204281854011-img.jpg", "epg": "Sports.Dummy.us"},
    "BOXING"      : {"name": "BOXING", "logo": "https://www.sportsmith.co/wp-content/uploads/2023/04/Thumbnail-scaled.jpg", "epg": "PPV.EVENTS.Dummy.us"},
    "AMERICAN_FOOTBALL": {"name": "AMERICAN FOOTBALL", "logo": "https://wallpaperaccess.com/full/301292.jpg", "epg": "NFL.Dummy.us"},
    "MOTORSPORT"       : {"name": "MOTORSPORT", "logo": "https://wallpapercave.com/wp/wp4034220.jpg", "epg": "Racing.Dummy.us"},
    "ESPORTS"          : {"name": "ESPORTS", "logo": "https://wallpaperaccess.com/full/438210.jpg", "epg": "Sports.Dummy.us"},
    "DARTS"            : {"name": "DARTS", "logo": "https://images.alphacoders.com/520/520864.jpg", "epg": "Darts.Dummy.us"},
    "RUGBY"            : {"name": "RUGBY", "logo": "https://wallpapercave.com/wp/wp1810625.jpg", "epg": "Rugby.Dummy.us"},
    "GOLF"             : {"name": "GOLF", "logo": "https://wallpaperaccess.com/full/1126425.jpg", "epg": "Golf.Dummy.us"},
    "FIGHT"            : {"name": "UFC/MMA", "logo": "https://wallpapercave.com/wp/wp1833446.jpg", "epg": "UFC.Fight.Pass.Dummy.us"},
    "FORMULA_1"        : {"name": "FORMULA 1", "logo": "https://wallpaperaccess.com/full/1154341.jpg", "epg": "Racing.Dummy.us"},
    "AUSTRALIAN_RULES" : {"name": "AUS RULES", "logo": "https://cdn-icons-png.flaticon.com/512/531/531313.png", "epg": "AUS.Rules.Football.Dummy.us"},
}

def main():
    print("📢 [IstPlay] Fetching stream list...")
    url_list = "https://api.istplay.xyz/stream-list-v2/?tv=tv"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://istplay.xyz",
        "Referer": "https://istplay.xyz/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    }

    try:
        response = requests.get(url_list, headers=headers, timeout=15)
        response.raise_for_status() 
        data = decompress_content_istplay(response)
        parsed = json.loads(data)
    except Exception as e:
        print(f"❌ [IstPlay] Error: {e}", file=sys.stderr)
        return

    all_events = []
    sports_data = parsed.get("sports", {})
    for sport_key, sport_category in sports_data.items():
        if not isinstance(sport_category, dict): continue
        events = sport_category.get("events", {})
        iterable = events.items() if isinstance(events, dict) else [(str(i), e) for i, e in enumerate(events)]
        for event_id, event_data in iterable:
            stream_id = event_data.get("stream_id")
            if stream_id:
                all_events.append((sport_key, event_id, event_data))

    if not all_events:
        print("ℹ️ [IstPlay] No events found.")
        return

    print(f"🔗 [IstPlay] Fetching links for {len(all_events)} events...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_event = {executor.submit(get_m3u8_istplay, ev[2]['stream_id'], headers): ev for ev in all_events}
        for future in as_completed(future_to_event):
            sport_key, event_id, event_data = future_to_event[future]
            try:
                sid, m3u8_url = future.result()
                event_data["m3u8_url"] = m3u8_url
            except Exception as e:
                print(f"⚠️ Future error: {e}", file=sys.stderr)

    # Updated M3U Header with EPG URL
    output_lines = ['#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"', '']
    found_streams_count = 0

    for sport_key, sport_category in sports_data.items():
        if not isinstance(sport_category, dict): continue
        events = sport_category.get("events", {})
        iterable = events.items() if isinstance(events, dict) else [(str(i), e) for i, e in enumerate(events)]

        for event_id, event_data in iterable:
            m3u8_url = event_data.get("m3u8_url")
            if not m3u8_url: continue

            league = event_data.get("league", "Unknown")
            competitors = event_data.get("competitiors", {})
            home = competitors.get("home", "").strip()
            away = competitors.get("away", "").strip()
            
            start_timestamp = event_data.get("start_time")
            start_time_str = ""
            if start_timestamp:
                try:
                    dt_object = datetime.datetime.fromtimestamp(int(start_timestamp))
                    start_time_str = f"[{dt_object.strftime('%H:%M')}] "
                except: pass

            # EPG & Logo Logic
            sport_info = SPORT_TRANSLATION_ISTPLAY.get(sport_key.upper(), {})
            display_sport = sport_info.get("name", sport_key.replace('_', ' ').upper())
            logo_url = sport_info.get("logo", DEFAULT_LOGO)
            epg_id = sport_info.get("epg", FALLBACK_EPG)

            if sport_key.upper() == "HORSE_RACING":
                display_title = f"{start_time_str}{home.upper()} ({league.upper()})"
            else:
                display_title = f"{start_time_str}{home.upper()} vs {away.upper()} ({league.upper()})"

            # Added tvg-id for EPG matching
            line = f'#EXTINF:-1 tvg-id="{epg_id}" tvg-name="{display_sport}" tvg-logo="{logo_url}" tvg-type="2" group-title="{display_sport}",{display_title}\n{m3u8_url}'
            output_lines.append(line)
            found_streams_count += 1

    with open("istplay_streams.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"💾 M3U saved ({found_streams_count} streams).")

if __name__ == "__main__":
    main()
