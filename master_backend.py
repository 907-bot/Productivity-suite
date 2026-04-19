"""
Master Backend - Productivity Suite OS
Consolidates all 5 specialized backends into a single API service for deployment.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Import the logic from each sub-backend
# Note: We'll modify the sub-apps to be modular
from life_admin.backend.main import app as life_app
from wellness_manager.backend.main import app as wellness_app
from finance_manager.backend.main import app as finance_app
from content_manager.backend.main import app as content_app
from relationship_manager.backend.main import app as relationship_app

app = FastAPI(title="Productivity Suite OS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all sub-applications
app.mount("/api/life", life_app)
app.mount("/api/wellness", wellness_app)
app.mount("/api/finance", finance_app)
app.mount("/api/content", content_app)
app.mount("/api/relationship", relationship_app)

@app.get("/")
def home():
    return {"status": "Productivity Suite API is Online", "apps": ["life", "wellness", "finance", "content", "relationship"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
