"""Movie search and details functionality for StreamPortal API."""

import asyncio

import aiohttp

from app.errors import ExternalAPIError, NotFoundError
from app.logger import get_logger
from app.utils import check_url_exists_async

# Get logger instance
logger = get_logger("movies")


async def search_movies(text_search, option_language, headers):
    """Quick search that returns basic movie information."""
    movies_list = []

    logger.info(
        f"Starting movie search for: '{text_search}'",
        extra_fields={"search_query": text_search, "language": option_language},
    )

    # Create aiohttp session for concurrent requests
    async with aiohttp.ClientSession() as session:
        # Search through first 5 pages concurrently
        tasks = []
        for page in range(1, 6):
            url = (
                f"https://api.themoviedb.org/3/search/movie?query={text_search}"
                f"&include_adult=false&language={option_language}&page={page}"
            )
            tasks.append(fetch_movie_page(session, url, headers, page))

        # Execute all page requests concurrently
        page_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process all movies from all pages - only basic info
        for page_num, page_data in enumerate(page_results, 1):
            if isinstance(page_data, Exception):
                logger.error(
                    f"Failed to fetch page {page_num}",
                    extra_fields={
                        "page": page_num,
                        "error": str(page_data),
                        "error_type": type(page_data).__name__,
                    },
                )
                continue

            if isinstance(page_data, dict) and page_data.get("results"):
                logger.debug(
                    f"Processing page {page_num} with "
                    f"{len(page_data['results'])} movies",
                    extra_fields={
                        "page": page_num,
                        "movies_count": len(page_data["results"]),
                    },
                )

                for movie in page_data["results"]:
                    poster = await display_movie_poster(movie)
                    movies_list.append(
                        {
                            "id": movie["id"],
                            "original_title": movie["original_title"],
                            "overview": movie["overview"],
                            "release_date": movie["release_date"],
                            "vote_average": movie["vote_average"],
                            "poster": poster,
                        }
                    )

    logger.info(
        f"Movie search completed: {len(movies_list)} movies found",
        extra_fields={"total_movies": len(movies_list), "search_query": text_search},
    )

    if movies_list:
        return movies_list
    else:
        return []


async def get_movie_details(movie_id, option_language, headers):
    """Get detailed movie information including streaming availability check."""
    logger.info(
        f"Getting details for movie ID: {movie_id}",
        extra_fields={"movie_id": movie_id, "language": option_language},
    )

    async with aiohttp.ClientSession() as session:
        # Get movie details from TMDB
        movie_url = (
            f"https://api.themoviedb.org/3/movie/{movie_id}?language={option_language}"
        )

        try:
            async with session.get(movie_url, headers=headers) as response:
                if response.status == 404:
                    raise NotFoundError(
                        f"Movie with ID {movie_id} not found", "Movie", movie_id
                    )
                elif response.status != 200:
                    raise ExternalAPIError(
                        f"TMDB API returned status {response.status}",
                        "TMDB API",
                        response.status,
                    )
                movie_data = await response.json()
        except aiohttp.ClientError as e:
            logger.error(
                "Network error fetching movie details",
                extra_fields={"movie_id": movie_id, "error": str(e)},
            )
            raise ExternalAPIError(f"Network error: {e!s}", "TMDB API")
        except Exception as e:
            if isinstance(e, (NotFoundError, ExternalAPIError)):
                raise
            logger.error(
                "Unexpected error fetching movie details",
                extra_fields={"movie_id": movie_id, "error": str(e)},
            )
            raise ExternalAPIError(f"Failed to fetch movie details: {e!s}", "TMDB API")

        # Check streaming availability
        url_to_check = f"https://vixsrc.to/movie/{movie_id}"
        try:
            is_available = await check_url_exists_async(session, url_to_check)
            logger.debug(
                f"Streaming availability check for movie {movie_id}",
                extra_fields={"movie_id": movie_id, "is_available": is_available},
            )
        except Exception as e:
            logger.warning(
                f"Failed to check streaming availability for movie {movie_id}",
                extra_fields={"movie_id": movie_id, "error": str(e)},
            )
            is_available = False

        poster = await display_movie_poster(movie_data)

        backdrop_path = None
        if movie_data.get("backdrop_path"):
            backdrop_path = (
                f"https://image.tmdb.org/t/p/original{movie_data['backdrop_path']}"
            )

        result = {
            "id": movie_data["id"],
            "url": url_to_check if is_available else None,
            "is_available": is_available,
            "original_title": movie_data["original_title"],
            "overview": movie_data["overview"],
            "release_date": movie_data["release_date"],
            "vote_average": movie_data["vote_average"],
            "vote_count": movie_data.get("vote_count", 0),
            "runtime": movie_data.get("runtime", 0),
            "genres": [genre["name"] for genre in movie_data.get("genres", [])],
            "poster": poster,
            "backdrop_path": backdrop_path,
            "budget": movie_data.get("budget", 0),
            "revenue": movie_data.get("revenue", 0),
            "status": movie_data.get("status", "Unknown"),
        }

        logger.info(
            "Movie details retrieved successfully",
            extra_fields={
                "movie_id": movie_id,
                "title": movie_data["original_title"],
                "is_available": is_available,
                "genres_count": len(result["genres"]),
            },
        )

        return result


async def fetch_movie_page(session, url, headers, page_num):
    """Fetch a single page of movie results."""
    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                logger.warning(
                    f"TMDB API returned status {response.status} for page {page_num}",
                    extra_fields={"page": page_num, "status": response.status},
                )
                return {"results": []}
            return await response.json()
    except Exception as e:
        logger.error(
            f"Failed to fetch movie page {page_num}",
            extra_fields={"page": page_num, "error": str(e)},
        )
        return {"results": []}


async def display_movie_poster(movie):
    """Get movie poster URL or placeholder."""
    if movie.get("poster_path"):
        return f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
    else:
        return "No poster found"
