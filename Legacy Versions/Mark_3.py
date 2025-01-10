##############################################
######-WHISPER SPEECH TO TEXT OPTIONS-########
##############################################

# @click.command()
# @click.option("--model", default="small", help="Model to use", type=click.Choice(["tiny","base", "small","medium","large","large-v2","large-v3"]))
# @click.option("--device", default=("cuda" if torch.cuda.is_available() else "cpu"), help="Device to use", type=click.Choice(["cpu","cuda","mps"]))
# @click.option("--english", default=False, help="Whether to use English model",is_flag=True, type=bool)
# @click.option("--verbose", default=False, help="Whether to print verbose output", is_flag=True,type=bool)
# @click.option("--energy", default=300, help="Energy level for mic to detect", type=int)
# @click.option("--dynamic_energy", default=False,is_flag=True, help="Flag to enable dynamic energy", type=bool)
# @click.option("--pause", default=0.8, help="Pause time before entry ends", type=float)
# @click.option("--save_file",default=False, help="Flag to save file", is_flag=True,type=bool)
# @click.option("--loop", default=False, help="Flag to loop", is_flag=True,type=bool)
# @click.option("--dictate", default=False, help="Flag to dictate (implies loop)", is_flag=True,type=bool)
# @click.option("--mic_index", default=None, help="Mic index to use", type=int)
# @click.option("--list_devices",default=False, help="Flag to list devices", is_flag=True,type=bool)
# @click.option("--faster",default=False, help="Use faster_whisper implementation", is_flag=True,type=bool)
# @click.option("--hallucinate_threshold",default=400, help="Raise this to reduce hallucinations.  Lower this to activate more often.", is_flag=True,type=int)

##############################################
#############-IMPORT LIBRARIES-###############
##############################################

import openai # For sending text to chatGPT to be processed
import multiprocessing as mp # For running two or more functions (JARVIS Text-to-Speech and Whisper) at once
import torch # For importing public libraries for use
from whisper_mic import WhisperMic #For Whisper Speech-to-Text
import elevenlabs # For elevenlabs text-to-speech (before they cancelled my subscription sadly.)
import pyaudio # For the wake word recognition
import pvporcupine # Also For the wake word recognition
import struct # To help store and transfer files
import datetime # To find date and time
from pydub import AudioSegment # Gets the audio from the JARVIS output file
from pydub.playback import play # Plays the audio from the JARVIS output file
import pyttsx3 # For text-to-speech if all else fails
from time import sleep, time #For finding current time and sleeping computer
import wave #Used to parse .wav files
import requests #To take files out of the computer
import threading #For running two or more functions at once
from PIL import Image #For displaying images
from io import BytesIO #For wrapping images in a image editor
from tkinter import filedialog
import base64
import python_weather
import asyncio
from icrawler.builtin import GoogleImageCrawler
import os
import Spot
from Combo_copy import mainer

##############################################
#############-THE JUICY STUFF-################
##############################################

def find_time():
  
  # Finds the time of day through the datetime library
  current_hour = datetime.datetime.now().hour
  if current_hour >= 0 and current_hour < 12:
    time_of_day = "morning"
  elif current_hour >= 12 and current_hour < 16:
    time_of_day = "afternoon"
  else:
    time_of_day = "evening"
  return time_of_day  

def send_to_chatGPT(message):
    global thread
    client.beta.threads.messages.create(thread.id, role="user", content = message)
    run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant.id)
    
    while (run_status := client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)).status != 'completed':
        if run_status.status == 'failed':
            return "The run failed."
        sleep(1)
    
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    return messages.data[0].content[0].text.value

def Listen(loop: bool, dictate: bool):
  
  #Initializes whisper, a function that allows the user to speak and it will output text.
  #If there is no speech in the time recognized by the "timeout" variable, the program will
  #shift to the "stasis_protocol" function. If there is text, it is sent back to the main function to be processed
  #the loop setting is set to "False", which is standard
  
  if not loop:
    try:
      result = mic.listen(timeout = 10)
      result = result.lower()
      while "timeout: no speech detected within the specified time." in result:
        print("\nSwitching to stasis protocols and will await your command.\n")
        stasis_protocol()
        result = mic.listen(timeout = 10)
        result = result.lower()
      else:
        return result
    except KeyboardInterrupt:
        print("Operation interrupted successfully")
  #if the loop setting is set to "True", meaning it will loop infinitely. It will never be used, but it's good to have options just in case :)
  else:
    try:
      mic.listen_loop(dictate=dictate,phrase_time_limit=2)
    except KeyboardInterrupt:
      print("Operation interrupted successfully")

