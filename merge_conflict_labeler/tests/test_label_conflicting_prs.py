import unittest.mock as mock

import pytest
from asynctest import patch
from merge_conflicts.merge_conflicts import label_conflicting_prs

from .testing_utils import generate


@pytest.mark.asyncio
async def test_labeled_pr():
    # GIVEN
    gh = mock.Mock()
    session = mock.Mock()
    pr = mock.Mock()
    pr.data = {"pull_request": {"merged": True}}

    # WHEN
    with patch("merge_conflicts.merge_conflicts.get_open_prs") as get_open_prs_mock:
        get_open_prs_mock.return_value = generate(
            [{"number": 2, "mergeable": "CONFLICTING", "labels": ["needs rebase"]}])
        await label_conflicting_prs(pr, gh, session)

    # THEN
    assert gh.post.call_count == 0


@pytest.mark.asyncio
async def test_unlabeled():
    # GIVEN
    gh = mock.Mock()
    session = mock.Mock()
    pr = mock.Mock()
    pr.data = {"pull_request": {"merged": True}}

    # WHEN
    with patch("merge_conflicts.merge_conflicts.get_open_prs") as get_open_prs_mock:
        get_open_prs_mock.return_value = generate([{"number": 2, "mergeable": "CONFLICTING", "labels": []}])
        await label_conflicting_prs(pr, gh, session)

    # THEN
    assert gh.post.call_count == 1


@pytest.mark.asyncio
async def test_label_creation():
    # GIVEN
    gh = mock.Mock()
    session = mock.Mock()
    pr = mock.Mock()
    pr.data = {"pull_request": {"merged": True}}

    prs = [
        {"number": 1, "mergeable": "CONFLICTING", "labels": []},
        {"number": 2, "mergeable": "CONFLICTING", "labels": []},
        {"number": 3, "mergeable": "CONFLICTING", "labels": ["needs rebase"]},
        {"number": 4, "mergeable": "CONFLICTING", "labels": []},
    ]

    # WHEN
    with patch("merge_conflicts.merge_conflicts.get_open_prs") as get_open_prs_mock:
        get_open_prs_mock.return_value = generate(prs)
        await label_conflicting_prs(pr, gh, session)

    # THEN
    expected_calls = [
        mock.call('https://api.github.com/repos/None/None/issues/1/labels', data=['needs_rebase']),
        mock.call('https://api.github.com/repos/None/None/issues/2/labels', data=['needs_rebase']),
        mock.call('https://api.github.com/repos/None/None/issues/4/labels', data=['needs_rebase'])
    ]

    assert gh.post.mock_calls == expected_calls
