# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest


class TestConnection(unittest.TestCase):

    PROJECT = 'project'
    FILTER = 'logName:syslog AND severity>=ERROR'

    @staticmethod
    def _get_target_class():
        from google.cloud.logging._http import Connection
        return Connection

    def _make_one(self, *args, **kw):
        return self._get_target_class()(*args, **kw)

    def test_default_url(self):
        creds = _Credentials()
        conn = self._make_one(creds)
        klass = self._get_target_class()
        self.assertEqual(conn.credentials._scopes, klass.SCOPE)


class Test_LoggingAPI(unittest.TestCase):

    PROJECT = 'project'
    LIST_ENTRIES_PATH = 'entries:list'
    WRITE_ENTRIES_PATH = 'entries:write'
    LOGGER_NAME = 'LOGGER_NAME'
    FILTER = 'logName:syslog AND severity>=ERROR'

    @staticmethod
    def _get_target_class():
        from google.cloud.logging._http import _LoggingAPI
        return _LoggingAPI

    def _make_one(self, *args, **kw):
        return self._get_target_class()(*args, **kw)

    def test_ctor(self):
        connection = object()
        client = _Client(connection)
        api = self._make_one(client)
        self.assertIs(api._connection, connection)
        self.assertIs(api._client, client)

    @staticmethod
    def _make_timestamp():
        import datetime
        from google.cloud._helpers import UTC

        NOW = datetime.datetime.utcnow().replace(tzinfo=UTC)
        return NOW, _datetime_to_rfc3339_w_nanos(NOW)

    def test_list_entries_no_paging(self):
        import six
        from google.cloud.logging.client import Client
        from google.cloud.logging.entries import TextEntry
        from google.cloud.logging.logger import Logger

        NOW, TIMESTAMP = self._make_timestamp()
        IID = 'IID'
        TEXT = 'TEXT'
        SENT = {
            'projectIds': [self.PROJECT],
        }
        TOKEN = 'TOKEN'
        RETURNED = {
            'entries': [{
                'textPayload': TEXT,
                'insertId': IID,
                'resource': {
                    'type': 'global',
                },
                'timestamp': TIMESTAMP,
                'logName': 'projects/%s/logs/%s' % (
                    self.PROJECT, self.LOGGER_NAME),
            }],
            'nextPageToken': TOKEN,
        }
        client = Client(project=self.PROJECT, credentials=object(),
                        use_gax=False)
        client._connection = _Connection(RETURNED)
        api = self._make_one(client)

        iterator = api.list_entries([self.PROJECT])
        page = six.next(iterator.pages)
        entries = list(page)
        token = iterator.next_page_token

        # First check the token.
        self.assertEqual(token, TOKEN)
        # Then check the entries returned.
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertIsInstance(entry, TextEntry)
        self.assertEqual(entry.payload, TEXT)
        self.assertIsInstance(entry.logger, Logger)
        self.assertEqual(entry.logger.name, self.LOGGER_NAME)
        self.assertEqual(entry.insert_id, IID)
        self.assertEqual(entry.timestamp, NOW)
        self.assertIsNone(entry.labels)
        self.assertIsNone(entry.severity)
        self.assertIsNone(entry.http_request)

        called_with = client._connection._called_with
        expected_path = '/%s' % (self.LIST_ENTRIES_PATH,)
        self.assertEqual(called_with, {
            'method': 'POST',
            'path': expected_path,
            'data': SENT,
        })

    def test_list_entries_w_paging(self):
        from google.cloud.logging import DESCENDING
        from google.cloud.logging.client import Client
        from google.cloud.logging.logger import Logger
        from google.cloud.logging.entries import ProtobufEntry
        from google.cloud.logging.entries import StructEntry

        PROJECT1 = 'PROJECT1'
        PROJECT2 = 'PROJECT2'
        NOW, TIMESTAMP = self._make_timestamp()
        IID1 = 'IID1'
        IID2 = 'IID2'
        PAYLOAD = {'message': 'MESSAGE', 'weather': 'partly cloudy'}
        PROTO_PAYLOAD = PAYLOAD.copy()
        PROTO_PAYLOAD['@type'] = 'type.googleapis.com/testing.example'
        TOKEN = 'TOKEN'
        PAGE_SIZE = 42
        SENT = {
            'projectIds': [PROJECT1, PROJECT2],
            'filter': self.FILTER,
            'orderBy': DESCENDING,
            'pageSize': PAGE_SIZE,
            'pageToken': TOKEN,
        }
        RETURNED = {
            'entries': [{
                'jsonPayload': PAYLOAD,
                'insertId': IID1,
                'resource': {
                    'type': 'global',
                },
                'timestamp': TIMESTAMP,
                'logName': 'projects/%s/logs/%s' % (
                    self.PROJECT, self.LOGGER_NAME),
            }, {
                'protoPayload': PROTO_PAYLOAD,
                'insertId': IID2,
                'resource': {
                    'type': 'global',
                },
                'timestamp': TIMESTAMP,
                'logName': 'projects/%s/logs/%s' % (
                    self.PROJECT, self.LOGGER_NAME),
            }],
        }
        client = Client(project=self.PROJECT, credentials=object(),
                        use_gax=False)
        client._connection = _Connection(RETURNED)
        api = self._make_one(client)

        iterator = api.list_entries(
            projects=[PROJECT1, PROJECT2], filter_=self.FILTER,
            order_by=DESCENDING, page_size=PAGE_SIZE, page_token=TOKEN)
        entries = list(iterator)
        token = iterator.next_page_token

        # First check the token.
        self.assertIsNone(token)
        # Then check the entries returned.
        self.assertEqual(len(entries), 2)
        entry1 = entries[0]
        self.assertIsInstance(entry1, StructEntry)
        self.assertEqual(entry1.payload, PAYLOAD)
        self.assertIsInstance(entry1.logger, Logger)
        self.assertEqual(entry1.logger.name, self.LOGGER_NAME)
        self.assertEqual(entry1.insert_id, IID1)
        self.assertEqual(entry1.timestamp, NOW)
        self.assertIsNone(entry1.labels)
        self.assertIsNone(entry1.severity)
        self.assertIsNone(entry1.http_request)

        entry2 = entries[1]
        self.assertIsInstance(entry2, ProtobufEntry)
        self.assertEqual(entry2.payload, PROTO_PAYLOAD)
        self.assertIsInstance(entry2.logger, Logger)
        self.assertEqual(entry2.logger.name, self.LOGGER_NAME)
        self.assertEqual(entry2.insert_id, IID2)
        self.assertEqual(entry2.timestamp, NOW)
        self.assertIsNone(entry2.labels)
        self.assertIsNone(entry2.severity)
        self.assertIsNone(entry2.http_request)

        called_with = client._connection._called_with
        expected_path = '/%s' % (self.LIST_ENTRIES_PATH,)
        self.assertEqual(called_with, {
            'method': 'POST',
            'path': expected_path,
            'data': SENT,
        })

    def test_write_entries_single(self):
        TEXT = 'TEXT'
        ENTRY = {
            'textPayload': TEXT,
            'resource': {
                'type': 'global',
            },
            'logName': 'projects/%s/logs/%s' % (
                self.PROJECT, self.LOGGER_NAME),
        }
        SENT = {
            'entries': [ENTRY],
        }
        conn = _Connection({})
        client = _Client(conn)
        api = self._make_one(client)

        api.write_entries([ENTRY])

        self.assertEqual(conn._called_with['method'], 'POST')
        path = '/%s' % self.WRITE_ENTRIES_PATH
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_write_entries_multiple(self):
        TEXT = 'TEXT'
        LOG_NAME = 'projects/%s/logs/%s' % (self.PROJECT, self.LOGGER_NAME)
        RESOURCE = {
            'type': 'global',
        }
        LABELS = {
            'baz': 'qux',
            'spam': 'eggs',
        }
        ENTRY1 = {
            'textPayload': TEXT,
        }
        ENTRY2 = {
            'jsonPayload': {'foo': 'bar'},
        }
        SENT = {
            'logName': LOG_NAME,
            'resource': RESOURCE,
            'labels': LABELS,
            'entries': [ENTRY1, ENTRY2],
        }
        conn = _Connection({})
        client = _Client(conn)
        api = self._make_one(client)

        api.write_entries([ENTRY1, ENTRY2], LOG_NAME, RESOURCE, LABELS)

        self.assertEqual(conn._called_with['method'], 'POST')
        path = '/%s' % self.WRITE_ENTRIES_PATH
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_logger_delete(self):
        path = '/projects/%s/logs/%s' % (self.PROJECT, self.LOGGER_NAME)
        conn = _Connection({})
        client = _Client(conn)
        api = self._make_one(client)

        api.logger_delete(self.PROJECT, self.LOGGER_NAME)

        self.assertEqual(conn._called_with['method'], 'DELETE')
        self.assertEqual(conn._called_with['path'], path)


