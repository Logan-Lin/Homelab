from flask import Flask, jsonify, render_template
import requests
import threading
import time
import logging
from waitress import serve

app = Flask(__name__, static_folder="assets", static_url_path="/assets")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Services to monitor
services = [
    {"name": "Plex", "url": "https://plex.yanlincs.com", "status": "unknown", "last_checked": 0, "auth_ok": True, "description": "Media server for movies and shows", "icon": "/assets/img/plex.webp"},
    {"name": "Emby", "url": "https://emby.yanlincs.com", "status": "unknown", "last_checked": 0, "description": "Media server for movies and shows", "icon": "/assets/img/emby.webp"},
    {"name": "Overseerr", "url": "https://seerr.yanlincs.com", "status": "unknown", "last_checked": 0, "description": "Request manager for media servers", "icon": "/assets/img/overseerr.webp"},
    {"name": "Gitea", "url": "https://git.yanlincs.com", "status": "unknown", "last_checked": 0, "description": "Self-hosted Git server", "icon": "/assets/img/gitea.webp"},
    {"name": "Nextcloud", "url": "https://cloud.yanlincs.com", "status": "unknown", "last_checked": 0, "description": "Self-hosted cloud storage", "icon": "/assets/img/nextcloud.webp"},
    {"name": "immich", "url": "https://photo.yanlincs.com", "status": "unknown", "last_checked": 0, "auth_ok": True, "description": "Home photo and video server", "icon": "/assets/img/immich.webp"},
    {"name": "Docmost", "url": "https://note.yanlincs.com", "status": "unknown", "last_checked": 0, "description": "Collaborative wiki and note software", "icon": "/assets/img/docmost.webp"},
    {"name": "Overleaf", "url": "https://latex.yanlincs.com", "status": "unknown", "last_checked": 0, "description": "Collaborative LaTeX editor", "icon": "/assets/img/overleaf.webp"},
    {"name": "linkding", "url": "https://link.yanlincs.com", "status": "unknown", "last_checked": 0, "description": "Bookmark manager and archiver", "icon": "/assets/img/linkding.webp"},
    {"name": "WebDAV", "url": "https://dav.yanlincs.com", "status": "unknown", "last_checked": 0, "auth_ok": True, "description": "A simple WebDAV server", "icon": "/assets/img/webdav.webp"},
    {"name": "Nginx Proxy Manager", "url": "https://proxy.yanlincs.com", "status": "unknown", "last_checked": 0, "description": "Proxy server connecting home and public internet", "icon": "/assets/img/nginx.webp"}
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health-status')
def health_status():
    return jsonify(services)

def check_service_health(service):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # First try a HEAD request which is faster
        response = requests.head(service["url"], timeout=5, headers=headers, allow_redirects=True)
        status_code = response.status_code
        
        # If the HEAD request fails or returns non-2xx, try a GET request
        if status_code >= 400:
            response = requests.get(service["url"], timeout=5, headers=headers, allow_redirects=True)
            status_code = response.status_code
        
        # For services that are known to require authentication
        if status_code < 400 or (status_code in [401, 403] and service.get("auth_ok", False)):
            service["status"] = "up"
            service["response_code"] = status_code
        else:
            service["status"] = "down"
            service["response_code"] = status_code
    except requests.RequestException as e:
        service["status"] = "down"
        service["response_code"] = None
        service["error"] = str(e)
    
    service["last_checked"] = time.time()
    logger.info(f"Health check for {service['name']}: {service['status']} (Code: {service.get('response_code')})")

def health_check_worker():
    while True:
        for service in services:
            check_service_health(service)
        # Sleep for 5 minutes before next check
        time.sleep(300)

# Start health check thread
health_thread = threading.Thread(target=health_check_worker, daemon=True)
health_thread.start()

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=8100, threads=16) 