"""
main.py - entrypoint server FastAPI untuk local & Vercel
"""

import os
from api import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)