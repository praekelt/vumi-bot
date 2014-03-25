import json
from pkg_resources import resource_stream

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import Protocol, Factory
from twisted.trial.unittest import TestCase

from vumi.tests.helpers import VumiTestCase

from tests.helpers import BotMessageProcessorHelper
from vumibot.github import GitHubAPI, GitHubMessageProcessor, extract_params


GITHUB_RESPONSES = json.load(
    resource_stream(__name__, 'github_responses.json'))


class GitHubHelpersTestCase(TestCase):
    def test_extract_params(self):
        self.assertEqual([], extract_params(""))
        self.assertEqual([], extract_params("foo"))
        self.assertEqual(["foo"], extract_params("%(foo)s"))
        self.assertEqual(["foo"], extract_params("%(foo)s %(foo)s"))
        self.assertEqual(["foo", "bar"], extract_params("%(foo)s %(bar)s"))
        self.assertEqual(
            ["foo", "bar"], extract_params("%(foo)s %(bar)s %(foo)s"))


class FakeHTTP(Protocol):
    def dataReceived(self, data):
        request_line, body = self.parse_request(data)
        response = self.handle_request(request_line, body)
        self.transport.write(response.encode('utf-8'))
        self.transport.loseConnection()

    def parse_request(self, data):
        headers, _, body = data.partition('\r\n\r\n')
        headers = headers.splitlines()
        request_line = headers.pop(0).rsplit(' ', 1)[0]
        return request_line, body

    def build_response(self, response_data):
        lines = ["HTTP/1.1 %s" % (response_data['response_code'],)]
        lines.extend(['', json.dumps(response_data['response_body'])])
        return '\r\n'.join(lines)

    def handle_request(self, request_line, body):
        response_data = GITHUB_RESPONSES.get(request_line)
        if not response_data:
            self.factory.testcase.fail(
                "Unexpected request: %s" % (request_line,))
        self.factory.testcase.assertEquals(response_data["request_body"],
                                           json.loads(body))
        return self.build_response(response_data)

    @classmethod
    def start_webserver(cls, testcase):
        factory = Factory()
        factory.protocol = cls
        factory.testcase = testcase
        webserver = reactor.listenTCP(0, factory, interface='127.0.0.1')
        testcase.add_cleanup(webserver.loseConnection)
        addr = webserver.getHost()
        webserver.url = "http://%s:%s/" % (addr.host, addr.port)
        return webserver


class GitHubAPITestCase(VumiTestCase):
    # I don't have a good way to test all of this stuff, so I'm just asserting
    # that we get the right size and shape of response.

    def setUp(self):
        self.fake_github = FakeHTTP.start_webserver(self)
        self.api = GitHubAPI("token", self.fake_github.url)

    def set_debug(self, debug=True, real_api=True):
        if real_api:
            self.api = GitHubAPI("token")
        self.api.DEBUG = debug

    @inlineCallbacks
    def test_list_pulls(self):
        resp = yield self.api.list_pulls('praekelt', 'vumi')
        self.assertIsInstance(resp, list)
        self.assertEqual(2, len(resp))

    @inlineCallbacks
    def test_get_pull(self):
        resp = yield self.api.get_pull('praekelt', 'vumi', '173')
        self.assertIsInstance(resp, dict)
        self.assertEqual(27, len(resp))

    @inlineCallbacks
    def test_get_issue(self):
        resp = yield self.api.get_issue('praekelt', 'vumi', '107')
        self.assertIsInstance(resp, dict)
        self.assertEqual(17, len(resp))


class GitHubWorkerTestCase(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.proc_helper = self.add_helper(
            BotMessageProcessorHelper(GitHubMessageProcessor))
        self.fake_github = FakeHTTP.start_webserver(self)

        self.proc = yield self.proc_helper.get_message_processor({
            'auth_token': 'tokentoken',
            'default_user': 'praekelt',
            'default_repo': 'vumi',
            'base_url': self.fake_github.url,
        })

    def get_response_content(self):
        return [m['content']
                for m in self.proc_helper.get_dispatched_outbound()]

    def assert_response_content(self, *responses):
        self.assertEqual(list(responses), self.get_response_content())

    def test_parse_repospec(self):
        parse = self.proc.parse_repospec
        self.assertEqual(('praekelt', 'vumi'), parse(None))
        self.assertEqual(('praekelt', 'vumi'), parse(''))
        self.assertEqual(('praekelt', 'vumi'), parse('vumi'))
        self.assertEqual(('praekelt', 'vumi-bot'), parse('vumi-bot'))
        self.assertEqual(('jerith', 'depixel'), parse('jerith/depixel'))
        self.assertEqual(('jerith', 'depixel'), parse('foo/jerith/depixel'))

    @inlineCallbacks
    def test_pulls(self):
        yield self.proc_helper.make_dispatch_inbound('!pulls', from_addr='dev')
        self.assert_response_content(
            'Found 2 pull requests for praekelt/vumi.',
            ('184: adding PingClientProtocol | unmerged | '
             'https://github.com/praekelt/vumi/pull/184'),
            ('173: Feature/issue 107 smpp split transport and '
             'client properly | unmerged | '
             'https://github.com/praekelt/vumi/pull/173'))

    @inlineCallbacks
    def test_pull(self):
        yield self.proc_helper.make_dispatch_inbound(
            '!pull 173', from_addr='dev')
        self.assert_response_content(
            ('173: Feature/issue 107 smpp split transport and '
             'client properly | unmerged | '
             'https://github.com/praekelt/vumi/pull/173'),
            ('created at: 2012-02-06T23:49:49Z | changed files: 19 '
             '| commits: 40 | comments: 7'))

    @inlineCallbacks
    def test_issue(self):
        yield self.proc_helper.make_dispatch_inbound(
            '!issue 107', from_addr='dev')
        self.assert_response_content(
            ('107: smpp split transport and client properly | '
             '\x02open\x02 | https://github.com/praekelt/vumi/issues/107'),
            ('created at: 2012-01-06T11:41:17Z | reporter: dmaclay | '
             'assigned: \x02nobody\x02 | comments: 0 | labels: Redis, SMPP'))