class Test_SinksAPI(unittest.TestCase):

    PROJECT = 'project'
    FILTER = 'logName:syslog AND severity>=ERROR'
    LIST_SINKS_PATH = 'projects/%s/sinks' % (PROJECT,)
    SINK_NAME = 'sink_name'
    SINK_PATH = 'projects/%s/sinks/%s' % (PROJECT, SINK_NAME)
    DESTINATION_URI = 'faux.googleapis.com/destination'

    @staticmethod
    def _get_target_class():
        from google.cloud.logging._http import _SinksAPI
        return _SinksAPI

    def _make_one(self, *args, **kw):
        return self._get_target_class()(*args, **kw)

    def test_ctor(self):
        connection = object()
        client = _Client(connection)
        api = self._make_one(client)
        self.assertIs(api._connection, connection)
        self.assertIs(api._client, client)

    def test_list_sinks_no_paging(self):
        import six
        from google.cloud.logging.sink import Sink

        TOKEN = 'TOKEN'
        RETURNED = {
            'sinks': [{
                'name': self.SINK_PATH,
                'filter': self.FILTER,
                'destination': self.DESTINATION_URI,
            }],
            'nextPageToken': TOKEN,
        }
        conn = _Connection(RETURNED)
        client = _Client(conn)
        api = self._make_one(client)

        iterator = api.list_sinks(self.PROJECT)
        page = six.next(iterator.pages)
        sinks = list(page)
        token = iterator.next_page_token

        # First check the token.
        self.assertEqual(token, TOKEN)
        # Then check the sinks returned.
        self.assertEqual(len(sinks), 1)
        sink = sinks[0]
        self.assertIsInstance(sink, Sink)
        self.assertEqual(sink.name, self.SINK_PATH)
        self.assertEqual(sink.filter_, self.FILTER)
        self.assertEqual(sink.destination, self.DESTINATION_URI)
        self.assertIs(sink.client, client)

        called_with = conn._called_with
        path = '/%s' % (self.LIST_SINKS_PATH,)
        self.assertEqual(called_with, {
            'method': 'GET',
            'path': path,
            'query_params': {},
        })

    def test_list_sinks_w_paging(self):
        from google.cloud.logging.sink import Sink

        TOKEN = 'TOKEN'
        PAGE_SIZE = 42
        RETURNED = {
            'sinks': [{
                'name': self.SINK_PATH,
                'filter': self.FILTER,
                'destination': self.DESTINATION_URI,
            }],
        }
        conn = _Connection(RETURNED)
        client = _Client(conn)
        api = self._make_one(client)

        iterator = api.list_sinks(
            self.PROJECT, page_size=PAGE_SIZE, page_token=TOKEN)
        sinks = list(iterator)
        token = iterator.next_page_token

        # First check the token.
        self.assertIsNone(token)
        # Then check the sinks returned.
        self.assertEqual(len(sinks), 1)
        sink = sinks[0]
        self.assertIsInstance(sink, Sink)
        self.assertEqual(sink.name, self.SINK_PATH)
        self.assertEqual(sink.filter_, self.FILTER)
        self.assertEqual(sink.destination, self.DESTINATION_URI)
        self.assertIs(sink.client, client)

        called_with = conn._called_with
        path = '/%s' % (self.LIST_SINKS_PATH,)
        self.assertEqual(called_with, {
            'method': 'GET',
            'path': path,
            'query_params': {
                'pageSize': PAGE_SIZE,
                'pageToken': TOKEN,
            },
        })

    def test_sink_create_conflict(self):
        from google.cloud.exceptions import Conflict
        SENT = {
            'name': self.SINK_NAME,
            'filter': self.FILTER,
            'destination': self.DESTINATION_URI,
        }
        conn = _Connection()
        conn._raise_conflict = True
        client = _Client(conn)
        api = self._make_one(client)

        with self.assertRaises(Conflict):
            api.sink_create(
                self.PROJECT, self.SINK_NAME, self.FILTER,
                self.DESTINATION_URI)

        self.assertEqual(conn._called_with['method'], 'POST')
        path = '/projects/%s/sinks' % (self.PROJECT,)
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_sink_create_ok(self):
        SENT = {
            'name': self.SINK_NAME,
            'filter': self.FILTER,
            'destination': self.DESTINATION_URI,
        }
        conn = _Connection({})
        client = _Client(conn)
        api = self._make_one(client)

        api.sink_create(
            self.PROJECT, self.SINK_NAME, self.FILTER, self.DESTINATION_URI)

        self.assertEqual(conn._called_with['method'], 'POST')
        path = '/projects/%s/sinks' % (self.PROJECT,)
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_sink_get_miss(self):
        from google.cloud.exceptions import NotFound
        conn = _Connection()
        client = _Client(conn)
        api = self._make_one(client)

        with self.assertRaises(NotFound):
            api.sink_get(self.PROJECT, self.SINK_NAME)

        self.assertEqual(conn._called_with['method'], 'GET')
        path = '/projects/%s/sinks/%s' % (self.PROJECT, self.SINK_NAME)
        self.assertEqual(conn._called_with['path'], path)

    def test_sink_get_hit(self):
        RESPONSE = {
            'name': self.SINK_PATH,
            'filter': self.FILTER,
            'destination': self.DESTINATION_URI,
        }
        conn = _Connection(RESPONSE)
        client = _Client(conn)
        api = self._make_one(client)

        response = api.sink_get(self.PROJECT, self.SINK_NAME)

        self.assertEqual(response, RESPONSE)
        self.assertEqual(conn._called_with['method'], 'GET')
        path = '/projects/%s/sinks/%s' % (self.PROJECT, self.SINK_NAME)
        self.assertEqual(conn._called_with['path'], path)

    def test_sink_update_miss(self):
        from google.cloud.exceptions import NotFound
        SENT = {
            'name': self.SINK_NAME,
            'filter': self.FILTER,
            'destination': self.DESTINATION_URI,
        }
        conn = _Connection()
        client = _Client(conn)
        api = self._make_one(client)

        with self.assertRaises(NotFound):
            api.sink_update(
                self.PROJECT, self.SINK_NAME, self.FILTER,
                self.DESTINATION_URI)

        self.assertEqual(conn._called_with['method'], 'PUT')
        path = '/projects/%s/sinks/%s' % (self.PROJECT, self.SINK_NAME)
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_sink_update_hit(self):
        SENT = {
            'name': self.SINK_NAME,
            'filter': self.FILTER,
            'destination': self.DESTINATION_URI,
        }
        conn = _Connection({})
        client = _Client(conn)
        api = self._make_one(client)

        api.sink_update(
            self.PROJECT, self.SINK_NAME, self.FILTER, self.DESTINATION_URI)

        self.assertEqual(conn._called_with['method'], 'PUT')
        path = '/projects/%s/sinks/%s' % (self.PROJECT, self.SINK_NAME)
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_sink_delete_miss(self):
        from google.cloud.exceptions import NotFound
        conn = _Connection()
        client = _Client(conn)
        api = self._make_one(client)

        with self.assertRaises(NotFound):
            api.sink_delete(self.PROJECT, self.SINK_NAME)

        self.assertEqual(conn._called_with['method'], 'DELETE')
        path = '/projects/%s/sinks/%s' % (self.PROJECT, self.SINK_NAME)
        self.assertEqual(conn._called_with['path'], path)

    def test_sink_delete_hit(self):
        conn = _Connection({})
        client = _Client(conn)
        api = self._make_one(client)

        api.sink_delete(self.PROJECT, self.SINK_NAME)

        self.assertEqual(conn._called_with['method'], 'DELETE')
        path = '/projects/%s/sinks/%s' % (self.PROJECT, self.SINK_NAME)
        self.assertEqual(conn._called_with['path'], path)


