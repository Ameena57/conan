# coding=utf-8

import unittest
from mock import mock

from conans.client.userio import UserIO


class UserIOTest(unittest.TestCase):

    @mock.patch("conans.client.userio.UserIO.get_username", return_value="username")
    @mock.patch("conans.client.userio.UserIO.get_password", return_value="passwd")
    def test_request_login(self, m1, m2):
        user_io = UserIO()

        # Use mocked ones
        u, p = user_io.request_login(remote_name="lol")
        self.assertEqual(u, "username")
        self.assertEqual(p, "passwd")

        # Use from argument
        username = "it's me!"
        u, p = user_io.request_login(remote_name="lol", username=username)
        self.assertEqual(u, username)
        self.assertEqual(p, "passwd")
