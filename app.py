from flask import Flask, jsonify, render_template
import requests
import threading
import time
import logging
from waitress import serve
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="assets", static_url_path="/assets")
load_dotenv()

# Services to monitor
services = [
    {"export": True, "name": "Plex", "url": "https://plex.yanlincs.com", "description": "Media streaming server", "icon": "/assets/img/plex.webp", "icon_dark": "/assets/img/plex_dark.webp"},
    {"export": True, "name": "Emby", "url": "https://emby.yanlincs.com", "description": "Media streaming server", "icon": "/assets/img/emby.webp", "icon_dark": "/assets/img/emby_dark.webp"},
    {"export": True, "name": "Overseerr", "url": "https://seerr.yanlincs.com", "description": "Media request manager", "icon": "/assets/img/overseerr.webp", "icon_dark": "/assets/img/overseerr_dark.webp"},
    {"export": True, "name": "Tautulli", "url": "https://tautu.yanlincs.com", "description": "Media server monitoring", "icon": "/assets/img/tautulli.webp", "icon_dark": "/assets/img/tautulli_dark.webp"},
    {"export": True, "name": "Gitea", "url": "https://git.yanlincs.com", "description": "Git and development platform", "icon": "/assets/img/gitea.webp"},
    {"export": True, "name": "Nextcloud", "url": "https://cloud.yanlincs.com", "description": "Cloud storage and office suite", "icon": "/assets/img/nextcloud.webp"},
    {"export": True, "name": "immich", "url": "https://photo.yanlincs.com", "description": "Home photo server", "icon": "/assets/img/immich.webp"},
    {"export": True, "name": "Docmost", "url": "https://note.yanlincs.com", "description": "Collaborative document editor", "icon": "/assets/img/docmost.webp"},
    {"export": True, "name": "Overleaf", "url": "https://latex.yanlincs.com", "description": "Collaborative LaTeX editor", "icon": "/assets/img/overleaf.webp"},
    {"export": True, "name": "linkding", "url": "https://link.yanlincs.com", "description": "Bookmark manager", "icon": "/assets/img/linkding.webp"},
    {"export": True, "name": "WebDAV", "url": "https://dav.yanlincs.com", "description": "A simple WebDAV server", "icon": "/assets/img/webdav.webp", "icon_dark": "/assets/img/webdav_dark.webp"},
    {"export": True, "name": "PairDrop", "url": "https://drop.yanlincs.com", "description": "P2P file sharing service", "icon": "/assets/img/pairdrop.webp"},
    {"export": True, "name": "Gotify", "url": "https://notify.yanlincs.com", "description": "Message distribution server", "icon": "/assets/img/gotify.webp"},
    {"export": True, "name": "NPM", "url": "https://proxy.yanlincs.com", "description": "Ngnix proxy manager", "icon": "/assets/img/nginx.webp"},
    # Inner services (not exposed to the public)
    {"export": False, "name": "Sonarr", "url": "http://so.home.lab:8989", "description": "TV series management", "icon": "/assets/img/sonarr.webp"},
    {"export": False, "name": "Radarr", "url": "http://ra.home.lab:7878", "description": "Movie management", "icon": "/assets/img/radarr.webp", "icon_dark": "/assets/img/radarr_dark.webp"},
    {"export": False, "name": "Lidarr", "url": "http://li.home.lab:8686", "description": "Music management", "icon": "/assets/img/lidarr.webp"},
    {"export": False, "name": "Bazarr", "url": "http://ba.home.lab:6767", "description": "Subtitle management", "icon": "/assets/img/bazarr.webp"},
    {"export": False, "name": "Pi-hole", "url": "http://pi.home.lab/admin", "description": "DNS-based ad blocker", "icon": "/assets/img/pihole.webp", "icon_dark": "/assets/img/pihole_dark.webp"},
    {"export": False, "display": False,"name": "Pi-hole @ nas", "url": "http://hole.back.up/admin", "description": "Backup of main Pi-hole", "icon": "/assets/img/pihole.webp", "icon_dark": "/assets/img/pihole_dark.webp"},
    {"export": False, "name": "Syncthing", "url": "http://pi.home.lab:8384", "description": "P2P file sync", "icon": "/assets/img/syncthing.webp"},
    {"export": False, "display": False, "name": "Syncthing @ nas", "url": "http://sync.home.lab:8384", "description": "P2P file sync", "icon": "/assets/img/syncthing.webp"},
    {"export": False, "name": "qBittorrent", "url": "http://qb.home.lab:8080", "description": "BitTorrent client", "icon": "/assets/img/qbittorrent.webp"},
    {"export": False, "name": "Transmission", "url": "http://tr.home.lab:9091", "description": "BitTorrent client", "icon": "/assets/img/transmission.webp"},
    {"export": False, "name": "Nas", "url": "http://nas.home.lab", "description": "Unraid home server", "icon": "/assets/img/unraid.webp"},
    {"export": False, "name": "Router", "url": "http://router.home.lab", "description": "OpenWRT home router", "icon": "/assets/img/openwrt.webp", "icon_dark": "/assets/img/openwrt_dark.webp"},
]
for service in services:
    service["status"] = "unknown"
    service["previous_status"] = "unknown"
    service["last_checked"] = 0
    service["response_code"] = None
    service["error"] = None
    service["response_time"] = None

