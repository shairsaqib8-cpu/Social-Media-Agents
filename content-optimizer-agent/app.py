import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agents.optimizer_agent import OptimizerAgent

app = FastAPI(title="Content Optimizer Agent")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class OptimizeRequest(BaseModel):
    title: str
    description: str = ""
    tags: list[str] = []
    hashtags: list[str] = []
    modes: list[str] = ["SEO", "SXO", "AEO", "GEO"]
    niche: str = ""
    language: str = "English"


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/optimize")
async def optimize(req: OptimizeRequest):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Title is required.")
    try:
        agent = OptimizerAgent()
        result = agent.optimize(
            title=req.title,
            description=req.description,
            tags=req.tags,
            hashtags=req.hashtags,
            modes=req.modes,
            niche=req.niche,
            language=req.language
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8003, reload=False)
