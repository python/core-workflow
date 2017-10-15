import logging
import os

import gidgethub.routing

from .utils import get_open_prs

router = gidgethub.routing.Router()
logger = logging.getLogger(__name__)


@router.register("pull_request", action="closed")
async def label_conflicting_prs(event, gh, session, *args, **kwargs):
    pull_request = event.data["pull_request"]
    if pull_request["merged"] is False:
        return

    org = os.getenv("ORG")
    repo = os.getenv("REPO")
    pull_requests = get_open_prs(org, repo, session)
    conflicting_pull_requests = [pr async for pr in pull_requests if pr["mergeable"] == 'CONFLICTING']
    needs_rebase_pull_request = [pr for pr in conflicting_pull_requests if "needs rebase" not in pr["labels"]]

    logger.info(f"Identified a total of {len(needs_rebase_pull_request)} pull requests with merge conflicts")

    for pr in needs_rebase_pull_request:
        try:
            logger.debug(f"Working on pr {pr['number']}")
            await gh.post(f'https://api.github.com/repos/{org}/{repo}/issues/{pr["number"]}/labels',
                          data=["needs_rebase"])
        except Exception as e:
            logger.exception(e)
