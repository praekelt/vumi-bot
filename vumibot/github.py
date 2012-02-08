# -*- test-case-name: tests.test_github -*-

"""
Github informational utilities
"""

import json

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.utils import http_request_full

from vumibot.base import BotCommand, BotWorker


class GitHubAPI(object):
    URL_BASE = "https://api.github.com/"

    def __init__(self, auth_token):
        self.auth_token = auth_token

    def _call_api(self, path, data=None, method='GET'):
        headers = {
            'User-Agent': "vumibot",
            'Authorization': "bearer %s" % (self.auth_token,),
            }
        d = http_request_full(
            "%s%s" % (self.URL_BASE, path), json.dumps(data), headers, method)
        return d.addCallback(self._parse_response)

    def _parse_response(self, response):
        return json.loads(response.delivered_body)

    @inlineCallbacks
    def list_pulls(self, user, repo):
        resp = yield self._call_api("repos/%(user)s/%(repo)s/pulls")
        returnValue(resp)


class IssuesCommand(BotCommand):
    pass


class PullsCommand(BotCommand):
    pass


class GitHubWorker(BotWorker):

    COMMANDS = (
        IssuesCommand,
        PullsCommand,
        )
    FEATURE_NAME = "time_tracker"
