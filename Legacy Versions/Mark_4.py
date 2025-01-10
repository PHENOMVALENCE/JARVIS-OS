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
import asyncio
from icrawler.builtin import GoogleImageCrawler
import os
from Utilities import Spot
import ollama
from pygame import mixer
import cv2
import numpy as np
import smtplib
from email.message import EmailMessage
from Utilities import constants
from Utilities.VolumeHandControl import mainer
#from scroll_volume_combo import mainer
conversation_history = []


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

def send_to_llama(message):
  try:
    system_call = open(constants.system_call_file, "r")
    system_message = system_call.read()

    # I also want you to ask questions to be able to further help the user with the commands you can do, by offering up ideas to help the user with your capabilities. Try your best to offer ideas that could help the user, BUT ALWAYS ALWAYS ALWAYS ASK BEFORE YOU EXECUTE FUNCTION CALLS. 

        # Add the new question to the conversation history
    conversation_history.append({'role': 'user', 'content': message})

        # Include the system message and conversation history in the request
    response = ollama.chat(model='gemma2', messages=[
      {'role': 'system', 'content': system_message}, *conversation_history
      ])
        
        # Add the AI response to the conversation history
    conversation_history.append({'role': 'assistant', 'content': response['message']['content']})

    return response['message']['content']
  
  except ollama.ResponseError as e:
    print(f"An error occurred: {e}")
    return f"The request failed: {e}"

def send_to_GUI(jarvis_text, text, new_window):
  i = 0
  n_count = 0
  for character in text:
      i += 1
      if character == "\n":
        n_count += 1
      if i % 90 == 0:
          text = text[:i] + "\n" + text[i:]
          n_count += 1

  # Create a blank image
  image = np.zeros((n_count *  50 + 50, 1200, 3), dtype=np.uint8)
  image[:] = (0, 0, 0) # set white background

  textbook = text.split("\n")

  font = cv2.FONT_HERSHEY_TRIPLEX
  i = 0
  font_scale = .6
  color = (255, 255, 255)  # Black
  thickness = 1
  for texts in textbook:
      position = (10, 25 + 30 * i)
      cv2.putText(image, texts, position, font, font_scale, color, thickness)
      i += 1

  # Save the image
  if jarvis_text:
      cv2.imwrite(constants.jarvis_text_image, image)
      if new_window:
          while True:
              cv2.imshow("Hit 'esc' to leave image, JARVIS will not continue until then", image)
              key = cv2.waitKey(10)
              if key == 27:                                    #Esc key to exit the camera
                  cv2.destroyWindow("Hit 'esc' to leave image, JARVIS will not continue until then")
                  break
  else:
      cv2.imwrite(constants.user_text_image, image)
      if new_window:
          while True:
              cv2.imshow("Hit 'esc' to leave image, JARVIS will not continue until then", image)
              key = cv2.waitKey(10)
              if key == 27:                                    #Esc key to exit the camera
                  cv2.destroyWindow("Hit 'esc' to leave image, JARVIS will not continue until then")
                  break

def Listen(loop: bool, dictate: bool):
  
  #Initializes whisper, a function that allows the user to speak and it will output text.
  #If there is no speech in the time recognized by the "timeout" variable, the program will
  #shift to the "stasis_protocol" function. If there is text, it is sent back to the main function to be processed
  #the loop setting is set to "False", which is standard
  mixer.music.load(constants.mic_beep)
  mixer.music.play()
  cv2.imwrite(constants.GUI_mic_png, cv2.imread(constants.mic_png))
  if not loop:
    try:
      result = mic.listen(timeout = 10)
      result = result.lower()
      mixer.music.play()
      cv2.imwrite(constants.GUI_mic_png, cv2.imread(constants.background_png))
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
  
  Spot.stop_song()

  if len(GPT_response.split(" ")) > 70:
    new_GPT_response = "I have compiled a catalog of information regarding your request. Hit 'escape' when you want to continue"
    send_to_GUI(True, new_GPT_response, False)
    engine = pyttsx3.init()
    engine.say(new_GPT_response)
    engine.runAndWait()
    send_to_GUI(True, GPT_response, True)
    return
  
  send_to_GUI(True, GPT_response, False)
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
  speech = GPT_response.split("#")[0]
  engine = pyttsx3.init()
  engine.say(speech)
  engine.runAndWait()

