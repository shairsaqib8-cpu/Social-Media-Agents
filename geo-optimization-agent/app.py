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

from agents.geo_agent import GEOAgent

app = FastAPI(title="GEO Optimization Agent")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class AnalyzeRequest(BaseModel):
    topic: str
    content: str = ""
    language: str = "English"


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Topic is required.")
    try:
        agent = GEOAgent()
        result = agent.analyze(req.topic, req.content, req.language)
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)
