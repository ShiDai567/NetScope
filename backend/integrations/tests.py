from django.test import TestCase
from unittest.mock import patch

from ikuai_sdk import IKuaiLoginResult


class IKuaiApiTests(TestCase):
    def test_ikuai_login_requires_fields(self):
        response = self.client.post(
            "/api/ikuai/login",
            data='{"routerUrl":"http://10.1.1.1","username":"admin"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "routerUrl, username, password are required",
        )

    def test_ikuai_sessions_empty_by_default(self):
        response = self.client.get("/api/ikuai/sessions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @patch("integrations.services.IKuaiClient.login")
    def test_ikuai_login_uses_sdk_and_persists_session(self, login_mock):
        login_mock.return_value = IKuaiLoginResult(
            router_url="http://10.1.1.1",
            login_url="http://10.1.1.1/Action/login",
            username="admin",
            request_mode="json",
            request_payload={
                "username": "admin",
                "passwd": "202cb962ac59075b964b07152d234b70",
                "pass": "ac59075b964b07150000",
                "remember_password": "",
            },
            upstream_status=200,
            upstream_response={"Result": 10000, "ErrMsg": "Succeess"},
            response_headers={"Content-Type": "application/json"},
            cookies={"sess_key": "abc123"},
            sess_key="abc123",
            cookie_header="sess_key=abc123; username=admin; login=1",
        )

        response = self.client.post(
            "/api/ikuai/login",
            data='{"routerUrl":"http://10.1.1.1","username":"admin","password":"123"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sess_key"], "abc123")
        login_mock.assert_called_once()
