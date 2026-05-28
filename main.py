import io
import threading
import uuid
from pathlib import Path
from threading import Lock

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

from processor import process_image, process_video

app = FastAPI(title="ComicFX")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv"}
ALLOWED_EXT = ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT

# job_id -> {"status", "progress", "output_path", "type", "error"}
jobs: dict[str, dict] = {}
jobs_lock = Lock()


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    cross_hatch: bool = Form(True),
    variable_contour: bool = Form(True),
    n_colors: int = Form(8),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    n_colors = max(4, min(12, n_colors))  # clamp to safe range
    opts = dict(cross_hatch=cross_hatch, variable_contour=variable_contour, n_colors=n_colors)

    is_video = suffix in ALLOWED_VIDEO_EXT
    job_id = str(uuid.uuid4())
    input_path = UPLOAD_DIR / f"{job_id}{suffix}"
    output_suffix = ".mp4" if is_video else ".png"
    output_path = OUTPUT_DIR / f"{job_id}_comic{output_suffix}"

    content = await file.read()
    input_path.write_bytes(content)

    if is_video:
        with jobs_lock:
            jobs[job_id] = {
                "status": "processing",
                "progress": 0,
                "output_path": str(output_path),
                "type": "video",
            }
        threading.Thread(
            target=_run_video_job,
            args=(job_id, str(input_path), str(output_path), opts),
        ).start()
        return {"job_id": job_id, "type": "video", "status": "processing"}

    # Image: process inline
    with jobs_lock:
        jobs[job_id] = {
            "status": "processing",
            "progress": 0,
            "output_path": str(output_path),
            "type": "image",
        }
    try:
        pil_img = Image.open(io.BytesIO(content)).convert("RGB")
        result = process_image(np.array(pil_img), **opts)
        Image.fromarray(result).save(str(output_path))
        with jobs_lock:
            jobs[job_id].update({"status": "done", "progress": 100})
    except Exception as exc:
        with jobs_lock:
            jobs[job_id].update({"status": "error", "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))

    return {"job_id": job_id, "type": "image", "status": "done"}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/download/{job_id}")
async def download(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job not complete yet")
    path = Path(job["output_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file missing")
    media = "video/mp4" if path.suffix == ".mp4" else "image/png"
    return FileResponse(path, media_type=media, filename=f"comicfx{path.suffix}")


# ---------------------------------------------------------------------------
# Background helper
# ---------------------------------------------------------------------------

def _run_video_job(job_id: str, input_path: str, output_path: str, opts: dict) -> None:
    try:
        def on_progress(pct: int) -> None:
            with jobs_lock:
                jobs[job_id]["progress"] = pct

        process_video(input_path, output_path, on_progress, **opts)
        with jobs_lock:
            jobs[job_id].update({"status": "done", "progress": 100})
    except Exception as exc:
        with jobs_lock:
            jobs[job_id].update({"status": "error", "error": str(exc)})
