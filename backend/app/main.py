from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, cart, categories, health, orders, products, shops, webhooks

app = FastAPI(
    title="LocalMart API",
    version="0.1.0",
    description="Backend for the LocalMart multi-vendor marketplace platform.",
)

# CORS: only the frontend's own origin is allowed to call this API with
# credentials. We deliberately do NOT use "*" here — that's a common
# shortcut in tutorials that becomes a real security gap in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers get registered here. Each new domain (auth, shops, products,
# cart, orders...) gets its own router file and one line added below —
# main.py itself should stay small forever.
app.include_router(health.router, tags=["health"])
app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(shops.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(webhooks.router)


@app.get("/")
async def root():
    return {"message": "LocalMart API is running", "environment": settings.environment}
