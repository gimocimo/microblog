import unittest

from app import create_app, db
from app.models import Post, User
from tests import TestConfig


def auth_headers(client, username, password):
    response = client.post('/api/tokens', auth=(username, password))
    if response.status_code != 200:
        raise AssertionError(f'Token request failed: {response.status_code}')
    return {'Authorization': f'Bearer {response.get_json()["token"]}'}


class UserAPICase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        john = User(id=1, username='john', email='john@example.com',
                    about_me='Hello from John')
        john.set_password('cat')
        follower = User(id=2, username='susan', email='susan@example.com')
        followed = User(id=3, username='mary', email='mary@example.com')
        db.session.add_all([john, follower, followed])
        db.session.add(Post(body='A post from John', author=john))
        follower.follow(john)
        john.follow(followed)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def assert_unauthorized(self, response):
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.mimetype, 'application/json')
        self.assertEqual(response.get_json(), {'error': 'Unauthorized'})

    def test_get_user_with_valid_token(self):
        response = self.client.get(
            '/api/users/1', headers=auth_headers(self.client, 'john', 'cat'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/json')
        data = response.get_json()
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['username'], 'john')
        self.assertEqual(data['about_me'], 'Hello from John')
        self.assertEqual(data['post_count'], 1)
        self.assertEqual(data['follower_count'], 1)
        self.assertEqual(data['following_count'], 1)
        self.assertEqual(
            data['_links']['avatar'],
            'https://www.gravatar.com/avatar/'
            'd4c74594d841139328695756648b6bd6?d=identicon&s=128')

    def test_get_user_without_token(self):
        response = self.client.get('/api/users/1')

        self.assert_unauthorized(response)

    def test_get_user_with_invalid_token(self):
        for authorization in ('Bearer', 'Bearer unknown-token'):
            with self.subTest(authorization=authorization):
                response = self.client.get(
                    '/api/users/1',
                    headers={'Authorization': authorization})

                self.assert_unauthorized(response)

    def test_get_user_with_revoked_token(self):
        headers = auth_headers(self.client, 'john', 'cat')
        response = self.client.delete('/api/tokens', headers=headers)

        self.assertEqual(response.status_code, 204)

        response = self.client.get('/api/users/1', headers=headers)

        self.assert_unauthorized(response)

    def test_get_nonexistent_user_with_valid_token(self):
        response = self.client.get(
            '/api/users/999', headers=auth_headers(self.client, 'john', 'cat'))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.mimetype, 'application/json')
        self.assertEqual(response.get_json(), {'error': 'Not Found'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
