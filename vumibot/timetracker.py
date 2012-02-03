# -*- test-case-name: tests.test_timetracker -*-

"""
Simple possible time tracker ever
"""

import re
from datetime import datetime, timedelta

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread

from gdata.spreadsheet import service
from gdata.service import CaptchaRequired

from vumi.utils import load_class_by_string
from vumi.application import ApplicationWorker

class GDocsError(Exception): pass

class GDocsSpreadSheet(object):
    def __init__(self, name, username=None, password=None,
                    captcha_token=None, captcha_response=None):
        self.name = name
        self.client = service.SpreadsheetsService()
        self.client.username = username
        self.client.password = password
        self.client.source = name
        self._worksheets = {}
        self.client.ProgrammaticLogin()
        self._spreadsheet_key = self._find_spreadsheet(self.client, self.name)

    def _find_spreadsheet(self, client, name):
        feed = client.GetSpreadsheetsFeed()
        for index, entry in enumerate(feed.entry):
            if entry.title.text == name:
                return entry.id.text.split('/',1)[1]
        raise GDocsError('Cannot find %s' % (name,))

    def _find_worksheet(self, client, spreadsheet_key, name):
        cache = self._worksheets.setdefault(spreadsheet_key, {})
        if name in cache:
            return cache.get(name)

        feed = client.GetWorksheetsFeed(spreadsheet_key)
        for index, entry in enumerate(feed.entry):
            if entry.title == name:
                worksheet_key = entry.id.text.spilt('/', 1)[1]
                cache[name] = worksheet_key
                return worksheet_key

        return self._make_worksheet(client, spreadsheet_key, name)

    def _make_worksheet(self, client, spreadsheet_key, name):
        pass

    def add_row(self, worksheet, row):
        self._data.setdefault(worksheet, [])
        self._data[worksheet].append(row)
        print 'adding'
        print row

    def get_worksheet(self, worksheet):
        return self._data.setdefault(worksheet, [])

class TimeTrackWorker(ApplicationWorker):

    HELP = "!log <amount><units> <project>, <notes>. " \
                        "Where units can be d,h,m. " \
                        "Backdate with `4h@yesterday` or `4h@yyyy-mm-dd`"
    TT_COMMAND = '!log'
    TT_FORMAT = r"""
        ^%s\s+                          # the command
        (?P<time>\d+[m,h,d])            # how many hours
        (@(?P<date>[a-z0-9\-]+))?       # back date 1 day at most
        \s+                             #
        (?P<project>[^,]+)              # column header
        (,\s)?                          #
        (?P<notes>.*)$                  # notes
        """ % TT_COMMAND

    def validate_config(self):
        self.spreadsheet_name = self.config['spreadsheet_name']
        self.username = self.config['username']
        self.password = self.config['password']
        cls_name = self.config.get('class_name')
        if cls_name:
            self.cls = load_class_by_string(cls_name)
        else:
            self.cls = GDocsSpreadSheet

    @inlineCallbacks
    def setup_application(self):
        self.spreadsheet = yield deferToThread(self.cls,
            self.spreadsheet_name,
            username=self.username,
            password=self.password)
        self.pattern = re.compile(self.TT_FORMAT, re.VERBOSE)

    def convert_date(self, named_date):
        if named_date=="yesterday":
            return datetime.utcnow().date() - timedelta(days=1)
        else:
            return datetime(*map(int, named_date.split('-'))).date()

    def consume_user_message(self, message):
        content = message['content']
        match = self.pattern.match(content)
        if match:
                results = match.groupdict()
                date = results['date']
                try:
                    results.update({
                        'date': (self.convert_date(date) if date
                                    else datetime.utcnow().date()).isoformat()
                    })
                    self.spreadsheet.add_row(message.user(), results)
                except (TypeError, ValueError), e:
                    self.reply_to(message, '%s: eep! %s.' % (
                        message['from_addr'], e))
        elif content.startswith(self.TT_COMMAND):
            self.reply_to(message,
                '%s: that does not compute. Format is %s' % (
                    message['from_addr'], self.HELP))
