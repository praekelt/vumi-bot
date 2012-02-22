import json
from pkg_resources import resource_stream

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import Protocol, Factory
from twisted.trial.unittest import TestCase

from vumi.application.tests.test_base import ApplicationTestCase

from vumibot.github import GitHubAPI, GitHubWorker, extract_params


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


class FakeHTTPTestCaseMixin(object):
    @inlineCallbacks
    def start_webserver(self):
        factory = Factory()
        factory.protocol = FakeHTTP
        factory.testcase = self
        self.webserver = yield reactor.listenTCP(0, factory)
        addr = self.webserver.getHost()
        self.url = "http://%s:%s/" % (addr.host, addr.port)

    def stop_webserver(self):
        return self.webserver.loseConnection()


class GitHubAPITestCase(TestCase, FakeHTTPTestCaseMixin):
    # I don't have a good way to test all of this stuff, so I'm just asserting
    # that we get the right size and shape of response.

    @inlineCallbacks
    def setUp(self):
        yield self.start_webserver()
        self.api = GitHubAPI("token", self.url)

    def tearDown(self):
        return self.stop_webserver()

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


class GitHubWorkerTestCase(ApplicationTestCase, FakeHTTPTestCaseMixin):

    application_class = GitHubWorker
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        yield super(GitHubWorkerTestCase, self).setUp()
        yield self.start_webserver()

        self.app = yield self.get_application({
                'worker_name': 'test_github',
                'github_auth_token': 'tokentoken',
                'github_default_user': 'praekelt',
                'github_default_repo': 'vumi',
                'github_base_url': self.url,
                })

    @inlineCallbacks
    def tearDown(self):
        yield super(GitHubWorkerTestCase, self).tearDown()
        yield self.stop_webserver()

    def get_response_content(self):
        return [m['content'] for m in self.get_dispatched_messages()]

    def assert_response_content(self, *responses):
        self.assertEqual(list(responses), self.get_response_content())

    def test_parse_repospec(self):
        parse = self.app.parse_repospec
        self.assertEqual(('praekelt', 'vumi'), parse(None))
        self.assertEqual(('praekelt', 'vumi'), parse(''))
        self.assertEqual(('praekelt', 'vumi'), parse('vumi'))
        self.assertEqual(('praekelt', 'vumi-bot'), parse('vumi-bot'))
        self.assertEqual(('jerith', 'depixel'), parse('jerith/depixel'))
        self.assertEqual(('jerith', 'depixel'), parse('foo/jerith/depixel'))

    @inlineCallbacks
    def test_pulls(self):
        msg = self.mkmsg_in(content='!pulls', from_addr='dev')
        yield self.dispatch(msg)
        self.assert_response_content(
            'Found 2 pull requests for praekelt/vumi.',
            ('184: adding PingClientProtocol | unmerged | '
             'https://github.com/praekelt/vumi/pull/184'),
            ('173: Feature/issue 107 smpp split transport and '
             'client properly | unmerged | '
             'https://github.com/praekelt/vumi/pull/173'))

    @inlineCallbacks
    def test_pull(self):
        msg = self.mkmsg_in(content='!pull 173', from_addr='dev')
        yield self.dispatch(msg)
        self.assert_response_content(
            ('173: Feature/issue 107 smpp split transport and '
             'client properly | unmerged | '
             'https://github.com/praekelt/vumi/pull/173'),
            ('created at: 2012-02-06T23:49:49Z | changed files: 19 '
             '| commits: 40 | comments: 7'))

    @inlineCallbacks
    def test_issue(self):
        msg = self.mkmsg_in(content='!issue 107', from_addr='dev')
        yield self.dispatch(msg)
        self.assert_response_content(
            ('107: smpp split transport and client properly | '
             '\x02open\x02 | https://github.com/praekelt/vumi/issues/107'),
            ('created at: 2012-01-06T11:41:17Z | reporter: dmaclay | '
             'assigned: \x02nobody\x02 | comments: 0 | labels: Redis, SMPP'))