# Response time threshold for slow status (in seconds)
SLOW_THRESHOLD = float(os.getenv("SLOW_THRESHOLD"))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health-status')
def health_status():
    return jsonify(services)

def send_notification(title, message, priority=5):
    data = {
        "title": title,
        "message": message,
        "priority": priority,
    }
    response = requests.post(f'{os.getenv("NOTIFY_URL")}?token={os.getenv("NOTIFY_TOKEN")}', json=data)

    return response.json()

def check_service_health(service):
    service["previous_status"] = service["status"]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # First try a HEAD request which is faster
        start_time = time.time()
        response = requests.head(service["url"], timeout=5, headers=headers, allow_redirects=True)
        status_code = response.status_code
        
        # If the HEAD request fails or returns non-2xx, try a GET request
        if status_code >= 400:
            start_time = time.time()
            response = requests.get(service["url"], timeout=5, headers=headers, allow_redirects=True)
            status_code = response.status_code
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000
        service["response_time"] = int(response_time)
        
        if status_code < 400 or (status_code in [401, 403]):
            # Service is reachable, check if it's slow
            if response_time > SLOW_THRESHOLD:
                service["status"] = "slow"
            else:
                service["status"] = "up"
            service["response_code"] = status_code
        else:
            service["status"] = "down"
            service["response_code"] = status_code
    except requests.RequestException as e:
        service["status"] = "down"
        service["response_code"] = None
        service["response_time"] = None
    
    service["last_checked"] = time.time()
    logger.info(f"Health check for {service['name']}: {service['status']} (Code: {service.get('response_code')}, Time: {service.get('response_time')}s)")

def health_check_worker():
    while True:
        newly_down_services = []
        recovered_services = []
        
        for service in services:
            check_service_health(service)
            
            # Check for state transitions - only consider actual down states, not slow
            if service["status"] == "down" and service["previous_status"] != "down":
                newly_down_services.append(service)
            elif service["status"] != "down" and service["previous_status"] == "down":
                recovered_services.append(service)

        # Notify about newly down services
        if newly_down_services:
            message = f"⚠️ Services down: {', '.join([s['name'] for s in newly_down_services])}"
            notify_resp = send_notification("Service Down Alert", message, priority=9)
            logger.info(f"Down notification sent: {notify_resp}")
        
        # Notify about recovered services
        if recovered_services:
            message = f"✅ Services recovered: {', '.join([s['name'] for s in recovered_services])}"
            notify_resp = send_notification("Service Recovery", message, priority=2)
            logger.info(f"Recovery notification sent: {notify_resp}")
        
        # Sleep for 5 minutes before next check
        time.sleep(300)

# Start health check thread
health_thread = threading.Thread(target=health_check_worker, daemon=True)
health_thread.start()

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=8100, threads=16) 