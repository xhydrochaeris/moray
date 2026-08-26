import asyncio
import nodriver as uc

from pathlib import Path

import re, subprocess, argparse
from random import randint

def sanitize_filename(name: str) -> str:
    # Replace Windows/Unix illegal characters and control chars with underscore
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)

    return name + '_' + str(randint(0, 999999)) # Random trailing number to avoid filename collisions

intercept_js = """
window.captured_session = null;

// 1. Hijack Fetch API
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const response = await originalFetch.apply(this, args);
    const url = args[0]?.url || args[0];
    if (url && url.includes('/api/playback/v2/session')) {
        const data = await response.clone().json();
        window.captured_session = data;
    }
    return response;
};

// 2. Hijack XMLHttpRequest (in case they use old-school AJAX)
const originalOpen = XMLHttpRequest.prototype.open;
const originalSend = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.open = function(method, url) {
    this._url = url;
    return originalOpen.apply(this, arguments);
};
XMLHttpRequest.prototype.send = function() {
    this.addEventListener('load', function() {
        if (this._url && this._url.includes('/api/playback/v2/session')) {
            try {
                window.captured_session = JSON.parse(this.responseText);
            } catch(e) {}
        }
    });
    return originalSend.apply(this, arguments);
};

// 3. Hijack JS popups so they don't block the thread
window.captured_alert = null;
const originalAlert = window.alert;
window.alert = function(msg) { window.captured_alert = msg; };
const originalConfirm = window.confirm;
window.confirm = function(msg) { window.captured_alert = msg; return false; };
const originalPrompt = window.prompt;
window.prompt = function(msg) { window.captured_alert = msg; return null; };
"""

mute_js = """
// 1. Mute any audio/video elements that might already exist
document.querySelectorAll('audio, video').forEach(m => { m.muted = true; m.volume = 0; });

// 2. Hijack the native play() function to force mute on all future plays
const originalPlay = HTMLMediaElement.prototype.play;
HTMLMediaElement.prototype.play = function() {
    this.muted = true;
    this.volume = 0.0;
    return originalPlay.apply(this, arguments);
};
"""

async def wait_for_element(parent, selector, timeout=20):
    for _ in range(timeout * 2):
        el = await parent.query_selector(selector)
        if el:
            return el
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Could not find element: {selector}")

async def get_text(el):
    if not el:
        return None
    return await el.apply("(el) => el.innerText")

async def parse_cdp_dict(res):
    if isinstance(res, (list, tuple)) and len(res) > 0 and isinstance(res[0], (list, tuple)):
        return {item[0]: item[1].get('value') for item in res}
    return res

