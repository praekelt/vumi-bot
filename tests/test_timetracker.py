from datetime import datetime, timedelta

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from vumibot.timetracker import TimeTrackCommand
from vumibot.timetracker import BotWorker

class TimeTrackWorkerTestCase(ApplicationTestCase):

    application_class = BotWorker
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        super(TimeTrackWorkerTestCase, self).setUp()
        self.app = yield self.get_application({
            'worker_name': 'test_timetracker',
            'command_configs': {
                'time_tracker': {
                    'spreadsheet_name': 'some-spreadsheet',
                    'username': 'praekeltjenkins',
                    'password': '54trgfbv',
                    'validity': '10',
                }
            }
        })
        self.fake_redis = FakeRedis()
        self.app.r_server = self.fake_redis

        [tt_command] = self.app.get_commands(TimeTrackCommand)
        tt_command.r_server = self.fake_redis

        self.today = datetime.utcnow().date()
        self.yesterday = self.today - timedelta(days=1)

    @inlineCallbacks
    def tearDown(self):
        yield super(TimeTrackWorkerTestCase, self).tearDown()
        self.fake_redis.teardown()

    @inlineCallbacks
    def test_logging(self):
        msg = self.mkmsg_in(content='!log 4h vumibot, writing tests')
        yield self.dispatch(msg)
        [tt_command] = self.app.get_commands(TimeTrackCommand)
        [(key, data)] = tt_command.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(data, {
            'date': self.today.isoformat(),
            'time': str(4 * 60 * 60),
            'project': 'vumibot',
            'notes': 'writing tests',
        })

    @inlineCallbacks
    def test_named_backdating(self):
        msg = self.mkmsg_in(
            content='!log 4h@yesterday vumibot, writing tests')
        yield self.dispatch(msg)
        [tt_command] = self.app.get_commands(TimeTrackCommand)
        [(key, data)] = tt_command.spreadsheet.get_worksheet(msg.user())
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
        [tt_command] = self.app.get_commands(TimeTrackCommand)
        [(key, data)] = tt_command.spreadsheet.get_worksheet(msg.user())
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
        [tt_command] = self.app.get_commands(TimeTrackCommand)
        self.assertEqual(response['content'],
            '%s: that does not compute. %s' % (
                msg.user(), tt_command.get_help()))
        worksheet = tt_command.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(list(worksheet), [])

    @inlineCallbacks
    def test_bad_format(self):
        msg = self.mkmsg_in(content='!log 4h@2012-2-31 vumibot, writing tests')
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        [tt_command] = self.app.get_commands(TimeTrackCommand)
        self.assertEqual(response['content'],
            '%s: eep! day is out of range for month.' % (msg.user(),))
        worksheet = tt_command.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(list(worksheet), [])

    @inlineCallbacks
    def test_without_notes(self):
        msg = self.mkmsg_in(content='!log 4h vumibot')
        yield self.dispatch(msg)
        [tt_command] = self.app.get_commands(TimeTrackCommand)
        [(key, data)] = tt_command.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(data, {
            'date': self.today.isoformat(),
            'time': str(4 * 60 * 60),
            'project': 'vumibot',
            'notes': '',
        })

    # @inlineCallbacks
    # def test_dumping_of_data(self):
    #     users = ['tester 123', 'testing 345']
    #     for user in users:
    #         for i in range(0,10):
    #             msg = self.mkmsg_in(content='!log 4h vumibot, testing %s' % (i,),
    #                                 from_addr=user)
    #             yield self.dispatch(msg)

    #     [tt_command] = self.app.get_commands(TimeTrackCommand)
    #     response = yield tt_command.spreadsheet.publish()
    #     print response