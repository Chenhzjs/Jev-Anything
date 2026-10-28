import unittest
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch, Mock
import requests
from jev_anything.jev import JevClient, JevConfig, JevError


class ProviderTests(unittest.TestCase):
    def test_explicit_retry_only_repeats_rejected_read_only_request_with_identical_bytes(self):
        def response(status, body):
            result = requests.Response(); result.status_code = status
            result.url = 'https://provider.invalid/decisions'; result._content = json.dumps(body).encode()
            result.headers['X-Request-ID'] = 'http-' + str(status)
            return result
        error = {'error': {'code': 1004, 'message': 'Invalid Decisions request'}}
        session = Mock(post=Mock(side_effect=[response(400, error), response(200, {'answers': {}})]))
        client = JevClient(JevConfig(api_key='test-only', decision_retries=1), session=session)
        self.assertEqual(client.decide(state={'full': '全部材料 Ω'}, questions={}), {})
        self.assertEqual(session.post.call_count, 2)
        self.assertEqual(session.post.call_args_list[0], session.post.call_args_list[1])
        self.assertEqual([a['http_status'] for a in client.metadata['read_only_attempts']], [400, 200])
        for status, body, count in [(400, error, 2), (413, error, 1), (400, {'error': {'code': 999}}, 1)]:
            with self.subTest(status=status, body=body):
                session.post = Mock(side_effect=lambda *args, **kwargs: response(status, body))
                with self.assertRaises(JevError): client.decide(state={}, questions={})
                self.assertEqual(session.post.call_count, count)
        session.post = Mock(return_value=response(400, error))
        with self.assertRaises(JevError):
            JevClient(JevConfig(api_key='test-only'), session=session).decide(state={}, questions={})
        session.post.assert_called_once()

    def setUp(self):
        self.client = JevClient(JevConfig(api_key="test-only", timeout=0.01))

    def test_timeout(self):
        with patch("jev_anything.jev.requests.post", side_effect=requests.Timeout("timed out")):
            with self.assertRaises(JevError):
                self.client.decide(state={}, questions={"a": {}})

    def test_invalid_bodies(self):
        for body in ([], None, {"answers": []}, {}):
            with self.subTest(body=body), patch("jev_anything.jev.requests.post") as post:
                post.return_value = Mock(json=Mock(return_value=body))
                with self.assertRaises(JevError):
                    self.client.decide(state={}, questions={"a": {}})

    def test_metadata(self):
        with patch("jev_anything.jev.requests.post") as post:
            post.return_value = Mock(json=Mock(return_value={"id": "request-1", "answers": {}, "usage": {"cost": 0.01}}))
            self.client.decide(state={}, questions={"a": {}})
            self.assertEqual(self.client.metadata["request_id"], "request-1")
            self.assertNotIn("api_key", self.client.metadata)

    def test_http_rejection_has_fresh_metadata(self):
        self.client.metadata = {"request_id": "previous", "usage": {"cost": 1}}
        response = requests.Response()
        response.status_code = 413
        response.url = self.client.config.api_url
        response.headers['X-Request-ID'] = 'rejected-request'
        with patch('jev_anything.jev.requests.post', return_value=response):
            with self.assertRaises(JevError):
                self.client.decide(state={}, questions={})
        self.assertEqual(self.client.metadata,
                         {'http_status': 413, 'request_id': 'rejected-request'})

    def test_actual_utf8_http_body_preserves_complete_json(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.headers['Content-Type'],
                                 self.rfile.read(int(self.headers['Content-Length']))))
                body = b'{"answers":{}}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            client = JevClient(JevConfig(api_key='utf8-stub-only', timeout=2,
                               api_url=f'http://127.0.0.1:{server.server_port}/decisions'))
            state = {'text': '公开正文 🧪\n尾部', 'future': {'保留': [True, None, 1.5]},
                     'history': [{'receipt': {'message': '完整回执'}}]}
            questions = {'a': {'type': 'choice', 'criteria': {'选择': '中文说明'}}}
            client.decide(state=state, questions=questions)
            payload = {'model': client.model, 'state': state, 'questions': questions}
            baseline = requests.Request('POST', 'http://127.0.0.1/unused', json=payload).prepare().body
            self.assertEqual(len(received), 1)
            content_type, raw = received[0]
            self.assertEqual(content_type, 'application/json')
            self.assertEqual(json.loads(raw), payload)
            self.assertIn('公开正文 🧪'.encode('utf-8'), raw)
            self.assertLess(len(raw), len(baseline))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_nonfinite_json_fails_before_transport_with_fresh_metadata(self):
        self.client.metadata = {'request_id': 'previous'}
        with patch('jev_anything.jev.requests.post') as post:
            with self.assertRaises(JevError):
                self.client.decide(state={'value': float('nan')}, questions={})
        post.assert_not_called()
        self.assertEqual(self.client.metadata, {})

    def test_injected_session_reuses_http_connection_and_does_not_retry_timeout(self):
        addresses=[];received=[]
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def do_POST(self):
                addresses.append(self.client_address)
                received.append(self.rfile.read(int(self.headers['Content-Length'])))
                body=b'{"answers":{},"id":"local-pooled"}'
                self.send_response(200);self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with requests.Session() as session:
                self.assertEqual(session.get_adapter('https://').max_retries.total,0)
                client=JevClient(JevConfig(api_key='session-test-only',timeout=2,
                    api_url=f'http://127.0.0.1:{server.server_port}/decisions'),session=session)
                state={'public':'完整内容🙂','history':[{'effect':'unknown'}]}
                for _ in range(2):client.decide(state=state,questions={})
                self.assertEqual(addresses[0],addresses[1]);self.assertEqual(received[0],received[1])
                self.assertEqual(json.loads(received[0])['state'],state)
                with patch.object(session,'post',side_effect=requests.Timeout('lost response')) as post:
                    with self.assertRaises(JevError):client.decide(state=state,questions={})
                    post.assert_called_once();self.assertEqual(client.metadata,{})
        finally:
            server.shutdown();server.server_close();worker.join(timeout=5)
