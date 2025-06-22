"""Utility functions for URL checking and episode validation."""

import asyncio
import concurrent.futures

import aiohttp
import requests


def check_url_exists(url):
    """Check if a URL exists and returns 200 status code."""
    try:
        response = requests.get(url, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False


async def check_url_exists_async(session, url):
    """Check if a URL exists asynchronously and returns 200 status code."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
            return response.status == 200
    except Exception:
        return False


def check_season_episodes(series_id, season, max_episodes=20):
    """Check which episodes exist for a given season."""
    valid_episodes = []
    first_episode_url = f"https://vixsrc.to/tv/{series_id}/{season}/1"
    if not check_url_exists(first_episode_url):
        return []

    episode_urls = [
        f"https://vixsrc.to/tv/{series_id}/{season}/{ep}"
        for ep in range(1, max_episodes + 1)
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_episode = {
            executor.submit(check_url_exists, url): i + 1
            for i, url in enumerate(episode_urls)
        }
        for future in concurrent.futures.as_completed(future_to_episode):
            episode_num = future_to_episode[future]
            if future.result():
                valid_episodes.append(episode_num)
    return sorted(valid_episodes)


async def check_season_episodes_async(session, series_id, season, max_episodes=20):
    """Check which episodes exist for a given season asynchronously."""
    valid_episodes = []
    first_episode_url = f"https://vixsrc.to/tv/{series_id}/{season}/1"
    if not await check_url_exists_async(session, first_episode_url):
        return []

    episode_urls = [
        f"https://vixsrc.to/tv/{series_id}/{season}/{ep}"
        for ep in range(1, max_episodes + 1)
    ]
    tasks = [check_url_exists_async(session, url) for url in episode_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        if result is True:
            valid_episodes.append(i + 1)
    return sorted(valid_episodes)
