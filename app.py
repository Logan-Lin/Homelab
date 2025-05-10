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
    {"name": "Plex", "url": "https://plex.yanlincs.com", "description": "Media server for movies and shows", "icon": "/assets/img/plex.webp"},
    {"name": "Emby", "url": "https://emby.yanlincs.com", "description": "Media server for movies and shows", "icon": "/assets/img/emby.webp"},
    {"name": "Overseerr", "url": "https://seerr.yanlincs.com", "description": "Request manager for media servers", "icon": "/assets/img/overseerr.webp"},
    {"name": "Tautulli", "url": "https://tautu.yanlincs.com", "description": "Media server monitoring", "icon": "/assets/img/tautulli.webp"},
    {"name": "Gitea", "url": "https://git.yanlincs.com", "description": "Self-hosted Git server", "icon": "/assets/img/gitea.webp"},
    {"name": "Nextcloud", "url": "https://cloud.yanlincs.com", "description": "Self-hosted cloud storage", "icon": "/assets/img/nextcloud.webp"},
    {"name": "immich", "url": "https://photo.yanlincs.com", "description": "Home photo and video server", "icon": "/assets/img/immich.webp"},
    {"name": "Docmost", "url": "https://note.yanlincs.com", "description": "Collaborative wiki and note software", "icon": "/assets/img/docmost.webp"},
    {"name": "Overleaf", "url": "https://latex.yanlincs.com", "description": "Collaborative LaTeX editor", "icon": "/assets/img/overleaf.webp"},
    {"name": "linkding", "url": "https://link.yanlincs.com", "description": "Bookmark manager and archiver", "icon": "/assets/img/linkding.webp"},
    {"name": "WebDAV", "url": "https://dav.yanlincs.com", "description": "A simple WebDAV server", "icon": "/assets/img/webdav.webp"},
    {"name": "Nginx Proxy Manager", "url": "https://proxy.yanlincs.com", "description": "Proxy server connecting home and public internet", "icon": "/assets/img/nginx.webp"}
]
for service in services:
    service["status"] = "unknown"
    service["previous_status"] = "unknown"
    service["last_checked"] = 0
    service["response_code"] = None
    service["error"] = None

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
        response = requests.head(service["url"], timeout=5, headers=headers, allow_redirects=True)
        status_code = response.status_code
        
        # If the HEAD request fails or returns non-2xx, try a GET request
        if status_code >= 400:
            response = requests.get(service["url"], timeout=5, headers=headers, allow_redirects=True)
            status_code = response.status_code
        
        if status_code < 400 or (status_code in [401, 403]):
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
        newly_down_services = []
        recovered_services = []
        
        for service in services:
            check_service_health(service)
            
            # Check for state transitions
            if service["status"] == "down" and service["previous_status"] != "down":
                newly_down_services.append(service)
            elif service["status"] == "up" and service["previous_status"] == "down":
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