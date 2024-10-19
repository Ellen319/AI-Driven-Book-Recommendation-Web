import csv
import unittest
from unittest.mock import patch, MagicMock
from flask import session, get_flashed_messages
from app import create_app, init_db
from connect import getCursor
import time

class FlaskAppTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize the app with testing configuration
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        init_db()  # Initialize database schema

    @classmethod
    def tearDownClass(cls):
        cls.app_context.pop()

        # Mock the getCursor function to avoid real database calls
    def mock_getCursor(self):
        connection = MagicMock()  # Mock connection object
        cursor = MagicMock()      # Mock cursor object
        return connection, cursor

    # Helper function to check if book exists in CSV
    def check_book_in_csv(self, book_id):
        with open('data.csv', mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['bookId'] == book_id:
                    return True
        return False

    # Helper function to simulate login
    def login(self, username, password):
        return self.client.post('/login', data=dict(username=username, password=password), follow_redirects=True)

    def test_home_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b'Welcome', response.data)

    def test_signup(self):
        with patch('connect.getCursor') as mock_cursor:
            mock_cursor.return_value = (MagicMock(), MagicMock())
            unique_username = f"testuser_{int(time.time())}"  # Generates a unique username
            response = self.client.post('/signup', data={
                'username': unique_username,
                'email': 'test@test.com',
                'password': '123'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Registration successful. Please log in', response.data)

    def test_login(self):
        # Post login data
        response = self.client.post('/login', data={
            'username': 'testuser',  # Replace with actual test user data
            'password': '123'  # Replace with actual test password
        }, follow_redirects=True)  # Follow the redirect to the dashboard

        # Check that the response status is 200 (success after redirect)
        self.assertEqual(response.status_code, 200)

        # Ensure the response data contains the flash message
        # self.assertIn(b'Logged in successful!', response.data)  # Check directly in the response data


   

    # Optional: Additional tests
    def test_login_failure(self):
        # Post invalid login data
        response = self.client.post('/login', data={
            'username': 'wronguser',
            'password': 'wrongpassword'
        })

        # Check that the response was a redirect
        self.assertEqual(response.status_code, 302)

        # Follow the redirect to the login page
        response = self.client.get(response.location)

        # Check if the flash message for failure is present
        # self.assertIn(b'Invalid username or password', response.data)

                
    def test_dashboard_access(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1  # Simulate a logged-in user

        with patch('connect.getCursor') as mock_cursor:
            mock_cursor.return_value = (MagicMock(), MagicMock())
            mock_cursor.return_value[1].fetchall.return_value = []  # No wishlist items

            response = self.client.get('/dashboard')
            self.assertEqual(response.status_code, 200)
            # self.assertIn(b'Your Dashboard', response.data)

    def test_logout(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1  # Simulate a logged-in user

        response = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b'You have been logged out', response.data)


    # Test adding a book to the wishlist when the user is not logged in
    @patch('connect.getCursor', side_effect=mock_getCursor)  # Patch the getCursor method
    def test_add_to_wishlist_not_logged_in(self, mock_getCursor):
        with self.client as client:
            response = client.post('/add_to_wishlist/123', data={'title': 'Test Book', 'coverImg': 'test_img.jpg'}, follow_redirects=True)
            #self.assertIn(b'Please log in to add books to your wishlist.', response.data)

    # Test adding a book to the wishlist when the user is logged in
    @unittest.mock.patch('connect.getCursor', side_effect=mock_getCursor)
    def test_add_to_wishlist_logged_in(self, mock_getCursor):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1

            # Mock database check for an existing book in the wishlist
            mock_getCursor.return_value[1].fetchone.return_value = None

            response = client.post('/add_to_wishlist/123', data={'title': 'Test Book', 'coverImg': 'test_img.jpg'}, follow_redirects=True)
            # self.assertIn(b'Book added to your wishlist successfully!', response.data)

    # Test removing a book from the wishlist when not logged in
    def test_remove_from_wishlist_not_logged_in(self):
        with self.client as client:
            response = client.post('/remove_from_wishlist/123/dashboard', follow_redirects=True)
            # self.assertIn(b'You need to be logged in to remove books from your wishlist.', response.data)

    # Test removing a book from the wishlist when logged in
    @unittest.mock.patch('connect.getCursor', side_effect=mock_getCursor)
    def test_remove_from_wishlist_logged_in(self, mock_getCursor):
        with self.client as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1

            # Mock successful deletion from the wishlist
            mock_getCursor.return_value[1].rowcount = 1

            response = client.post('/remove_from_wishlist/123/book_details', data={}, follow_redirects=True)
            # self.assertIn(b'Book removed from your wishlist successfully!', response.data)


    def test_extract_keywords_and_summary(self):
        response = self.client.post('/extract', data={
            'user_input': 'This is a test input for keyword extraction and summarization.'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'loading', response.data)

    def test_results_page(self):
        with self.client.session_transaction() as sess:
            sess['keywords'] = ['keyword1', 'keyword2']
            sess['summary'] = 'This is a summary.'
            sess['top_books'] = []

        response = self.client.get('/results')
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b'<li>keyword1</li>', response.data)
        # self.assertIn(b'<li>keyword2</li>', response.data)


if __name__ == '__main__':
    unittest.main()
