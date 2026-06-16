from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

SERVICES = [
    {
        "name": "Linkding",
        "url": "http://rpi.local:9090",
        "description": "Bookmark manager",
        "icon": "📑",
        "status": "online",
    },
    {
        "name": "Jellyfin",
        "url": "http://rpi.local:8096",
        "description": "Media server",
        "icon": "🎬",
        "status": "online",
    },
    {
        "name": "Transmission",
        "url": "http://rpi.local:9091",
        "description": "BitTorrent client",
        "icon": "⬇️",
        "status": "online",
    },
    {
        "name": "Open WebUI",
        "url": "http://rpi.local:8080",
        "description": "LLM chat interface",
        "icon": "🤖",
        "status": "online",
    }
]


@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request, "dashboard.html", {"services": SERVICES}
    )
