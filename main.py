from fastapi import FastAPI

app = FastAPI(title="agent-foundation")


@app.get("/health")
def health():
    return {"ok": True}
