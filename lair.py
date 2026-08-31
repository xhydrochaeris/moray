from mitmproxy import http
import subprocess
import datetime
import os

class StreamRipper:
    def request(self, flow: http.HTTPFlow) -> None:
        if flow.request.method == "GET" and "stream.evilenlucifervk.com/stream/audio" in flow.request.pretty_url:

            url = flow.request.pretty_url

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stream_{timestamp}"

            print(f"\n[!] Stream intercepted! Starting yt-dlp for {filename}")

            # 1. Extract headers from the Android app's request & add to command
            headers = flow.request.headers
            ytdlp_cmd = [
                "yt-dlp"
            ]
            for key, value in headers.items():
                # We skip Host and Content-Length as ffmpeg calculates those itself
                if key.lower() not in ['host', 'content-length']:
                    ytdlp_cmd.append("--add-headers")
                    ytdlp_cmd.append(f"{key}:{value}")

            # 2. Complete the yt-dlp command
            ytdlp_cmd.append(url)
            ytdlp_cmd.append("-o")
            ytdlp_cmd.append(filename+".%(ext)s")

            # 3. Open a log file so we can see yt-dlp's output
            log_file = open(f"{filename}.log", "w")
            print(f"    -> Writing logs to {filename}.log")

            # 4. Launch yt-dlp, sending stderr to the log file
            subprocess.Popen(ytdlp_cmd, stdout=log_file, stderr=subprocess.STDOUT)

addons = [StreamRipper()]
