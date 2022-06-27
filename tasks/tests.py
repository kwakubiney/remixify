from django.test import TestCase
from tasks.helpers import chunker, get_playlist_id

class ChunkerTestCase(TestCase):
    def test_chunker(self):
        actual = chunker([1]*158)
        expected=[[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]]
        self.assertEqual(actual, expected)
        
class GetPlaylistID(TestCase):
    def test_get_playlist_id(self):
        actual = get_playlist_id("https://open.spotify.com/playlist/0NhxPzEKlniP54ZDqDC8bR?si=cfb6e43bdd7d4aee")
        expected = "0NhxPzEKlniP54ZDqDC8bR"
        self.assertEqual(actual, expected)
        
# class GetPlaylistIDUnhappyPath(TestCase):
#     def test_get_playlist_id_if_throws_exception(self):
#         self.assertRaises(ValueError("Remixify needs a Spotify link, kindly check again"), get_playlist_id("https://open.spotify.com/playlist/"))