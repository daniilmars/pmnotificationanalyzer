import uvicorn
from dotenv import load_dotenv

# Lädt die Umgebungsvariablen (z.B. GOOGLE_API_KEY) aus der .env-Datei
load_dotenv()

if __name__ == "__main__":
    # Startet den Server auf Port 8000, um Konflikte mit dem Frontend zu vermeiden
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
