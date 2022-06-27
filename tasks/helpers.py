import re

def chunker(array):
    return [array[i:i+100] for i in range(len(array))[::100]]
    

def get_playlist_id(url):
        mo = re.match(r".*ist/(\w{22})\?", url)
        if mo is None:
            raise ValueError("Remixify needs a Spotify link, kindly check again")
        return mo.group(1)
        