import uvicorn

if __name__ == "__main__":
    # Ermöglicht das einfache Starten der App mit "python3 run.py"
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)