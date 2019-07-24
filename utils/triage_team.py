# One time script for creating the triage team, and adding the necessary repos to the team

import os
import asyncio
import aiohttp

from gidgethub.aiohttp import GitHubAPI

import cachetools

cache = cachetools.LRUCache(maxsize=500)


async def get_core_repos(gh, team_id):
    """
    Return the team's public repos
    """
    async for repo in gh.getiter(f"/teams/{team_id}/repos"):
        if not repo["private"] and not repo["fork"]:
            print(repo)
            yield repo["full_name"]


async def get_team(gh, team_name):
    """
    Get a team by name (slug)
    """
    return await gh.getitem(f"/orgs/python/teams/{team_name}")


async def main():
    """
    - Get Python core team
    - Get Python core's public repos
    - Create Python triage team, assign the repos
    :return:
    """
    async with aiohttp.ClientSession() as session:
        # must have repo, and admin:org permissions
        gh = GitHubAPI(session, "python", oauth_token=os.getenv("GH_AUTH"), cache=cache)
        core_team = await get_team(gh, "python-core")
        repo_names = [repo async for repo in get_core_repos(gh, core_team["id"])]
        await gh.post(
            "/orgs/python/teams",
            data={
                "name": "Python triage",
                "description": "Triagers for core Python",
                "maintainers": "mariatta",
                "privacy": "closed",
                "repo_names": repo_names,
            },
        )


asyncio.run(main())
