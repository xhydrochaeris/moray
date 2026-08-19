from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from pathlib import Path

import re, subprocess, time, argparse
from random import randint

def sanitize_filename(name: str) -> str:
    # Replace Windows/Unix illegal characters and control chars with underscore
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)

    return name + '_' + str(randint(0, 999999)) # Random trailing number to avoid filename collisions

def album_count_reached(driver):
    cards = driver.find_elements(By.CSS_SELECTOR, "div.album-card")
    if len(cards) >= expected_count:
        return cards
    return False

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rip m3u8 streams from evilenlucifervk.")
    parser.add_argument("urls", nargs="+", help="One or more URLs to process")
    args = parser.parse_args()

    driver = webdriver.Firefox()
    try:
        for url in args.urls:
            driver.get(url)

            metric_locator = (By.CSS_SELECTOR, ".artist-metric-card--releases .artist-metric-value")
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(metric_locator)
            )

            metric_element = driver.find_element(*metric_locator)
            expected_count = int(metric_element.text)

            album_cards = WebDriverWait(driver, 30).until(album_count_reached)

            artist_name = driver.find_element(By.ID, "artist-name").text

            print(f"Artist: {artist_name}")
            print(f"Expecting {expected_count} releases")
            print(f"Total releases found: {len(album_cards)}")

            artist_dir = Path(sanitize_filename(artist_name))
            try:
                artist_dir.mkdir()
            except FileExistsError:
                print(f"Directory '{artist_dir}' already exists.")
                exit(1)
            except PermissionError:
                print(f"Permission denied: Unable to create '{artist_dir}'.")
                exit(1)
            except Exception as e:
                print(f"An error occurred: {e}")
                exit(1)

            driver.execute_script(intercept_js)
            driver.execute_script(mute_js)
            print("Network interceptors injected.")

            for index, card in enumerate(album_cards):
                title = card.find_element(By.CSS_SELECTOR, ".public-album-title").text

                subtitle_els = card.find_elements(By.CSS_SELECTOR, ".public-album-subtitle")
                subtitle = subtitle_els[0].text if subtitle_els else None

                badge_els = card.find_elements(By.CSS_SELECTOR, ".public-album-badges span")
                date = badge_els[0].text if badge_els else "UNKNOWN"

                folder_name = f"[{date}] {title} ({subtitle})" if subtitle else f"[{date}] {title}"
                folder_name = sanitize_filename(folder_name)
                print("\n" + folder_name)
                alb_dir = artist_dir / folder_name
                try:
                    alb_dir.mkdir()
                except FileExistsError:
                    print(f"Directory '{alb_dir}' already exists.")
                    exit(1)
                except PermissionError:
                    print(f"Permission denied: Unable to create '{alb_dir}'.")
                    exit(1)
                except Exception as e:
                    print(f"An error occurred: {e}")
                    exit(1)

                summary_elements = card.find_elements(By.CSS_SELECTOR, "details.public-track-details:not([open])")
                if summary_elements:
                    summary_elements[0].click()
                    time.sleep(0.2)

                track_buttons = card.find_elements(By.XPATH, ".//button[.//span[contains(@class, 'track-item__num')]]")

                for btn in track_buttons:
                    if not btn.is_enabled():
                        continue

                    track_num = btn.find_element(By.CSS_SELECTOR, ".track-item__num").text

                    track_name = btn.find_element(By.CSS_SELECTOR, ".track-item__title .font-medium").text

                    name2_els = btn.find_elements(By.XPATH, ".//div[contains(@class, 'mt-0.5')]")
                    track_name2 = name2_els[0].text if name2_els else None

                    final_name = track_name2 if track_name2 else track_name
                    filename = sanitize_filename(f"{track_num}. {final_name}") + ".mp3"

                    print(f"  {filename}")
                    try:
                        btn.click()
                    except:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                        driver.execute_script("window.scrollBy(0, -300);")
                        btn.click()
                    try:
                        Alert(driver).accept()
                    except:
                        pass

                    session_data = None
                    for _ in range(10): # Try for up to 5 seconds
                        session_data = driver.execute_script("return window.captured_session;")
                        if session_data:
                            break
                        time.sleep(0.5)

                    if not session_data:
                        print("  -> Failed to capture session JSON! Skipping.")
                        continue

                    driver.execute_script("window.captured_session = null;")

                    stream_url = "https://evilenlucifervk.com" + session_data['stream_url']
                    request_id = session_data['x-request-id']

                    print(f"  Captured Session! URL: {stream_url}")

                    cookies = driver.get_cookies()
                    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                    user_agent = driver.execute_script("return navigator.userAgent;")

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
            print("------------------------")
    finally:
        driver.quit()
