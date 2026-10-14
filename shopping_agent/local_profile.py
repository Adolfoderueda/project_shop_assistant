"""Fixed public profiles for isolated local Ollama transports."""

DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
PROFILE_12B = "gemma4-12b-shop:16k"
ENDPOINT_12B = "http://127.0.0.1:11435"


def validate_endpoint(endpoint: str, *, model: str | None = None) -> str:
    if endpoint not in (DEFAULT_ENDPOINT, ENDPOINT_12B):
        raise ValueError("Only fixed local Ollama endpoints are permitted")
    if model == PROFILE_12B and endpoint != ENDPOINT_12B:
        raise ValueError("Gemma 12B requires its dedicated local endpoint")
    return endpoint


def generation_profile(model: str) -> dict:
    if model == PROFILE_12B:
        return {
            "think": True,
            "keep_alive": "30m",
            "options": {
                "temperature": 0,
                "num_ctx": 16384,
                "num_predict": 2048,
                "top_p": 0.95,
                "top_k": 64,
                "seed": 42,
                "draft_num_predict": 3,
            },
        }
    return {"think": False, "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 512}}