def stasis_protocol(pause = False):
        
  #If whisper doesn't detect any speech in the alloted time window, you will be sent to this function.
  #It waits for the wake-word "JARVIS" to be said, and then picks up the conversation where you left off.
  #I am using pvporcupine to do this.      
        
  #constants that will be changed later      
  porcupine = None
  pa = None
  audio_stream = None

  mixer.music.load(constants.mute_beep)
  mixer.music.play()
  if pause == False:
    Spot.play_song()

  try:
    
    #Changes the constants into usable executable statements
    porcupine = pvporcupine.create(keywords = ['jarvis'], sensitivities= [0.5], access_key = constants.porcupine_API_key)
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
  if "-" in intent:
    try:
      save_message = intent.split("-")[2]
    except:
      pass
    query = intent.split("-")[1]
    intent = intent.split("-")[0]
    
  if "mute" in intent:
    print("\nSwitching to stasis protocols and will await your command.\n")
    stasis_protocol()    

  if "search" in intent:
    files = os.listdir("./images")
    [os.remove(os.path.join("./images", file)) for file in files]
    search_google_images(query)
    try:
      Image.open(f"./images/000001.jpg").show()
    except:
      Image.open("./images/000001.png").show()

  if "google" in intent:
    string = search_google_text(query)
    jarvis_response = send_to_llama(string)
    print("J.A.R.V.I.S: " + jarvis_response)
    Speak(jarvis_response)
    return

  elif "image" in intent:
    image_generation(query)
    return

  elif "vision" in intent:
    vision(query)
    return

  elif "spotify" in intent:
    spotify_info = Spot.get_current_song()
    query = "System Info: " + str(spotify_info)
    print(query)
    jarvis_response = send_to_llama(query)
    print("J.A.R.V.I.S: " + jarvis_response)
    Speak(jarvis_response)
    stasis_protocol()

  elif "save" in intent:
    save_text(query, save_message)
    print(f"J.A.R.V.I.S: Message saved under {query}.txt. How else can I assist sir?")
    Speak(f"Message saved under {query}.txt. How else can I assist sir?")

  elif "message" in intent:
    send_message(query, save_message)
    print("J.A.R.V.I.S: Message successfully sent sir. How else can I assist?")
    Speak("Message successfully sent sir.")

  elif "play" in intent:
    Spot.play_song()
    stasis_protocol()
    
  elif "pause" in intent:
    Spot.stop_song()
    stasis_protocol(pause = True)
    
  elif "skip" in intent:
    Spot.next_song()
    stasis_protocol()

  elif "previous" in intent:
    Spot.previous_song()
    stasis_protocol()

  elif "analyze" in intent:
    print("Go ahead and upload the file you need me to analyze now")
    Speak("Go ahead and upload the file you need me to analyze now")
    analyze_file(query)

def search_google_images(query):
  google_Crawler = GoogleImageCrawler(storage = ({"root_dir": constants.image_search_root_dir}))
  google_Crawler.crawl(keyword = query, max_num = 1)

def search_google_text(query):
  # Replace with your actual API key
  api_key = constants.google_search_API_key

  # Set up the parameters
  params = {
      'q': query,
      'api_key': api_key
  }

  # Make the request to SerpApi
  response = requests.get('https://serpapi.com/search.json', params=params)

  # Check if the request was successful
  if response.status_code == 200:
    # Parse the JSON response
    results = response.json()

    # Extract and print the snippets
    snippet_string = f"System results for {query}:\n"
    for idx, result in enumerate(results['organic_results'], start=1):
      snippet = result.get('snippet', 'No snippet available').replace("...", "")
      snippet_string += f"Snippet {idx}: {snippet}\n"
    snippet_string += "Please parse these snippets provided and give the most accurate answer based on your understanding to the asked query above."
    print(snippet_string)
    return snippet_string
  else:
    print('Error:', response.status_code)

