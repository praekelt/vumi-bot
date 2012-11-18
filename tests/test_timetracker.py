# -*- coding: utf-8 -*-
import json

from datetime import datetime, timedelta

from twisted.internet.defer import inlineCallbacks
from twisted.web.resource import Resource
from twisted.internet import reactor
from twisted.web.server import Site

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from vumibot.timetracker import TimeTrackWorker


class GistResource(Resource):

    isLeaf = True

    def render_POST(self, request):
        self.captured_post_data = request.content.read()
        return json.dumps({
            'html_url': 'http://web.localhost/id',
            'url': 'http://api.localhost/id',
        })


class TimeTrackWorkerTestCase(ApplicationTestCase):

    application_class = TimeTrackWorker
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        super(TimeTrackWorkerTestCase, self).setUp()

        self.gist_resource = GistResource()
        gist_factory = Site(self.gist_resource)
        self.gist_server = yield reactor.listenTCP(0, gist_factory)
        addr = self.gist_server.getHost()
        self.server_url = "http://%s:%s/" % (addr.host, addr.port)

        self.fake_redis = FakeRedis()
        self.patch(TimeTrackWorker, 'get_redis',
            lambda x: self.fake_redis)

        self.app = yield self.get_application({
            'worker_name': 'test_timetracker',
            'spreadsheet_name': 'some-spreadsheet',
            'username': 'some-user',
            'password': 'some-password',
            'validity': '10',
            })

        self.app.spreadsheet.r_server = self.fake_redis
        self.app.spreadsheet.gist_url = self.server_url

        self.today = datetime.utcnow().date()
        self.yesterday = self.today - timedelta(days=1)

    @inlineCallbacks
    def tearDown(self):
        yield super(TimeTrackWorkerTestCase, self).tearDown()
        self.fake_redis.teardown()
        yield self.gist_server.loseConnection()

    @inlineCallbacks
    def test_logging(self):
        msg = self.mkmsg_in(content='!log 4h vumibot, writing tests')
        yield self.dispatch(msg)
        [(key, data)] = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(data, {
            'date': self.today.isoformat(),
            'time': str(4 * 60 * 60),
            'project': 'vumibot',
            'notes': 'writing tests',
        })

        # This should probably be in its own test.
        # We use a different queue name so that we can have multiple workers
        # listening to the same routing key.
        self.assertTrue("sphex.inbound.time_tracker" in self._amqp.queues)
        self.assertTrue("sphex.inbound" not in self._amqp.queues)

    @inlineCallbacks
    def test_named_backdating(self):
        msg = self.mkmsg_in(
            content='!log 4h@yesterday vumibot, writing tests')
        yield self.dispatch(msg)
        [(key, data)] = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(data, {
            'date': self.yesterday.isoformat(),
            'time': str(4 * 60 * 60),
            'project': 'vumibot',
            'notes': 'writing tests',
        })

    @inlineCallbacks
    def test_backdating(self):
        msg = self.mkmsg_in(
            content='!log 4h@2012-2-4 vumibot, writing tests')
        yield self.dispatch(msg)
        [(key, data)] = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(data, {
            'date': '2012-02-04',
            'time': str(4 * 60 * 60),
            'project': 'vumibot',
            'notes': 'writing tests',
        })

    @inlineCallbacks
    def test_bad_command(self):
        msg = self.mkmsg_in(content='!log foo bar baz')
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertEqual(response['content'],
            'that does not compute. %s' % (
                self.app.cmd_log.__doc__))
        worksheet = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(list(worksheet), [])

    @inlineCallbacks
    def test_bad_format(self):
        msg = self.mkmsg_in(content='!log 4h@2012-2-31 vumibot, writing tests')
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertEqual(
            response['content'],
            'eep! ValueError: day is out of range for month.')
        worksheet = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(list(worksheet), [])
        self.flushLoggedErrors()

    @inlineCallbacks
    def test_without_notes(self):
        msg = self.mkmsg_in(content='!log 4h vumibot')
        yield self.dispatch(msg)
        [(key, data)] = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(data, {
            'date': self.today.isoformat(),
            'time': str(4 * 60 * 60),
            'project': 'vumibot',
            'notes': '',
        })

    @inlineCallbacks
    def test_publish(self):
        msg = self.mkmsg_in(content='!publish')
        yield self.dispatch(msg)
        posted_data = json.loads(self.gist_resource.captured_post_data)
        self.assertTrue("description" in posted_data)
        self.assertFalse(posted_data["public"])

    @inlineCallbacks
    def test_file_name_generation(self):
        msg1 = self.mkmsg_in(content='!log 4h vumibot',
                from_addr='jïd@domain.net/resource')
        msg2 = self.mkmsg_in(content='!publish',
                from_addr='jïd@domain.net/resource')
        yield self.dispatch(msg1)
        yield self.dispatch(msg2)
        posted_data = json.loads(self.gist_resource.captured_post_data)
        files = posted_data['files']
        self.assertEqual(files.keys(), [
            'jid-domain-net-resource.csv'
        ])

    @inlineCallbacks
    def test_dumping_of_data(self):
        users = ['tester 123', 'testing 345']
        for user in users:
            for i in range(0, 10):
                msg = self.mkmsg_in(
                    content='!log 4h vumibot, testing %s' % (i,),
                    from_addr=user)
                yield self.dispatch(msg)

        response = yield self.app.spreadsheet.publish()
        self.assertEqual(response, 'http://web.localhost/id')
        posted_payload = json.loads(self.gist_resource.captured_post_data)
        self.assertEqual(posted_payload['files'],
            self.app.spreadsheet.get_gist_payload()['files'])
