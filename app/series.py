import requests
import aiohttp
import asyncio
from app.utils import check_url_exists, check_url_exists_async, check_season_episodes_async
from app.logger import get_logger
from app.errors import ExternalAPIError, NotFoundError, StreamingAvailabilityError

# Get logger instance
logger = get_logger("series")

async def search_series(text_search, option_language, headers):
    """Quick search that returns basic series information without checking streaming availability."""
    series_list = []
    
    logger.info(
        f"Starting series search for: '{text_search}'",
        extra_fields={"search_query": text_search, "language": option_language}
    )
    
    # Create aiohttp session for concurrent requests
    async with aiohttp.ClientSession() as session:
        # Search through first 3 pages concurrently
        tasks = []
        for page in range(1, 4):
            url_stream = f"https://api.themoviedb.org/3/search/tv?query={text_search}&include_adult=false&language={option_language}&page={page}"
            tasks.append(fetch_series_page(session, url_stream, headers, page))
        
        # Execute all page requests concurrently
        page_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process all series from all pages - only basic info
        for page_num, page_data in enumerate(page_results, 1):
            if isinstance(page_data, Exception):
                logger.error(
                    f"Failed to fetch page {page_num}",
                    extra_fields={
                        "page": page_num,
                        "error": str(page_data),
                        "error_type": type(page_data).__name__
                    }
                )
                continue
                
            if isinstance(page_data, dict) and page_data.get("results"):
                logger.debug(
                    f"Processing page {page_num} with {len(page_data['results'])} series",
                    extra_fields={"page": page_num, "series_count": len(page_data["results"])}
                )
                
                for series in page_data["results"]:
                    poster = await display_series_poster(series)
                    name, air_date, vote_avg, overview = await display_series_info(series)
                    series_list.append({
                        "id": series["id"],
                        "name": name,
                        "air_date": air_date,
                        "vote_avg": vote_avg,
                        "overview": overview,
                        "poster": poster
                    })
    
    logger.info(
        f"Series search completed: {len(series_list)} series found",
        extra_fields={"total_series": len(series_list), "search_query": text_search}
    )
    
    if series_list:
        return series_list
    else:
        return []

async def get_series_details(series_id, option_language, headers):
    """Get detailed series information including streaming availability check."""
    logger.info(
        f"Getting details for series ID: {series_id}",
        extra_fields={"series_id": series_id, "language": option_language}
    )
    
    async with aiohttp.ClientSession() as session:
        # Get series details from TMDB
        series_url = f"https://api.themoviedb.org/3/tv/{series_id}?language={option_language}"
        
        try:
            async with session.get(series_url, headers=headers) as response:
                if response.status == 404:
                    raise NotFoundError(f"Series with ID {series_id} not found", "Series", series_id)
                elif response.status != 200:
                    raise ExternalAPIError(
                        f"TMDB API returned status {response.status}",
                        "TMDB API",
                        response.status
                    )
                series_data = await response.json()
        except aiohttp.ClientError as e:
            logger.error(
                f"Network error fetching series details",
                extra_fields={"series_id": series_id, "error": str(e)}
            )
            raise ExternalAPIError(f"Network error: {str(e)}", "TMDB API")
        except Exception as e:
            if isinstance(e, (NotFoundError, ExternalAPIError)):
                raise
            logger.error(
                f"Unexpected error fetching series details",
                extra_fields={"series_id": series_id, "error": str(e)}
            )
            raise ExternalAPIError(f"Failed to fetch series details: {str(e)}", "TMDB API")
        
        # Check streaming availability and get episode information
        try:
            valid_seasons, valid_episodes, streaming_urls = await search_series_data_async(session, series_data, option_language, headers)
            logger.debug(
                f"Streaming availability check for series {series_id}",
                extra_fields={
                    "series_id": series_id,
                    "valid_seasons": len(valid_seasons),
                    "total_episodes": len(streaming_urls)
                }
            )
        except Exception as e:
            logger.warning(
                f"Failed to check streaming availability for series {series_id}",
                extra_fields={"series_id": series_id, "error": str(e)}
            )
            valid_seasons, valid_episodes, streaming_urls = [], {}, []
        
        poster = await display_series_poster(series_data)
        name, air_date, vote_avg, overview = await display_series_info(series_data)
        
        result = {
            "id": series_data["id"],
            "name": name,
            "air_date": air_date,
            "vote_avg": vote_avg,
            "overview": overview,
            "poster": poster,
            "is_available": len(valid_seasons) > 0,
            "valid_seasons": valid_seasons,
            "valid_episodes": valid_episodes,
            "streaming_urls": streaming_urls,
            "number_of_seasons": series_data.get("number_of_seasons", 0),
            "number_of_episodes": series_data.get("number_of_episodes", 0),
            "status": series_data.get("status", "Unknown"),
            "genres": [genre["name"] for genre in series_data.get("genres", [])],
            "backdrop_path": f"https://image.tmdb.org/t/p/original{series_data['backdrop_path']}" if series_data.get("backdrop_path") else None,
            "first_air_date": series_data.get("first_air_date", "Unknown"),
            "last_air_date": series_data.get("last_air_date", "Unknown"),
            "vote_count": series_data.get("vote_count", 0),
            "popularity": series_data.get("popularity", 0)
        }
        
        logger.info(
            f"Series details retrieved successfully",
            extra_fields={
                "series_id": series_id,
                "name": name,
                "is_available": result["is_available"],
                "seasons_count": len(valid_seasons),
                "episodes_count": len(streaming_urls),
                "genres_count": len(result["genres"])
            }
        )
        
        return result

