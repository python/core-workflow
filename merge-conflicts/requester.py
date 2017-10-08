import json
import os
import textwrap
from string import Template

import requests

GH_TOKEN = os.getenv("GH_TOKEN")

query_template = Template(textwrap.dedent(
    r"""query {
      repository(owner: "$org", name: "$repo") {
        pullRequests($args states: OPEN) {
          edges {
            cursor
            node {
              number
              mergeable
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


def open_prs(organization, repo):
    query_args = "first:100,"
    while True:
        first_query = query_template.substitute(args=query_args, org=organization, repo=repo)
        response = requests.post('https://api.github.com/graphql', data=json.dumps({"query": first_query}),
                                 headers={"Authorization": f"bearer {GH_TOKEN}"})
        pull_requests = json.loads(response.content)["data"]["repository"]["pullRequests"]["edges"]
        if not pull_requests:
            return
        for pr in pull_requests:
            pr_info = pr["node"]
            pr_info["labels"] = {node["name"] for node in pr_info["labels"]["nodes"]}
            yield pr_info
        query_args = f'after: "{pull_requests[-1]["cursor"]}", first:100,'


def main():
    org = os.getenv("ORG")
    repo = os.getenv("REPO")
    pull_requests = open_prs(org, repo)
    conflicting_pull_requests = (pr for pr in pull_requests if pr["mergeable"] == 'CONFLICTING')
    needs_rebase_pull_request = (pr for pr in conflicting_pull_requests if "needs rebase" not in pr["labels"])

    for pr in needs_rebase_pull_request:
        requests.post(f'https://api.github.com/repos/{org}/{repo}/issues/{pr["number"]}/labels',
                      data=json.dumps(["needs rebase"]), headers={
                "Authorization": f"bearer {GH_TOKEN}"})


if __name__ == "__main__":
    main()