def Speak(GPT_response):
  
  #Prints the response from chatgpt, and then saves the text-to-speech to an output file and plays it.
  #Also some other options, elevenlabs cancelled my subscription, but the code for using it is there.
  #If all else fails, the microsoft code for text-to-speech is there but it's very bad and basically ancient.
        
  # print(f"\nJ.A.R.V.I.S: {GPT_response}")	

  # ######-CODE FOR OPENAI TEXT-TO-SPEECH WITH STREAMING-###### -> https://community.openai.com/t/streaming-from-text-to-speech-api/493784/25
  # url = "https://api.openai.com/v1/audio/speech"
  # headers = {
  #   "Authorization": "Bearer REDACTED_OPENAI_API_KEY",
  # }

  # data = {
  #     "model": "tts-1",
  #     "input": f"{GPT_response}",
  #     "voice": "onyx",
  #     "response_format": "wav",
  # }
  
  # response = requests.post(url, headers=headers, json=data, stream=True)
  # response = requests.post('https://api.openai.com/v1/audio/speech', headers=headers, json=data, stream=True)

  # CHUNK_SIZE = 1024

  # if response.ok:
  #   #print(f"Time to first byte: {int((time() - start_time) * 1000)} ms") <-- for testing streaming
  #   with wave.open(response.raw, 'rb') as wf:
  #     p = pyaudio.PyAudio()
  #     stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
  #                     channels=wf.getnchannels(),
  #                     rate=wf.getframerate(),
  #                     output=True)

  #     while len(data := wf.readframes(CHUNK_SIZE)): 
  #       stream.write(data)
  #     # Sleep to make sure playback has finished before closing
  #     sleep(0.1)
  #     stream.close()
  #     p.terminate()
  # else:
  #   response.raise_for_status()
  
  
  
  ######-CODE FOR OPENAI TEXT-TO-SPEECH WITHOUT STREAMING-######
  # response = openai.OpenAI(api_key='REDACTED_OPENAI_API_KEY').audio.speech.create(
  #     model="tts-1",
  #     voice="onyx", #"onyx" for male voice, "nova" for female voice
  #     input=f"{GPT_response}"
  # )
  # response.stream_to_file("output.mp3")
  # sleep(.25)
  # audio = AudioSegment.from_mp3("C:\\Users\\coleh\\OneDrive\\Coding\\Python folder\\J.A.R.V.I.S\\output.mp3")
  # play(audio)
  
  ######-CODE FOR ELEVENLABS-######
  # voice = elevenlabs.Voice(
  #   voice_id =  "W9GV3eOlVsQY5K64iRWp",
  #   settings = elevenlabs.VoiceSettings(
  #   stability = 0.75,
  #   similarity_boost = 0.5,
  #   use_speaker_boost= False
  #   )
  # )
  
  # audio = elevenlabs.generate(
  #   text = f"{GPT_response}",
  #   voice = voice,
  #   latency= 4
  # )
  # elevenlabs.play(audio)
  
  #####-CODE FOR MICROSOFT PYTTSX3-######
  engine = pyttsx3.init()
  engine.say(GPT_response)
  engine.runAndWait()