def image_generation(query):

  client = openai.OpenAI(api_key= constants.OpenAI_API_key)

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

  print("J.A.R.V.I.S: Here is the image you requested sir. Please be sure to close the image to continue.")
  Speak("Here is the image you requested sir. Please be sure to close the image to continue.")

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
  Speak("2")
  sleep(1)
  message = message.replace("2", "1")
  print(message)
  Speak("1")
  sleep(1)
  print("Scanning now!!")
  Speak("Scanning now!!")

  # OpenAI API Key
  api_key = constants.OpenAI_API_key

  # Function to encode the image
  def encode_image(image_path):
    with open(image_path, "rb") as image_file:
      return base64.b64encode(image_file.read()).decode('utf-8')

  # Path to your image
  image_path = constants.vision_image

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
    "max_tokens": 200
  }

  response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
  try:
    jarvis_response = send_to_llama('System Message:' + response.json()["choices"][0]["message"]["content"])
    #print('System Message:' + response.json()["choices"][0]["message"]["content"])
    print("\nJ.A.R.V.I.S:" + jarvis_response)
    Speak(jarvis_response)

  except:
    jarvis_response = send_to_llama("Error: Image could not be parsed.")
    print("\nJ.A.R.V.I.S:" + jarvis_response)
    Speak(jarvis_response)

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

      api_key = constants.OpenAI_API_key

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
          "max_tokens": 200
      }

      response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
      try:
        jarvis_response = send_to_llama('System Message:' + response.json()["choices"][0]["message"]["content"])
        #print('System Message:' + response.json()["choices"][0]["message"]["content"])
        print("\nJ.A.R.V.I.S:" + jarvis_response)
        Speak(jarvis_response)

      except:
        jarvis_response = send_to_llama("Error: Image could not be parsed.")
        print("\nJ.A.R.V.I.S:" + jarvis_response)
        Speak(jarvis_response)
  else:
      Speak("I'm sorry sir, I didn't recieve a file.")
      print("I'm sorry sir, I didn't recieve a file.")

def save_text(filename, message):
  file = open(f"{constants.log_files_root_dir}\\{filename}.txt", "w")
  file.write(message)
  file.close()

def send_message(recipient, message):

  if "cole" in recipient:
    recipient = contact_list["cole"]
  elif "grampy" in recipient:
    recipient = contact_list["grampy"]
  elif "katie stout" in recipient:
    recipient = contact_list["katie stout"]
  elif "allen stout" in recipient:
    recipient = contact_list["allen stout"]
  elif "aaron hacker" in recipient:
    recipient = contact_list["aaron hacker"] 

  msg = EmailMessage()
  msg.set_content(message)
  msg['subject'] = ''
  msg['to'] = recipient

  user = "colehacker381@gmail.com"
  msg['from'] = user
  password = "flwi dfui dbxd pwho"
  
  server = smtplib.SMTP("smtp.gmail.com", 587)
  server.starttls()
  server.login(user, password)
  server.send_message(msg)
  server.quit()

##############################################
##########-CONSTANTS AND API KEYS-############
##############################################

contact_list = {
  "cole": "4632099000@vtext.com",
  "grampy": "3177142579@vtext.com",
  "katie stout": "3173844858@vtext.com",
  "aaron hacker": "3175011338@vtext.com",
  "allen stout": "3172131333@vtext.com"
}

client = openai.OpenAI(api_key= constants.OpenAI_API_key)
mixer.init()

# Retrieve the assistant and thread
assistant = client.beta.assistants.retrieve(constants.OpenAI_assistant_ID)
thread = client.beta.threads.retrieve(constants.OpenAI_thread_ID)

#elevenlabs.set_api_key(constants.eleven_labs_API_key)

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
    #result = input("Type now: ")
    send_to_GUI(False, result, False)

    print("\nCole: " + result)
    result = result + " " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if len(result.split(" ")) > 30:
      print(f"\nJ.A.R.V.I.S: Understood, give me a few seconds to process.")
      Speak("Understood, give me a few seconds to process.")
    jarvis_response = send_to_llama(result)
    print(f"\nJ.A.R.V.I.S: {jarvis_response}")
    Speak(jarvis_response)
    
    if len(jarvis_response.split('#')) > 1:
      command = jarvis_response.split('#')[1]
      executable_functions(command)

if __name__ == '__main__':
  threading.Thread(target=mainer).start()
  threading.Thread(target=main).start()
  #main()