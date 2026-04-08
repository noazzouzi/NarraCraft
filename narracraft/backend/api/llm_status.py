from fastapi import APIRouter

from backend.llm.manager import get_provider, get_provider_name, list_providers

router = APIRouter()


@router.get("/status")
async def llm_status():
    try:
        provider = get_provider()
        status = await provider.check_status()
        return status
    except RuntimeError:
        return {
            "provider": None,
            "configured": False,
            "message": "LLM provider not configured. Set API key in Settings.",
            "available_providers": list_providers(),
        }