class Test_MetricsAPI(unittest.TestCase):

    PROJECT = 'project'
    FILTER = 'logName:syslog AND severity>=ERROR'
    LIST_METRICS_PATH = 'projects/%s/metrics' % (PROJECT,)
    METRIC_NAME = 'metric_name'
    METRIC_PATH = 'projects/%s/metrics/%s' % (PROJECT, METRIC_NAME)
    DESCRIPTION = 'DESCRIPTION'

    @staticmethod
    def _get_target_class():
        from google.cloud.logging._http import _MetricsAPI
        return _MetricsAPI

    def _make_one(self, *args, **kw):
        return self._get_target_class()(*args, **kw)

    def test_list_metrics_no_paging(self):
        import six
        from google.cloud.logging.metric import Metric

        TOKEN = 'TOKEN'
        RETURNED = {
            'metrics': [{
                'name': self.METRIC_PATH,
                'filter': self.FILTER,
            }],
            'nextPageToken': TOKEN,
        }
        conn = _Connection(RETURNED)
        client = _Client(conn)
        api = self._make_one(client)

        iterator = api.list_metrics(self.PROJECT)
        page = six.next(iterator.pages)
        metrics = list(page)
        token = iterator.next_page_token

        # First check the token.
        self.assertEqual(token, TOKEN)
        # Then check the metrics returned.
        self.assertEqual(len(metrics), 1)
        metric = metrics[0]
        self.assertIsInstance(metric, Metric)
        self.assertEqual(metric.name, self.METRIC_PATH)
        self.assertEqual(metric.filter_, self.FILTER)
        self.assertEqual(metric.description, '')
        self.assertIs(metric.client, client)

        called_with = conn._called_with
        path = '/%s' % (self.LIST_METRICS_PATH,)
        self.assertEqual(called_with, {
            'method': 'GET',
            'path': path,
            'query_params': {},
        })

    def test_list_metrics_w_paging(self):
        from google.cloud.logging.metric import Metric

        TOKEN = 'TOKEN'
        PAGE_SIZE = 42
        RETURNED = {
            'metrics': [{
                'name': self.METRIC_PATH,
                'filter': self.FILTER,
            }],
        }
        conn = _Connection(RETURNED)
        client = _Client(conn)
        api = self._make_one(client)

        iterator = api.list_metrics(
            self.PROJECT, page_size=PAGE_SIZE, page_token=TOKEN)
        metrics = list(iterator)
        token = iterator.next_page_token

        # First check the token.
        self.assertIsNone(token)
        # Then check the metrics returned.
        self.assertEqual(len(metrics), 1)
        metric = metrics[0]
        self.assertIsInstance(metric, Metric)
        self.assertEqual(metric.name, self.METRIC_PATH)
        self.assertEqual(metric.filter_, self.FILTER)
        self.assertEqual(metric.description, '')
        self.assertIs(metric.client, client)

        called_with = conn._called_with
        path = '/%s' % (self.LIST_METRICS_PATH,)
        self.assertEqual(called_with, {
            'method': 'GET',
            'path': path,
            'query_params': {
                'pageSize': PAGE_SIZE,
                'pageToken': TOKEN,
            },
        })

    def test_metric_create_conflict(self):
        from google.cloud.exceptions import Conflict
        SENT = {
            'name': self.METRIC_NAME,
            'filter': self.FILTER,
            'description': self.DESCRIPTION,
        }
        conn = _Connection()
        conn._raise_conflict = True
        client = _Client(conn)
        api = self._make_one(client)

        with self.assertRaises(Conflict):
            api.metric_create(
                self.PROJECT, self.METRIC_NAME, self.FILTER,
                self.DESCRIPTION)

        self.assertEqual(conn._called_with['method'], 'POST')
        path = '/projects/%s/metrics' % (self.PROJECT,)
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_metric_create_ok(self):
        SENT = {
            'name': self.METRIC_NAME,
            'filter': self.FILTER,
            'description': self.DESCRIPTION,
        }
        conn = _Connection({})
        client = _Client(conn)
        api = self._make_one(client)

        api.metric_create(
            self.PROJECT, self.METRIC_NAME, self.FILTER, self.DESCRIPTION)

        self.assertEqual(conn._called_with['method'], 'POST')
        path = '/projects/%s/metrics' % (self.PROJECT,)
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_metric_get_miss(self):
        from google.cloud.exceptions import NotFound
        conn = _Connection()
        client = _Client(conn)
        api = self._make_one(client)

        with self.assertRaises(NotFound):
            api.metric_get(self.PROJECT, self.METRIC_NAME)

        self.assertEqual(conn._called_with['method'], 'GET')
        path = '/projects/%s/metrics/%s' % (self.PROJECT, self.METRIC_NAME)
        self.assertEqual(conn._called_with['path'], path)

    def test_metric_get_hit(self):
        RESPONSE = {
            'name': self.METRIC_NAME,
            'filter': self.FILTER,
            'description': self.DESCRIPTION,
        }
        conn = _Connection(RESPONSE)
        client = _Client(conn)
        api = self._make_one(client)

        response = api.metric_get(self.PROJECT, self.METRIC_NAME)

        self.assertEqual(response, RESPONSE)
        self.assertEqual(conn._called_with['method'], 'GET')
        path = '/projects/%s/metrics/%s' % (self.PROJECT, self.METRIC_NAME)
        self.assertEqual(conn._called_with['path'], path)

    def test_metric_update_miss(self):
        from google.cloud.exceptions import NotFound
        SENT = {
            'name': self.METRIC_NAME,
            'filter': self.FILTER,
            'description': self.DESCRIPTION,
        }
        conn = _Connection()
        client = _Client(conn)
        api = self._make_one(client)

        with self.assertRaises(NotFound):
            api.metric_update(
                self.PROJECT, self.METRIC_NAME, self.FILTER,
                self.DESCRIPTION)

        self.assertEqual(conn._called_with['method'], 'PUT')
        path = '/projects/%s/metrics/%s' % (self.PROJECT, self.METRIC_NAME)
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_metric_update_hit(self):
        SENT = {
            'name': self.METRIC_NAME,
            'filter': self.FILTER,
            'description': self.DESCRIPTION,
        }
        conn = _Connection({})
        client = _Client(conn)
        api = self._make_one(client)

        api.metric_update(
            self.PROJECT, self.METRIC_NAME, self.FILTER, self.DESCRIPTION)

        self.assertEqual(conn._called_with['method'], 'PUT')
        path = '/projects/%s/metrics/%s' % (self.PROJECT, self.METRIC_NAME)
        self.assertEqual(conn._called_with['path'], path)
        self.assertEqual(conn._called_with['data'], SENT)

    def test_metric_delete_miss(self):
        from google.cloud.exceptions import NotFound
        conn = _Connection()
        client = _Client(conn)
        api = self._make_one(client)

        with self.assertRaises(NotFound):
            api.metric_delete(self.PROJECT, self.METRIC_NAME)

        self.assertEqual(conn._called_with['method'], 'DELETE')
        path = '/projects/%s/metrics/%s' % (self.PROJECT, self.METRIC_NAME)
        self.assertEqual(conn._called_with['path'], path)

    def test_metric_delete_hit(self):
        conn = _Connection({})
        client = _Client(conn)
        api = self._make_one(client)

        api.metric_delete(self.PROJECT, self.METRIC_NAME)

        self.assertEqual(conn._called_with['method'], 'DELETE')
        path = '/projects/%s/metrics/%s' % (self.PROJECT, self.METRIC_NAME)
        self.assertEqual(conn._called_with['path'], path)


class _Credentials(object):

    _scopes = None

    @staticmethod
    def create_scoped_required():
        return True

    def create_scoped(self, scope):
        self._scopes = scope
        return self


class _Connection(object):

    _called_with = None
    _raise_conflict = False

    def __init__(self, *responses):
        self._responses = responses

    def api_request(self, **kw):
        from google.cloud.exceptions import Conflict
        from google.cloud.exceptions import NotFound
        self._called_with = kw
        if self._raise_conflict:
            raise Conflict('oops')
        try:
            response, self._responses = self._responses[0], self._responses[1:]
        except IndexError:
            raise NotFound('miss')
        return response


def _datetime_to_rfc3339_w_nanos(value):
    from google.cloud._helpers import _RFC3339_NO_FRACTION
    no_fraction = value.strftime(_RFC3339_NO_FRACTION)
    return '%s.%09dZ' % (no_fraction, value.microsecond * 1000)


class _Client(object):

    def __init__(self, connection):
        self._connection = connection
