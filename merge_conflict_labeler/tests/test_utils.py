import textwrap
import unittest.mock as mock

import pytest
from merge_conflicts.utils import get_open_prs

from .testing_utils import AsyncContextManagerMock, get_back


@pytest.mark.asyncio
async def test_get_open_prs():
    # GIVEN
    session = mock.Mock()
    response = mock.Mock()
    post_mock = AsyncContextManagerMock(return_item=response)
    session.post.return_value = post_mock
    response.text.side_effect = [
        get_back(textwrap.dedent("""
        {
          "data": {
            "repository": {
              "pullRequests": {
                "edges": [
                  {
                    "cursor": "Y3Vyc29yOnYyOpHOBk4feQ==",
                    "node": {
                      "number": 45,
                      "url": "https://github.com/python/cpython/pull/45",
                      "labels": {
                        "nodes": [
                          {
                            "name": "CLA signed"
                          },
                          {
                            "name": "type-documentation"
                          }
                        ]
                      }
                    }
                  },
                  {
                    "cursor": "Y3Vyc29yOnYyOpHOBk6OZw==",
                    "node": {
                      "number": 57,
                      "url": "https://github.com/python/cpython/pull/57",
                      "labels": {
                        "nodes": [
                          {
                            "name": "CLA signed"
                          }
                        ]
                      }
                    }
                  }
                ]
              }
            }
          }
        }""")),
        get_back(textwrap.dedent("""
        {
          "data": {
            "repository": {
              "pullRequests": {
                "edges": []
              }
            }
          }
        }
        """))]

    # WHEN

    response = [pr async for pr in get_open_prs("Python", "cpython", session)]

    # THEN

    expected_response = [{'number': 45, 'url': 'https://github.com/python/cpython/pull/45',
                          'labels': {'type-documentation', 'CLA signed'}},
                         {'number': 57, 'url': 'https://github.com/python/cpython/pull/57',
                          'labels': {'CLA signed'}}]

    assert response == expected_response
