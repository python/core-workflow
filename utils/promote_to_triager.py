# One time script for promoting to the triage team.
# The next iteration better be a bot!
# pip install gidgethub aiohttp cachetools

import os
import asyncio
import aiohttp

from gidgethub.aiohttp import GitHubAPI

import cachetools

cache = cachetools.LRUCache(maxsize=500)

async def get_team(gh, team_name):
    """
    Get a team by name (slug)
    """
    return await gh.getitem(f"/orgs/python/teams/{team_name}")

async def add_to_team(gh, username, team_id):
    await gh.put(f"/teams/{team_id}/memberships/{username}")


async def main():
    """
    - Get Python triage team
    - Add people to Python Triage team
    :return:
    """
    async with aiohttp.ClientSession() as session:
        # must have repo, and admin:org permissions
        gh = GitHubAPI(session, "python", oauth_token=os.getenv("GH_AUTH"), cache=cache)
        triage_team = await get_team(gh, "python-triage")
        response = await add_to_team(gh, "maxking", triage_team["id"])

asyncio.run(main())
