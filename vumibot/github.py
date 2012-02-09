# -*- test-case-name: tests.test_github -*-

"""
Github informational utilities
"""

import json

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.utils import http_request_full

from vumibot.base import BotWorker, botcommand


class GitHubAPI(object):
    URL_BASE = "https://api.github.com/"

    def __init__(self, auth_token):
        self.auth_token = auth_token

    def _call_api(self, path, data=None, method='GET'):
        url = "%s%s" % (self.URL_BASE, path)
        if isinstance(url, unicode):
            url = url.encode('utf-8')
        headers = {
            'User-Agent': "vumibot",
            'Authorization': "bearer %s" % (self.auth_token,),
            }
        d = http_request_full(
            url, json.dumps(data), headers, method)
        return d.addCallback(self._parse_response)

    def _parse_response(self, response):
        return json.loads(response.delivered_body)

    @inlineCallbacks
    def list_pulls(self, user, repo):
        resp = yield self._call_api("repos/%(user)s/%(repo)s/pulls" % {
                'user': user, 'repo': repo})
        returnValue(resp)

    @inlineCallbacks
    def get_pull(self, user, repo, pull):
        url = "repos/%(user)s/%(repo)s/pulls/%(pull)s" % {
            'user': user, 'repo': repo, 'pull': pull}
        resp = yield self._call_api(url)
        returnValue(resp)


class GitHubWorker(BotWorker):
    FEATURE_NAME = "github"

    def setup_bot(self):
        self.github = GitHubAPI(self.config['github_auth_token'])
        self.default_user = self.config['github_default_user']
        self.default_repo = self.config['github_default_repo']

    def parse_repospec(self, repospec):
        user, repo = ([''] + (repospec or '').split('/'))[-2:]
        if not user:
            user = self.default_user
        if not repo:
            repo = self.default_repo
        return user, repo

    def format_pull_short(self, raw_pull):
        return "%(number)s: %(title)s | %(url)s" % raw_pull

    def format_pull(self, raw_pull):
        return [
            "%(number)s: %(title)s | %(url)s" % raw_pull,
            " | ".join([
                    "\x02merged\x02" if raw_pull['merged'] else "unmerged",
                    "created at: %(created_at)s",
                    "changed files: %(changed_files)s",
                    "commits: %(commits)s",
                    "comments: %(review_comments)s",
                    ]) % raw_pull,
            ]

    @botcommand(r'(?P<repospec>\S*)')
    @inlineCallbacks
    def cmd_pulls(self, message, params, repospec):
        user, repo = self.parse_repospec(repospec)
        raw_pulls = yield self.github.list_pulls(user, repo)

        replies = ["Found %s pull requests found for %s/%s." % (
                len(raw_pulls), user, repo)]
        if raw_pulls:
            replies.extend([self.format_pull_short(pull)
                            for pull in raw_pulls])
        returnValue(replies)

    @botcommand(r'^(?:(?P<repospec>\S+)\s+)?(?P<pull_num>\d+)$')
    @inlineCallbacks
    def cmd_pull(self, message, params, repospec, pull_num):
        user, repo = self.parse_repospec(repospec)
        raw_pull = yield self.github.get_pull(user, repo, pull_num)
        print raw_pull.get('message')
        if raw_pull.get('message') == 'Not Found':
            returnValue("Sorry, I can't seem to find that in %s/%s." % (
                    user, repo))
        returnValue(self.format_pull(raw_pull))
