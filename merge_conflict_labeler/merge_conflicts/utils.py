import json
import logging
import os
import textwrap
from string import Template

logger = logging.getLogger(__name__)

query_template = Template(textwrap.dedent(
    r"""query {
      repository(owner: "$org", name: "$repo") {
        pullRequests($args states: OPEN) {
          edges {
            cursor
            node {
              number
              url
              labels(first: 20) {
                nodes {
                  name
                }
              }
            }
          }
        }
      }
    }
    """
))


async def get_open_prs(organization, repo, session):
    gh_token = os.getenv("GH_AUTH")
    query_args = "first:100,"
    while True:
        first_query = query_template.substitute(args=query_args, org=organization, repo=repo)
        async with session.post(url='https://api.github.com/graphql',
                                data=json.dumps({"query": first_query}),
                                headers={"Authorization": f"bearer {gh_token}"}) as response:
            pull_requests = json.loads(await response.text())["data"]["repository"]["pullRequests"]["edges"]
        if not pull_requests:
            return
        for pr in pull_requests:
            pr_info = pr["node"]
            pr_info["labels"] = {node["name"] for node in pr_info["labels"]["nodes"]}
            yield pr_info
        query_args = f'after: "{pull_requests[-1]["cursor"]}", first:100,'
