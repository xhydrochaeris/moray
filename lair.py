from mitmproxy import http
import subprocess
import datetime
import os

class StreamRipper:
    def request(self, flow: http.HTTPFlow) -> None:
        if flow.request.method == "GET" and "stream.evilenlucifervk.com/stream/audio" in flow.request.pretty_url:

            url = flow.request.pretty_url

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stream_{timestamp}.mp3"

            print(f"\n[!] Stream intercepted! Starting ffmpeg for {filename}")

            # 1. Extract headers from the Android app's request
            headers = flow.request.headers
            header_str = ""
            for key, value in headers.items():
                # We skip Host and Content-Length as ffmpeg calculates those itself
                if key.lower() not in ['host', 'content-length']:
                    header_str += f"{key}: {value}\r\n"

            # 2. Construct the ffmpeg command WITH headers
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-headers", header_str,
                "-i", url,
                "-c", "copy",
                filename
            ]

            # 3. Open a log file so we can see ffmpeg's output
            log_file = open(f"{filename}.log", "w")
            print(f"    -> Writing logs to {filename}.log")

            # 4. Launch ffmpeg, sending stderr to the log file
            subprocess.Popen(ffmpeg_cmd, stdout=log_file, stderr=subprocess.STDOUT)

addons = [StreamRipper()]
