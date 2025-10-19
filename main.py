"""
Swim OCR App - FastAPI Backend V2
Entry point for the modular swimming OCR application
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
