# run.py

import uvicorn

import os
port = int(os.environ.get("PORT", 8000))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True  # Auto-reload during development
    )
