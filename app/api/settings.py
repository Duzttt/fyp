import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings


class SettingsUpdate(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = None


router = APIRouter()


SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "settings.json")


@router.get("/settings")
async def get_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {
            "provider": settings.LLM_PROVIDER,
            "model": settings.GEMINI_MODEL,
            "has_api_key": bool(settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")),
        }

    try:
        import json
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            data["has_api_key"] = bool(data.get("api_key"))
            data.pop("api_key", None)
            return data
    except Exception:
        return {
            "provider": settings.LLM_PROVIDER,
            "model": settings.GEMINI_MODEL,
            "has_api_key": False,
        }


@router.post("/settings")
async def update_settings(settings_update: SettingsUpdate):
    valid_providers = ["gemini", "openrouter"]
    if settings_update.provider not in valid_providers:
        raise HTTPException(status_code=400, detail="Invalid provider")

    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        import json
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings_update.model_dump(), f)
        return {"success": True, "message": "Settings updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")
