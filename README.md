# moray
moray is an automated ripping tool for the Evil en Lucifer (EeL) website

If you can't run it yourself, you can find all site content ripped at https://drive.google.com/drive/folders/1sf2emWVv_sRDuGfxdjNftihpIbohbMjh?usp=drive_link

## Setup

You need Python + nodriver + Chromium + ffmpeg

## Run

`moray.py [url]+` (can paste multiple urls separated by spaces)

Optional argument `-a`, which lets you authenticate (needed to download some stuff)

Downloads will all be in the same folder as script

# LaIR
LaIR (Listen and Insta-Rip) is a ripping tool for the Evil en Lucifer Android app

If you can't run it yourself, you can find some of the app-exclusive content ripped at https://drive.google.com/drive/folders/1fogy6POlQJLAQoILEsKbOoSjfto-ggY7?usp=sharing

## Setup

You need Waydroid + ARM translation layer + mitmproxy + yt-dlp. You also need to install the Evil en Lucifer app in Waydroid.

```
# Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# Redirect Waydroid's HTTP/HTTPS traffic to mitmproxy on port 8080
sudo iptables -t nat -A PREROUTING -i waydroid0 -p tcp --dport 80 -j REDIRECT --to-port 8080
sudo iptables -t nat -A PREROUTING -i waydroid0 -p tcp --dport 443 -j REDIRECT --to-port 8080
```

* Start mitmproxy and the waydroid session
* Enter the waydroid shell: `sudo waydroid shell`
* (In waydroid shell) Mount the system partition as read/write: `mount -o rw,remount /`
* (In host shell):
```
# The cert must be named by its subject hash with a .0 extension
CERT_HASH=$(openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1)
# Copy to somehwere accessible by waydroid
cp ~/.mitmproxy/mitmproxy-ca-cert.pem ~/.local/share/waydroid/data/$CERT_HASH.0
echo $CERT_HASH # Copy this. You'll paste it where there is the line [PASTE] in the waydroid shell part
```
* (In waydroid shell):
```
cp /data/[PASTE].0 /system/etc/security/cacerts/
chmod 644 /system/etc/security/cacerts/[PASTE].0
```
* Close waydroid shell, Reboot waydroid

## Run

Unfortunately this cannot be automated. You must click each track you want to rip in the Waydroid container with the app open.

1. In a shell window run `mitmdump -s lair.py`

2. Select songs in the Evil en Lucifer app running in Waydroid

If you select a song and it doesn't rip, clear Evil en Lucifer app's cache
