"""
Generate a Spotify refresh token for the central account.

This is a ONE-TIME setup command. Run it locally to authenticate with your
Spotify account and get a refresh token that can be used in production.

Usage:
    python manage.py generate_spotify_token
"""
from django.core.management.base import BaseCommand
from decouple import config
from spotipy.oauth2 import SpotifyOAuth
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle the OAuth callback and extract the authorization code."""
    
    auth_code = None
    
    def do_GET(self):
        """Handle GET request from Spotify callback."""
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if 'code' in params:
            CallbackHandler.auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'''
                <html>
                <head><title>Success!</title></head>
                <body style="font-family: system-ui; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: linear-gradient(135deg, #1DB954 0%, #191414 100%);">
                    <div style="text-align: center; color: white;">
                        <h1>&#10003; Authorization Successful!</h1>
                        <p>You can close this window and return to the terminal.</p>
                    </div>
                </body>
                </html>
            ''')
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            error = params.get('error', ['Unknown error'])[0]
            self.wfile.write(f'<html><body><h1>Error: {error}</h1></body></html>'.encode())
    
    def log_message(self, format, *args):
        """Suppress HTTP request logs."""
        pass


class Command(BaseCommand):
    help = 'Generate a Spotify refresh token for the central account'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('Spotify Token Generator for Central Account'))
        self.stdout.write(self.style.WARNING('='*60 + '\n'))
        
        client_id = config("SPOTIPY_CLIENT_ID", default=None)
        client_secret = config("SPOTIPY_CLIENT_SECRET", default=None)
        
        if not client_id or not client_secret:
            self.stdout.write(self.style.ERROR(
                'ERROR: SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET must be set in your environment.'
            ))
            return
        
        # Use localhost for the callback
        redirect_uri = "http://127.0.0.1:8888/callback"
        
        self.stdout.write(self.style.NOTICE(
            f'\nIMPORTANT: Make sure to add this redirect URI to your Spotify app settings:'
        ))
        self.stdout.write(self.style.SUCCESS(f'  {redirect_uri}\n'))
        
        # Required scopes for Remixify
        scope = "user-library-read playlist-modify-private playlist-modify-public playlist-read-collaborative playlist-read-private user-follow-modify"
        
        # Create OAuth manager
        sp_oauth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            open_browser=False
        )
        
        # Get authorization URL
        auth_url = sp_oauth.get_authorize_url()
        
        self.stdout.write('\nOpening browser for Spotify authorization...')
        self.stdout.write(f'If the browser does not open, visit this URL:\n')
        self.stdout.write(self.style.SUCCESS(f'  {auth_url}\n'))
        
        # Start local server to receive callback
        server = HTTPServer(('localhost', 8888), CallbackHandler)
        server_thread = threading.Thread(target=server.handle_request)
        server_thread.start()
        
        # Open browser
        webbrowser.open(auth_url)
        
        self.stdout.write('Waiting for authorization...')
        server_thread.join(timeout=120)  # Wait up to 2 minutes
        
        if not CallbackHandler.auth_code:
            self.stdout.write(self.style.ERROR('\nERROR: No authorization code received. Timed out or cancelled.'))
            return
        
        self.stdout.write(self.style.SUCCESS('\nAuthorization code received!'))
        
        # Exchange code for tokens
        try:
            token_info = sp_oauth.get_access_token(CallbackHandler.auth_code)
            
            refresh_token = token_info['refresh_token']
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('SUCCESS! Here is your refresh token:'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(f'\n{refresh_token}\n')
            
            self.stdout.write(self.style.WARNING('\n' + '-'*60))
            self.stdout.write(self.style.WARNING('Next steps:'))
            self.stdout.write(self.style.WARNING('-'*60))
            self.stdout.write('\n1. Add to your local .env file:')
            self.stdout.write(self.style.SUCCESS(f'   SPOTIFY_REFRESH_TOKEN={refresh_token}'))
            self.stdout.write('\n2. Add to Fly.io secrets:')
            self.stdout.write(self.style.SUCCESS(f'   fly secrets set SPOTIFY_REFRESH_TOKEN="{refresh_token}"'))
            self.stdout.write('\n')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nERROR exchanging code for token: {e}'))