def stasis_protocol():
        
  #If whisper doesn't detect any speech in the alloted time window, you will be sent to this function.
  #It waits for the wake-word "JARVIS" to be said, and then picks up the conversation where you left off.
  #I am using pvporcupine to do this.      
        
  #constants that will be changed later      
  porcupine = None
  pa = None
  audio_stream = None

  try:
    
    #Changes the constants into usable executable statements
    porcupine = pvporcupine.create(keywords = ['jarvis'], sensitivities= [0.5], access_key = "U1wcQNpaj7FKCzXxnA/D/Th1Mn1yKJsF/v0yjr9evel7G0oqi/wx+A==")
    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate = porcupine.sample_rate,
        channels = 1,
        format = pyaudio.paInt16,
        input = True,
        frames_per_buffer= porcupine.frame_length
      )
      
    #Waits for the user input and then continues the process.
    while True:
      pcm = audio_stream.read(porcupine.frame_length)
      pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

      keyword_index = porcupine.process(pcm)
      if keyword_index >= 0:
        #Where the magic happens, basically just runs the initiallization code inside of this function forever,
        #or until the terminal is killed
          print("At your service, sir.")
          Speak("At your service sir.")
          return

  finally:
  
    #Deletes all of the saved files it has run through, so everything is safe and secure.
    if porcupine is not None:
      porcupine.delete()
          
    if audio_stream is not None:
      audio_stream.close()
      
    if pa is not None:
      pa.terminate()

def executable_functions(intent):
  if "mute" in intent:
    print("\nSwitching to stasis protocols and will await your command.\n")
    stasis_protocol()

  if "weather" in intent:
    try:
      weather_description = asyncio.run(get_weather("Indianapolis"))
      query = "System Info: " + str(weather_description)
      print(query)
      jarvis_response = send_to_chatGPT(query)
      print("J.A.R.V.I.S: " + jarvis_response)
      Speak(jarvis_response)
    except RuntimeError as e:
      print(f"Cannot run the weather function due to error: {e}")
      jarvis_response = send_to_chatGPT(f"Cannot run the weather function due to error: {e}")
      print("J.A.R.V.I.S: " + jarvis_response)
      Speak(jarvis_response)     

  if "search" in intent:
    files = os.listdir("./images")
    [os.remove(os.path.join("./images", file)) for file in files]
    query = intent.split("-")[1]
    search_google(query)
    try:
      Image.open(f"./images/000001.jpg").show()
    except:
      Image.open("./images/000001.png").show()

  elif "image" in intent:
    query = intent.split("-")[1]
    image_generation(query)
    Speak("Here is the image you requested sir.")
    return

  elif "vision" in intent:
    query = intent.split("-")[1]
    vision(query)
    return

  elif "spotify" in intent:
    spotify_info = Spot.get_current_song()
    query = "System Info: " + str(spotify_info)
    print(query)
    jarvis_response = send_to_chatGPT(query)
    print("J.A.R.V.I.S: " + jarvis_response)
    Speak(jarvis_response)
    stasis_protocol()

  elif "play" in intent:
    Spot.play_song()
    stasis_protocol()
    
  elif "pause" in intent:
    Spot.stop_song()
    stasis_protocol()
    
  elif "skip" in intent:
    Spot.next_song()
    stasis_protocol()

  elif "previous" in intent:
    Spot.previous_song()
    stasis_protocol()

  elif "analyze" in intent:
    query = intent.split("-")[1]
    print("Go ahead and upload the file you need me to analyze now")
    Speak("Go ahead and upload the file you need me to analyze now")
    analyze_file(query)

async def get_weather(location):
  try:
    async with python_weather.Client(unit = python_weather.IMPERIAL) as client:
      weather = await client.get(location)
      return weather
  finally: 
    await client.close()

def search_google(query):
  google_Crawler = GoogleImageCrawler(storage = ({"root_dir": "C:\\Users\\coleh\\OneDrive\\Coding\\Python folder\\J.A.R.V.I.S\\images"}))
  google_Crawler.crawl(keyword = query, max_num = 1)

def image_generation(query):

  client = openai.OpenAI(api_key='REDACTED_OPENAI_API_KEY')

  response = client.images.generate(
    model="dall-e-3",
    prompt= query,
    size="1024x1024",
    quality="standard",
    n=1,
  )
  image_url = response.data[0].url
  # Fetch the image from the URL
  response = requests.get(image_url)
  # Open the image
  img = Image.open(BytesIO(response.content))
  img.show()
  return