async def fetch_series_page(session, url, headers, page_num):
    """Fetch a single page of series results"""
    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                logger.warning(
                    f"TMDB API returned status {response.status} for page {page_num}",
                    extra_fields={"page": page_num, "status": response.status}
                )
                return {"results": []}
            return await response.json()
    except Exception as e:
        logger.error(
            f"Failed to fetch series page {page_num}",
            extra_fields={"page": page_num, "error": str(e)}
        )
        return {"results": []}

async def search_series_data_async(session, series, option_language, headers):       
    url_to_check = f"https://vixsrc.to/tv/{series['id']}/1/1"
    
    try:
        is_available = await check_url_exists_async(session, url_to_check)
        if not is_available:
            logger.debug(
                f"Series {series['id']} not available for streaming",
                extra_fields={"series_id": series["id"]}
            )
            return [], {}, []
    except Exception as e:
        logger.warning(
            f"Failed to check initial streaming availability for series {series['id']}",
            extra_fields={"series_id": series["id"], "error": str(e)}
        )
        return [], {}, []
    
    series_id = series["id"]
    total_seasons = min(series.get("number_of_seasons", 0), 10)
    
    logger.debug(
        f"Checking {total_seasons} seasons for series {series_id}",
        extra_fields={"series_id": series_id, "total_seasons": total_seasons}
    )
    
    valid_seasons = []
    valid_episodes = {}
    streaming_urls = []
    
    # Check seasons concurrently
    season_tasks = []
    for season in range(1, total_seasons + 1):
        season_tasks.append(check_season_episodes_async(session, series_id, season))
    
    season_results = await asyncio.gather(*season_tasks, return_exceptions=True)
    
    for season, episodes in enumerate(season_results, 1):
        if isinstance(episodes, Exception):
            logger.warning(
                f"Failed to check season {season} for series {series_id}",
                extra_fields={"series_id": series_id, "season": season, "error": str(episodes)}
            )
            continue
            
        if episodes and isinstance(episodes, list):
            valid_seasons.append(season)
            valid_episodes[season] = episodes
            # Add streaming URLs for this season
            for episode in episodes:
                streaming_urls.append(f"https://vixsrc.to/tv/{series_id}/{season}/{episode}")
            
            logger.debug(
                f"Season {season} has {len(episodes)} episodes",
                extra_fields={"series_id": series_id, "season": season, "episodes_count": len(episodes)}
            )
    
    logger.info(
        f"Series {series_id} streaming check completed",
        extra_fields={
            "series_id": series_id,
            "valid_seasons": len(valid_seasons),
            "total_episodes": len(streaming_urls)
        }
    )
    
    return valid_seasons, valid_episodes, streaming_urls

async def display_series_poster(series):
    if series.get("poster_path"):
        return f"https://image.tmdb.org/t/p/w500{series['poster_path']}"
    else:
        return "https://via.placeholder.com/200x300.png?text=No+Poster"

async def display_series_info(series):
    name = series['original_name']
    air_date = series.get('first_air_date', 'N/A')
    vote_avg = series.get('vote_average', 0)
    overview = series.get('overview', 'No overview available.')
    return name, air_date, vote_avg, overview

