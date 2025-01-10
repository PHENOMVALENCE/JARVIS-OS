import spotipy
from spotipy.oauth2 import SpotifyOAuth

username = 'zuajngxkn70mj85em46i69e8r'
client_id = "bb14c0d81681448798f0c1785c728ee8"
client_secret = "7f2e35b56db04ebaaae233d76936fa45"
redirect_uri = "http://localhost:8888/callback"

def spotify_authenticate(client_id, client_secret, redirect_uri, username):
    scope = "user-read-currently-playing user-modify-playback-state"
    auth_manager = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, scope=scope, username=username)
    return spotipy.Spotify(auth_manager=auth_manager)

def get_current_song():
    global spotify
    current_song = spotify.current_user_playing_track()
    if current_song is None:
        return None
    
    artist = current_song['item']['artists'][0]['name']
    album = current_song['item']['album']['name']
    song = current_song['item']['name']
    
    return {
        "artist": artist,
        "album": album,
        "song": song
    }

def play_song():
    global spotify
    try:
        spotify.start_playback()
    except spotipy.SpotifyException as e:
        return f"Error in starting playback: {str(e)}"
    
def stop_song():
    global spotify
    try:
        spotify.pause_playback()
    except spotipy.SpotifyException as e:
        return f"Error in pausing playback: {str(e)}"
    
def next_song():
    global spotify
    try:
        spotify.next_track()
    except spotipy.SpotifyException as e:
        return f"Error in skipping to next playback: {str(e)}"

def previous_song():
    global spotify
    try:
        spotify.previous_track()
    except spotipy.SpotifyException as e:
        return f"Error in skipping to previous playback: {str(e)}"
    
def volume_control():
    return
    
spotify = spotify_authenticate(client_id, client_secret, redirect_uri, username)