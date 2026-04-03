from fastapi import FastAPI

app = FastAPI(title="AI Tool - Harness Scaffold")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Replace this with your implementation"}
