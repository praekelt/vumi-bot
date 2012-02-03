# -*- test-case-name: tests.test_timetracker -*-

"""
Simple possible time tracker ever
"""

import re
from datetime import datetime, timedelta

from gdata.spreadsheet import service

from vumi.application import ApplicationWorker

class SpreadSheet(object):
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


class TimeTrackWorker(ApplicationWorker):

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
        self.spreadsheet = SpreadSheet(self.spreadsheet_name,
            username=self.username, password=self.password)
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
                    self.reply_to(message, 'Eep! %s.' % (e,))
        elif content.startswith(self.TT_COMMAND):
            self.reply_to(message, 'That does not compute.')
