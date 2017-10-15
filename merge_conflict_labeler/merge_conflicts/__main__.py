import asyncio
import os
import sys
import traceback

import aiohttp
import cachetools
from aiohttp import web
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing
from gidgethub import sansio

from . import merge_conflicts

router = routing.Router(merge_conflicts.router)
cache = cachetools.LRUCache(maxsize=500)


async def main(request):
    try:
        body = await request.read()
        secret = os.environ.get("GH_SECRET")
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        print('GH delivery ID', event.delivery_id, file=sys.stderr)
        if event.event == "ping":
            return web.Response(status=200)
        asyncio.ensure_future(identify_merge_conflicting_prs(event))

        print("Answering")
        return web.Response(status=200)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


async def identify_merge_conflicting_prs(event):
    oauth_token = os.environ.get("GH_AUTH")
    async with aiohttp.ClientSession() as session:
        gh = gh_aiohttp.GitHubAPI(session, "pablogsal",
                                  oauth_token=oauth_token,
                                  cache=cache)
        await router.dispatch(event, gh, session)
    try:
        print('GH requests remaining:', gh.rate_limit.remaining)
    except AttributeError:
        pass


if __name__ == "__main__":  # pragma: no cover
    app = web.Application()
    app.router.add_post("/", main)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)
    web.run_app(app, port=port)
