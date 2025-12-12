import re

def chunker(array):
    return [array[i:i+100] for i in range(len(array))[::100]]
    

def get_playlist_id(url):
    """Extract playlist ID from Spotify URL (with or without query params)."""
    url = url.strip()  # Remove any whitespace
    
    # Match playlist ID with optional query params
    # Handles: /playlist/ID or /playlist/ID?si=...
    mo = re.search(r"playlist/([a-zA-Z0-9]{22})(?:\?|$)", url)
    
    if mo is None:
        raise ValueError("Remixify needs a Spotify link, kindly check again")
    
    return mo.group(1)