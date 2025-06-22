"""Application and API endpoints."""

import os
import time
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
import logging
from app.movies import search_movies, get_movie_details
from app.series import search_series, get_series_details
from app.security import rate_limit_middleware, sanitize_input, log_request, log_error, get_client_ip
from app.logger import get_logger, uvicorn_logger
from app.errors import (
    StreamPortalError, ValidationError, AuthenticationError, ExternalAPIError,
    handle_streamportal_error, create_http_exception, handle_generic_exception,
    validate_api_key, validate_search_query, validate_content_id, validate_content_type
)

# Load environment variables
load_dotenv()

# Get logger instance using uvicorn logger
logger = get_logger("main")

# Load environment variables (but don't validate yet)
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

class SearchRequest(BaseModel):
    text_search: str
    type_of_content: str
    option_language: str = "en-US"
    
    @validator('text_search')
    def sanitize_text_search(cls, v):
        sanitized = sanitize_input(v)
        validate_search_query(sanitized)
        return sanitized
    
    @validator('type_of_content')
    def validate_content_type(cls, v):
        validate_content_type(v)
        return v

class DetailsRequest(BaseModel):
    content_id: int
    type_of_content: str
    option_language: str = "en-US"
    
    @validator('content_id')
    def validate_content_id(cls, v):
        validate_content_id(v)
        return v
    
    @validator('type_of_content')
    def validate_content_type(cls, v):
        validate_content_type(v)
        return v

class SearchResponse(BaseModel):
    results: list[dict]

class DetailsResponse(BaseModel):
    details: dict

app = FastAPI(
    title="StreamPortal API",
    description="A secure API for searching movies and series with streaming availability",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

def get_headers():
    """Get headers with API key from environment variable."""
    if not TMDB_API_KEY:
        raise AuthenticationError("TMDB_API_KEY environment variable is required")
    return {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_API_KEY}"
    }

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header and log requests."""
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log successful requests
        log_request(request, process_time)
        
        return response
    except Exception as e:
        process_time = time.time() - start_time
        log_error(request, e)
        raise

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Apply rate limiting to all requests."""
    return await rate_limit_middleware(request, call_next)

@app.exception_handler(StreamPortalError)
async def streamportal_error_handler(request: Request, exc: StreamPortalError):
    """Handle StreamPortal custom errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=handle_streamportal_error(exc)
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """Handle generic exceptions."""
    client_ip = get_client_ip(request)
    logger.exception(
        f"Unhandled exception for IP {client_ip}",
        extra_fields={
            "client_ip": client_ip,
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__
        }
    )
    
    error_response = handle_generic_exception(exc, "API Request")
    return JSONResponse(
        status_code=500,
        content=error_response
    )

@app.on_event("startup")
async def startup_event():
    """Validate configuration on startup."""
    if not TMDB_API_KEY:
        logger.critical("TMDB_API_KEY environment variable is required")
        raise ValueError("TMDB_API_KEY environment variable is required")
    
    # Validate API key
    try:
        validate_api_key(TMDB_API_KEY)
        logger.info("TMDB API key validated successfully")
    except AuthenticationError as e:
        logger.critical(f"Invalid TMDB API key: {e.message}")
        raise
    
    logger.info(f"CORS configured for origins: {ALLOWED_ORIGINS}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {"status": "healthy", "message": "StreamPortal API is running"}

@app.post("/search")
async def search(request: SearchRequest):
    """Search endpoint for movies and series - returns basic info only.
    
    This endpoint performs a quick search and returns basic information
    without checking streaming availability or detailed metadata.
    Perfect for displaying search results in a webapp.
    """ 

    logger.info(
        f"Search request: {request.type_of_content} - '{request.text_search}'",
        extra_fields={
            "content_type": request.type_of_content,
            "search_query": request.text_search,
            "language": request.option_language
        }
    )

    headers = get_headers()

    try:
        if request.type_of_content == "Movie":
            response = await search_movies(request.text_search, request.option_language, headers)
            logger.info(
                f"Movie search completed: {len(response)} results found",
                extra_fields={"result_count": len(response)}
            )
            return SearchResponse(results=response)
        else:  # Series
            response = await search_series(request.text_search, request.option_language, headers)
            logger.info(
                f"Series search completed: {len(response)} results found",
                extra_fields={"result_count": len(response)}
            )
            return SearchResponse(results=response)
    except Exception as e:
        logger.error(
            f"Search failed: {str(e)}",
            extra_fields={
                "content_type": request.type_of_content,
                "search_query": request.text_search,
                "error_type": type(e).__name__
            }
        )
        if isinstance(e, StreamPortalError):
            raise
        else:
            raise ExternalAPIError(f"Search failed: {str(e)}", "TMDB API")


@app.post("/details")
async def get_details(request: DetailsRequest):
    """Get detailed information for a specific movie or series.
    
    This endpoint is called when a user clicks on a search result.
    It performs the heavy lifting of checking streaming availability
    and gathering detailed metadata.
    """

    logger.info(
        f"Details request: {request.type_of_content} ID {request.content_id}",
        extra_fields={
            "content_type": request.type_of_content,
            "content_id": request.content_id,
            "language": request.option_language
        }
    )

    headers = get_headers()

    try:
        if request.type_of_content == "Movie":
            response = await get_movie_details(request.content_id, request.option_language, headers)
            logger.info(
                f"Movie details retrieved successfully",
                extra_fields={
                    "content_id": request.content_id,
                    "is_available": response.get("is_available", False)
                }
            )
            return DetailsResponse(details=response)
        else:  # Series
            response = await get_series_details(request.content_id, request.option_language, headers)
            logger.info(
                f"Series details retrieved successfully",
                extra_fields={
                    "content_id": request.content_id,
                    "is_available": response.get("is_available", False),
                    "seasons_count": len(response.get("valid_seasons", []))
                }
            )
            return DetailsResponse(details=response)
    except Exception as e:
        logger.error(
            f"Details retrieval failed: {str(e)}",
            extra_fields={
                "content_type": request.type_of_content,
                "content_id": request.content_id,
                "error_type": type(e).__name__
            }
        )
        if isinstance(e, StreamPortalError):
            raise
        else:
            raise ExternalAPIError(f"Failed to get details: {str(e)}", "TMDB API")