async def main():
    parser = argparse.ArgumentParser(description="Rip m3u8 streams from evilenlucifervk.")
    parser.add_argument("-a", "--auth", action="store_true")
    parser.add_argument("urls", nargs="+", help="One or more URLs to process")
    args = parser.parse_args()

    browser = await uc.start()

    if args.auth:
        await browser.get("https://evilenlucifervk.com")
        print("\n" + "="*50)
        print("BROWSER PAUSED FOR AUTHENTICATION")
        print("Please log in via the browser window.")
        print("Press Enter in this terminal when you are done.")
        print("="*50 + "\n")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input)

    try:
        for url in args.urls:
            tab = await browser.get(url)
            await asyncio.sleep(0.5)

            # Wait for metric card and extract text
            metric_element = await wait_for_element(tab, ".artist-metric-card--releases .artist-metric-value", timeout=20)
            expected_count = int(await get_text(metric_element))

            album_cards = []
            for _ in range(60):  # Try for up to 30 seconds
                album_cards = await tab.query_selector_all("div.album-card")
                if len(album_cards) >= expected_count:
                    break
                await asyncio.sleep(0.5)

            artist_name_el = await tab.query_selector("#artist-name")
            artist_name = await get_text(artist_name_el)

            print(f"Artist: {artist_name}")
            print(f"Expecting {expected_count} releases")
            print(f"Total releases found: {len(album_cards)}")

            artist_dir = Path(sanitize_filename(artist_name))
            try:
                artist_dir.mkdir()
            except FileExistsError:
                print(f"Directory '{artist_dir}' already exists.")
                return
            except PermissionError:
                print(f"Permission denied: Unable to create '{artist_dir}'.")
                return
            except Exception as e:
                print(f"An error occurred: {e}")
                return

            await tab.evaluate(intercept_js)
            await tab.evaluate(mute_js)
            print("Network interceptors injected.")

            for index, card in enumerate(album_cards):
                title_el = await card.query_selector(".public-album-title")
                title = await get_text(title_el)

                subtitle_els = await card.query_selector_all(".public-album-subtitle")
                subtitle = await get_text(subtitle_els[0]) if subtitle_els else None

                badge_els = await card.query_selector_all(".public-album-badges span")
                date = await get_text(badge_els[0]) if badge_els else "UNKNOWN"

                folder_name = f"[{date}] {title} ({subtitle})" if subtitle else f"[{date}] {title}"
                folder_name = sanitize_filename(folder_name)
                print("\n" + folder_name)
                alb_dir = artist_dir / folder_name
                try:
                    alb_dir.mkdir()
                except FileExistsError:
                    print(f"Directory '{alb_dir}' already exists.")
                    return
                except PermissionError:
                    print(f"Permission denied: Unable to create '{alb_dir}'.")
                    return
                except Exception as e:
                    print(f"An error occurred: {e}")
                    return

                summary_elements = await card.query_selector_all("details.public-track-details:not([open])")
                if summary_elements:
                    await summary_elements[0].click()
                    await asyncio.sleep(0.2)

                # CSS :has() is fully supported in modern Chrome
                track_buttons = await card.query_selector_all("button:has(span.track-item__num)")

                i = 1
                for btn in track_buttons:
                    # Use apply to check disabled state
                    if await btn.apply("(el) => el.disabled"):
                        continue

                    track_num_el = await btn.query_selector(".track-item__num")
                    track_num = await get_text(track_num_el)

                    track_name_el = await btn.query_selector(".track-item__title .font-medium")
                    track_name = await get_text(track_name_el)

                    name2_els = await btn.query_selector_all("div[class*='mt-0.5']")
                    track_name2 = await get_text(name2_els[0]) if name2_els else None

                    final_name = track_name2 if track_name2 else track_name
                    filename = sanitize_filename(f"[{i}]{track_num}. {final_name}") + ".mp3"

                    print(f"  {filename}")
                    try:
                        await btn.click()
                    except:
                        await btn.scroll_into_view()
                        await tab.evaluate("window.scrollBy(0, -300);")
                        await btn.click()

                    session_data = None
                    for _ in range(10):
                        res = await tab.evaluate("window.captured_session")
                        if isinstance(res, (list, tuple)):
                            res = await parse_cdp_dict(res)
                        if res:
                            session_data = res
                            break
                        await asyncio.sleep(0.5)

                    if not session_data:
                        print("  -> Failed to capture session JSON! Skipping.")
                        continue

                    await tab.evaluate("window.captured_session = null;")

                    stream_url = "https://evilenlucifervk.com" + session_data['stream_url']
                    request_id = session_data['x-request-id']

                    print(f"  Captured Session! URL: {stream_url}")

                    cookies = await browser.cookies.get_all()
                    cookie_str = "; ".join([f"{c.name}={c.value}" for c in cookies])
                    res_ua = await tab.evaluate("navigator.userAgent")
                    user_agent = await parse_cdp_dict(res) if isinstance(res_ua, (list, tuple)) else res_ua

                    ffmpeg_cmd = [
                        "ffmpeg",
                        "-y",
                        "-headers", f"Cookie: {cookie_str}\r\nUser-Agent: {user_agent}\r\nx-request-id: {request_id}\r\n",
                        "-i", stream_url,
                        "-c", "copy",
                        str(alb_dir / filename)
                    ]

                    print(f"  Starting ffmpeg download...")
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

                    if result.returncode == 0:
                        print("  Download complete!")
                    else:
                        print(f"  ffmpeg failed! Error:\n{result.stderr[-500:]}")
                        (alb_dir / filename).unlink()
                    i += 1

            print("------------------------")
    finally:
        browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