def vision(result):

  Speak("Scanning in 3 seconds")
  message = "Scanning in 3..."
  print(message)
  sleep(1)
  message = message.replace("3", "2")
  print(message)
  sleep(1)
  message = message.replace("2", "1")
  print(message)
  sleep(1)
  print("Scanning now!!")

  # OpenAI API Key
  api_key = "REDACTED_OPENAI_API_KEY"

  # Function to encode the image
  def encode_image(image_path):
    with open(image_path, "rb") as image_file:
      return base64.b64encode(image_file.read()).decode('utf-8')

  # Path to your image
  image_path = "C:\\Users\\coleh\\OneDrive\\Coding\\Python folder\\J.A.R.V.I.S\\Vision.jpg"

  # Getting the base64 string
  base64_image = encode_image(image_path)

  headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
  }

  payload = {
    "model": "gpt-4o",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": f"Tell me about the image in the context of this prompt: {result}"
          },
          {
            "type": "image_url",
            "image_url": {
              "url": f"data:image/jpeg;base64,{base64_image}"
            }
          }
        ]
      }
    ],
    "max_tokens": 75
  }

  response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

  print(response.json()["choices"][0]["message"]["content"])
  Speak(response.json()["choices"][0]["message"]["content"])
  return

def analyze_file(result):
  
  # Function to encode the image
  def encode_image(image_path):
      with open(image_path, "rb") as image_file:
          return base64.b64encode(image_file.read()).decode('utf-8')

  file_path = filedialog.askopenfilename()
  if file_path is not None:
      file_path_list = file_path.split('/')
      filename = file_path_list[-1]
      print("Selected:", filename)
      
      import base64
      import requests

      # OpenAI API K

      api_key = "REDACTED_OPENAI_API_KEY"

      # Path to your image
      image_path = file_path

      # Getting the base64 string
      base64_image = encode_image(image_path)

      headers = {
          "Content-Type": "application/json",
          "Authorization": f"Bearer {api_key}"
      }

      payload = {
          "model": "gpt-4o",
          "messages": [
          {
              "role": "user",
              "content": [
              {
                  "type": "text",
                  "text": f"You are given a file with both text and diagrams. Please give the user a concise answer to this prompt: {result}"
              },
              {
                  "type": "image_url",
                  "image_url": {
                  "url": f"data:image/jpeg;base64,{base64_image}"
                  }
              }
              ]
          }
          ],
          "max_tokens": 100
      }

      response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

      Speak(response.json()["choices"][0]["message"]["content"])
      print(response.json()["choices"][0]["message"]["content"])
  else:
      Speak("I'm sorry sir, I didn't recieve a file.")
      print("I'm sorry sir, I didn't recieve a file.")

##############################################
##########-CONSTANTS AND API KEYS-############
##############################################

client = openai.OpenAI(api_key="REDACTED_OPENAI_API_KEY")
assistant_id = "asst_KkKSIdYGRFTymUd5cMQJ5nt9"
thread_id = "thread_lwLouuysNzTlCGB80QurqnWG"
# Retrieve the assistant and thread
assistant = client.beta.assistants.retrieve(assistant_id)
thread = client.beta.threads.retrieve(thread_id)

#elevenlabs.set_api_key("c70867fd4ab0c0aef2d52da29aa1137e")

#Constants for different parts of the program
loop = False
dictate = False

time_of_day = find_time()

mic = WhisperMic(model="base", english=False, verbose=False, energy=300, pause=0.8, dynamic_energy=False, save_file=False, device=("cuda" if torch.cuda.is_available() else "cpu"),mic_index=None,implementation="faster_whisper",hallucinate_threshold=000)

jarvis_response = f"Good {time_of_day} and welcome back sir! How can we get started today?"
print("Initializing startup sequence...")
Speak(jarvis_response)
print("Say something!")

##############################################
##########-PROGRAM INITIALIZATION-############
##############################################

def main():
  while True:
    #gets the user input from the whisper function
    result = Listen(loop, dictate)
    print("\nCole: " + result)
    result = result + " " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #print(result)
    jarvis_response = send_to_chatGPT(result)
    print(f"\nJ.A.R.V.I.S: {jarvis_response}")
    speech = jarvis_response.split("#")[0]
    Speak(speech)
    
    if len(jarvis_response.split('#')) > 1:
      command = jarvis_response.split('#')[1]
      executable_functions(command)

if __name__ == '__main__':
  # threading.Thread(target=mainer).start()
  # threading.Thread(target=main).start()
  main()