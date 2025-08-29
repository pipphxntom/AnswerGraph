import uvicorn
from typing import Optional, Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import logging
import os

from src.api.routes import router as api_router
from src.api.pdf_routes import router as pdf_router
from src.api.admin_routes import admin_router
from src.core.config import settings
from src.core.dependencies import (
    get_qdrant_client, 
    get_embedding_model, 
    get_session,
    init_embedding_model,
    init_qdrant_client,
    init_reranker,
    init_cross_encoder,
    get_reranker,
    get_cross_encoder,
    init_retriever,
    get_retriever
)

logger = logging.getLogger(__name__)

def init_singletons():
    """Initialize all singleton dependencies."""
    logger.info("Initializing all singleton dependencies")
    init_embedding_model()
    init_qdrant_client()
    init_reranker()
    init_cross_encoder()
    init_retriever()


def create_app(config: Optional[Dict[str, Any]] = None) -> FastAPI:
    """
    Application factory pattern for creating the FastAPI app.
    
    Args:
        config: Optional configuration to override settings
        
    Returns:
        FastAPI application instance
    """
    # Override config if provided
    app_settings = settings
    if config:
        for key, value in config.items():
            if hasattr(app_settings, key):
                setattr(app_settings, key, value)
    
    # Create FastAPI app
    app = FastAPI(
        title=app_settings.PROJECT_NAME,
        description=app_settings.PROJECT_DESCRIPTION,
        version=app_settings.VERSION,
        openapi_url=f"{app_settings.API_V1_STR}/openapi.json"
    )
    
    # Initialize all singletons
    init_singletons()
    
    # Set up CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include all routers
    app.include_router(api_router, prefix=app_settings.API_V1_STR)
    app.include_router(pdf_router, prefix=app_settings.API_V1_STR)
    app.include_router(admin_router, prefix=app_settings.API_V1_STR)
    
    # Mount static files directory
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Add root endpoint to redirect to UI
    @app.get("/")
    async def root():
        return RedirectResponse(url="/static/index.html")
    
    # Add startup and shutdown events
    @app.on_event("startup")
    async def startup_event():
        """Execute startup tasks."""
        logger.info(f"Starting {app_settings.PROJECT_NAME} v{app_settings.VERSION}")
        logger.info(f"Debug mode: {app_settings.DEBUG}")
        
        # Check singletons to make sure they're initialized properly
        # Embedding model
        model = get_embedding_model()
        if model:
            # Pre-load model by running a simple embedding
            _ = model.encode("warmup")
            logger.info(f"Embedding model ready: {app_settings.EMBEDDING_MODEL}")
        else:
            logger.warning("Embedding model not initialized properly")
        
        # Qdrant client
        client = get_qdrant_client()
        if client:
            try:
                _ = client.get_collections()
                logger.info(f"Qdrant connection established: {app_settings.QDRANT_HOST}:{app_settings.QDRANT_PORT}")
            except Exception as e:
                logger.error(f"Qdrant connection failed: {str(e)}")
        else:
            logger.warning("Qdrant client not initialized properly")
        
        # Reranker model
        reranker = get_reranker()
        if reranker:
            logger.info("Reranker model ready")
        else:
            logger.warning("Reranker not initialized properly")
        
        # Cross-encoder model
        cross_encoder = get_cross_encoder()
        if cross_encoder:
            # Pre-load model by running a simple prediction
            _ = cross_encoder.predict([("warmup", "warmup text")])
            logger.info("Cross-encoder model ready")
        else:
            logger.warning("Cross-encoder not initialized properly")
            
        # Retriever
        retriever = get_retriever()
        if retriever:
            logger.info("Retriever ready")
        else:
            logger.warning("Retriever not initialized properly")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Execute shutdown tasks."""
        logger.info("Shutting down application")
        # Reset singleton instances for clean shutdown
        from src.core.dependencies import (
            _embedding_model, 
            _qdrant_client, 
            _reranker, 
            _cross_encoder,
            _retriever
        )
        
        # Close Qdrant client if it exists
        if _qdrant_client:
            try:
                # No explicit close method but set to None to release resources
                logger.info("Releasing Qdrant client")
            except Exception as e:
                logger.error(f"Error releasing Qdrant client: {str(e)}")
        
        # Set all singletons to None
        globals()["_embedding_model"] = None
        globals()["_qdrant_client"] = None
        globals()["_reranker"] = None
        globals()["_cross_encoder"] = None
        globals()["_retriever"] = None
        
        logger.info("All singleton resources released")
    
    return app

# Create the default app instance
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS
    )
