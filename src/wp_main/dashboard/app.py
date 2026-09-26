from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .data import find_password, load_sites

HERE = Path(__file__).parent
NO_STORE = {"Cache-Control": "no-store"}

app = FastAPI(title="wp-main dashboard", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"sites": load_sites()}, headers=NO_STORE)


@app.get("/api/sites/{site_id}/password")
def password(site_id: str):
    value = find_password(site_id)
    if value is None:
        raise HTTPException(status_code=404, detail="パスワードが見つかりません", headers=NO_STORE)
    return JSONResponse({"password": value}, headers=NO_STORE)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
