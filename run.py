import os
import uvicorn
from app.core.config import settings # Pulls your ENV variable profile configuration

if __name__ == "__main__":
    # Check if the app environment config is explicitly set to production
    is_production = settings.ENV == "production"

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0" if is_production else "127.0.0.1", # 0.0.0.0 exposes to the public web safely
        port=8000,
        
        # 💥 PRODUCTION HARDENING: Turn off auto-reload on production live servers
        reload=False if is_production else True,
        
        # 💥 PRODUCTION PERFORMANCE: Scale up to multiple CPU process threads on production
        workers=4 if is_production else 1 
    )
