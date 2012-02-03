from datetime import datetime, timedelta

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from vumibot.timetracker import TimeTrackWorker

class TestSpreadSheet(object):
    def __init__(self, name, username=None, password=None):
        self.name = name
        self.username = username
        self.password = password
        self._data = {}
        if self.username:
            self.authenticate()

    def authenticate(self):
        return True

    def add_row(self, worksheet, row):
        self._data.setdefault(worksheet, [])
        self._data[worksheet].append(row)

    def get_worksheet(self, worksheet):
        return self._data.setdefault(worksheet, [])

class TimeTrackWorkerTestCase(ApplicationTestCase):

    application_class = TimeTrackWorker
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        super(TimeTrackWorkerTestCase, self).setUp()
        self.app = yield self.get_application({
            'worker_name': 'test_timetracker',
            'spreadsheet_name': 'some-spreadsheet',
            'username': 'username',
            'password': 'password',
            'class_name': 'tests.test_timetracker.TestSpreadSheet',
        })
        self.app.r_server = FakeRedis()
        self.app.spreadsheet = TestSpreadSheet(
            self.app.spreadsheet_name,
            self.app.username, self.app.password)
        self.today = datetime.utcnow().date()
        self.yesterday = self.today - timedelta(days=1)

    def tearDown(self):
        self.app.r_server.teardown()

    @inlineCallbacks
    def test_logging(self):
        msg = self.mkmsg_in(content='!log 4h vumibot, writing tests')
        yield self.dispatch(msg)
        worksheet = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(worksheet, [{
            'date': self.today.isoformat(),
            'time': '4h',
            'project': 'vumibot',
            'notes': 'writing tests',
        }])

    @inlineCallbacks
    def test_named_backdating(self):
        msg = self.mkmsg_in(
            content='!log 4h@yesterday vumibot, writing tests')
        yield self.dispatch(msg)
        worksheet = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(worksheet, [{
            'date': self.yesterday.isoformat(),
            'time': '4h',
            'project': 'vumibot',
            'notes': 'writing tests',
        }])

    @inlineCallbacks
    def test_backdating(self):
        msg = self.mkmsg_in(
            content='!log 4h@2012-2-4 vumibot, writing tests')
        yield self.dispatch(msg)
        worksheet = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(worksheet, [{
            'date': '2012-02-04',
            'time': '4h',
            'project': 'vumibot',
            'notes': 'writing tests',
        }])

    @inlineCallbacks
    def test_bad_command(self):
        msg = self.mkmsg_in(content='!log foo bar baz')
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertEqual(response['content'],
            '%s: that does not compute. Format is %s' % (
                msg.user(), self.app.HELP))
        self.assertEqual(self.app.spreadsheet._data, {})

    @inlineCallbacks
    def test_bad_format(self):
        msg = self.mkmsg_in(content='!log 4h@2012-2-31 vumibot, writing tests')
        yield self.dispatch(msg)
        [response] = self.get_dispatched_messages()
        self.assertEqual(response['content'],
            '%s: eep! day is out of range for month.' % (msg.user(),))
        self.assertEqual(self.app.spreadsheet._data, {})

    @inlineCallbacks
    def test_without_notes(self):
        msg = self.mkmsg_in(content='!log 4h vumibot')
        yield self.dispatch(msg)
        worksheet = self.app.spreadsheet.get_worksheet(msg.user())
        self.assertEqual(worksheet, [{
            'date': self.today.isoformat(),
            'time': '4h',
            'project': 'vumibot',
            'notes': '',
        }])