import spotipy
import numpy as np
from spotipy.oauth2 import SpotifyOAuth
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
try:
    import constants
except:
    from . import constants

devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(
IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume = interface.QueryInterface(IAudioEndpointVolume)

volumeRange = volume.GetVolumeRange()
minVolume = volumeRange[0]
maxVolume = volumeRange[1]

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

def add_to_queue(track_name, artist_name = None):

    if artist_name:
        results = spotify.search(q=f"track:{track_name} artist:{artist_name}", type='track')
    else:
        results = spotify.search(q=f"track:{track_name}", type='track')

    try:
        uri = results['tracks']['items'][0]['uri']
    except IndexError as e:    
        return f"System Message: Error in adding to queue: {str(e)}, please relate back to user" 
    except spotipy.SpotifyException as e: 
        return f"System Message: Error in adding to queue: {str(e)}, please relate back to user"
    
    spotify.add_to_queue(uri=uri)
    
def play_track(track_name, artist_name = None):
    if artist_name:
        results = spotify.search(q=f"track:{track_name} artist:{artist_name}", type='track')
    else:
        results = spotify.search(q=f"track:{track_name}", type='track')

    try:
        uri = results['tracks']['items'][0]['uri']
    except IndexError as e:    
        return f"System Message: Error in adding to queue: {str(e)}, please relate back to user" 
    except spotipy.SpotifyException as e: 
        return f"System Message: Error in adding to queue: {str(e)}, please relate back to user"
    
    spotify.start_playback(uris=[uri])

def volume_control(command, given_vol):
    given_vol = int(given_vol)
    given_vol /= 100
    if command == 'control':
        if given_vol <= 0:
            volume.SetMasterVolumeLevel(minVolume, None)
        elif given_vol >= 100:
            volume.SetMasterVolumeLevel(maxVolume, None)
        else:
            volume.SetMasterVolumeLevelScalar(given_vol, None)
    elif command == 'up':
        currentVolume = volume.GetMasterVolumeLevelScalar()
        currentVolume += given_vol
        if currentVolume <= 0:
            volume.SetMasterVolumeLevel(minVolume, None)
        elif currentVolume >= 1:
            volume.SetMasterVolumeLevel(maxVolume, None)
        else:
            volume.SetMasterVolumeLevelScalar(currentVolume, None)
    elif command == 'down':
        currentVolume = volume.GetMasterVolumeLevelScalar()
        currentVolume -= given_vol
        if currentVolume <= 0:
            volume.SetMasterVolumeLevel(minVolume, None)
        elif currentVolume >= 1:
            volume.SetMasterVolumeLevel(maxVolume, None)
        else:
            volume.SetMasterVolumeLevelScalar(currentVolume, None)




spotify = spotify_authenticate(constants.client_id, constants.client_secret, constants.redirect_uri, constants.username)
if __name__ == "__main__":
   #for testing
   volume_control('control', 40)