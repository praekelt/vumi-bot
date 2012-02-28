# -*- test-case-name: tests.test_timetracker -*-

"""
Simplest possible time tracker ever
"""

import re
import time
import uuid
import csv
import json
import base64
import unicodedata
from StringIO import StringIO
from datetime import datetime, timedelta

import redis
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.utils import http_request_full
from vumi.transports.scheduler import Scheduler

from vumibot.base import BotWorker, botcommand


class RedisSpreadSheet(object):
    def __init__(self, r_server, r_prefix, username, password, validity=600):
        self.r_server = r_server
        self.r_prefix = r_prefix
        self.username = username
        self.password = password
        self.validity = validity
        self.worksheets_key = self.r_key('worksheets')
        self.gist_url = 'https://api.github.com/gists'
        self.gist_headers = {
            'Authorization': 'Basic %s' % (
                base64.b64encode('%s:%s' % (
                    self.username,
                    self.password,
                )),
            )
        }

        self.scheduler = Scheduler(self.r_server, self.gc_expired_documents,
            '%s:scheduler' % (self.r_prefix,))
        self.scheduler.start()
        self.gc_key = self.r_key('worksheets')

    def r_key(self, *args):
        return ':'.join([self.r_prefix] + map(unicode, args))

    def get_row_key(self, worksheet_name):
        return self.r_key(worksheet_name, 'rows')

    def get_column_key(self, worksheet_name, row_key):
        return self.r_key(worksheet_name, row_key, 'columns')

    def get_worksheets(self):
        return self.r_server.smembers(self.worksheets_key)

    def get_rows(self, worksheet_name):
        rows_key = self.get_row_key(worksheet_name)
        return self.r_server.zrange(rows_key, 0, -1)

    def add_row(self, worksheet_name, row):
        # add as a worksheet
        self.r_server.sadd(self.worksheets_key, worksheet_name)
        # timestamp for this row, used in ordering
        date = row['date']
        date_in_seconds = time.mktime(date.timetuple())
        # unique uuid for this row
        row_key = uuid.uuid4().hex
        # store row reference in order of timestamps
        worksheet_row_key = self.get_row_key(worksheet_name)
        self.r_server.zadd(worksheet_row_key, **{
            row_key: int(date_in_seconds)
        })
        return row_key, self.add_column(worksheet_name, row_key, row)

    def add_column(self, worksheet_name, row_key, data):
        # store column data
        worksheet_column_key = self.get_column_key(worksheet_name, row_key)
        data.update({
            'date': data['date'].isoformat(),
        })
        self.r_server.hmset(worksheet_column_key, data)
        return data

    def get_column(self, worksheet_name, row_key):
        worksheet_column_key = self.get_column_key(worksheet_name, row_key)
        return self.r_server.hgetall(worksheet_column_key)

    def get_worksheet(self, worksheet_name):
        rows = self.get_rows(worksheet_name)
        for row_key in rows:
            yield row_key, self.get_column(worksheet_name, row_key)

    def worksheet_to_filename(self, worksheet_name):
        # Shamelessly copied & modified from Django's
        # slugify default filter
        if isinstance(worksheet_name, unicode):
            worksheet_name = unicodedata.normalize('NFKD',
                                worksheet_name).encode('ascii', 'ignore')
        worksheet_name = unicode(re.sub('[^\w\s-]', '-',
                                worksheet_name).strip().lower())
        return re.sub('[-\s]+', '-', worksheet_name)

    def get_gist_payload(self):
        gist_payload = {
            "description": "TimeTrack report as of %s" % (
                                datetime.now().isoformat(),),
            "public": False,
        }
        worksheets = self.get_worksheets()
        for worksheet_name in worksheets:
            sio = StringIO()
            writer = csv.writer(sio)
            # write the header
            writer.writerow([
                "date",
                "project",
                "time",
                "notes",
            ])
            worksheet = self.get_worksheet(worksheet_name)
            for row_key, data in worksheet:
                writer.writerow([
                    data['date'],
                    data['project'],
                    data['time'],
                    data['notes'],
                ])

            files = gist_payload.setdefault('files', {})
            worksheet_filename = self.worksheet_to_filename(worksheet_name)
            files["%s.csv" % (worksheet_filename,)] = {
                "content": sio.getvalue(),
            }
        return gist_payload

    @inlineCallbacks
    def publish(self):
        gist_payload = self.get_gist_payload()
        response = yield http_request_full(
            self.gist_url,
            json.dumps(gist_payload), self.gist_headers)

        data = json.loads(response.delivered_body)
        html_url = data['html_url']
        url = data['url']
        self.scheduler.schedule(self.validity, url)
        returnValue(html_url)

    @inlineCallbacks
    def gc_expired_documents(self, scheduled_at, url):
        yield http_request_full(
            url.encode('utf8'), headers=self.gist_headers, method="DELETE")


class TimeTrackWorker(BotWorker):

    FEATURE_NAME = "time_tracker"

    def validate_config(self):
        self.r_config = self.config.get('redis_config', {})

    def setup_bot(self):
        self.r_server = redis.Redis(**self.r_config)

        self.spreadsheet_name = self.config['spreadsheet_name']
        self.username = self.config['username']
        self.password = self.config['password']
        self.validity = int(self.config['validity'])

        self.spreadsheet = RedisSpreadSheet(
            self.r_server,
            self.spreadsheet_name,
            username=self.username,
            password=self.password,
            validity=self.validity
        )

    def teardown_bot(self):
        if self.spreadsheet:
            self.spreadsheet.scheduler.stop()

    def convert_date(self, named_date):
        if named_date == "yesterday":
            return datetime.utcnow().date() - timedelta(days=1)
        else:
            return datetime(*map(int, named_date.split('-'))).date()

    def convert_time_unit(self, named_time):
        formatters = {
            'h': lambda v: int(v) * 60 * 60,
            'm': lambda v: int(v) * 60,
        }
        value, unit = named_time[0:-1], named_time[-1]
        return formatters.get(unit)(value)

    @botcommand(re.compile(r"""
        ^
        (?P<time>\d+[m,h])              # how many hours
        (@(?P<date>[a-z0-9\-]+))?       # back date 1 day at most
        \s+                             #
        (?P<project>[^,]+)              # column header
        (,\s)?                          #
        (?P<notes>.*)$                  # notes
        """, re.VERBOSE))
    def cmd_log(self, message, params, **results):
        ("Format is <amount><units> <project>, <notes>. "
         "Where units can be h,m. "
         "Backdate with `4h@yesterday` or `4h@yyyy-mm-dd`")

        date = results['date']
        time = results['time']
        results.update({
            'date': (self.convert_date(date) if date
                        else datetime.utcnow().date()),
            'time': self.convert_time_unit(time),
        })
        self.spreadsheet.add_row(message.user(), results)
        return "Logged, thanks."

    @botcommand
    @inlineCallbacks
    def cmd_publish(self, message, params):
        "Publish the latest time tracker stats as a multifile Gist"
        url = yield self.spreadsheet.publish()
        returnValue(url)
