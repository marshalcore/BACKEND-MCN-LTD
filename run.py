# run.py

import uvicorn
import os

# Use the PORT environment variable provided by Render
port = int(os.environ.get("PORT", 8000))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # Important: Use 0.0.0.0 to accept connections from any IP
        port=port,       # Use the port from environment variable
        reload=False     # Set to False in production (Render will handle this)
    )