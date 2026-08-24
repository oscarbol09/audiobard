from fastapi import FastAPI

app = FastAPI(title="AudioBard API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check � Tauri queries this on startup."""
    return {"status": "ok"}
