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
from whisper_mic import WhisperMic #For Whisper Speech -to-Text
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
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import re
from selenium.webdriver.common.by import By

##############################################
#############-THE JUICY STUFF-################
##############################################

def find_time():
  
  # Finds the time of day through the datetime library
  current_hour = datetime.datetime.now().hour
  if current_hour >= 0 and current_hour < 12:
    time_of_day = "morning"
  elif current_hour >= 12 and current_hour < 4:
    time_of_day = "afternoon"
  else:
    time_of_day = "evening"
  return time_of_day  

def send_to_chatGPT(messages, model="gpt-3.5-turbo"):
  
  #sends the text inputted by the user through Speech-to-text to chat gpt for a response.
  response = openai.chat.completions.create(model=model, messages=messages, max_tokens=1000, n=1, stop=None, temperature=0.5)
  message = response.choices[0].message.content
  messages.append(response.choices[0].message)
  return message

def create_speak_process(response):
  
  #Creates a JARVIS speak process factory, as a process cannot be used more
  #than once so it needs to be generated again and again to be used infinetly.
  return mp.Process(target=Speak, args=[response])

def create_my_speech_process(queue):
  
  #Creates a User listening process factory, as a process cannot be used more
  #than once so it needs to be generated again and again to be used infinetly.
  return mp.Process(target=Listen, args=[loop, dictate, queue])

def Listen(loop: bool, dictate: bool, queue):
  
  #Initializes whisper, a function that allows the user to speak and it will output text.
  #If there is no speech in the time recognized by the "timeout" variable, the program will
  #shift to the "stasis_protocol" function. If there is text, it is wrapped up into a queue
  #and sent back to chat gpt to be processed.
  #if the loop setting is set to "False", which is standard
  timeout = 10
  if not loop:
    try:
      result = mic.listen(timeout=timeout)
      executable_functions(result, timeout, queue)
      return
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
        
  print(f"\nJ.A.R.V.I.S: {GPT_response}")	

  ######-CODE FOR OPENAI TEXT-TO-SPEECH WITH STREAMING-###### -> https://community.openai.com/t/streaming-from-text-to-speech-api/493784/25
  url = "https://api.openai.com/v1/audio/speech"
  headers = {
      "Authorization": 'Bearer REDACTED_OPENAI_API_KEY',
  }

  data = {
      "model": "tts-1",
      "input": f"{GPT_response}",
      "voice": "onyx",
      "response_format": "wav",
  }
  
  response = requests.post(url, headers=headers, json=data, stream=True)
  response = requests.post('https://api.openai.com/v1/audio/speech', headers=headers, json=data, stream=True)

  CHUNK_SIZE = 1024

  if response.ok:
    #print(f"Time to first byte: {int((time() - start_time) * 1000)} ms") <-- for testing streaming
    with wave.open(response.raw, 'rb') as wf:
      p = pyaudio.PyAudio()
      stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                      channels=wf.getnchannels(),
                      rate=wf.getframerate(),
                      output=True)

      while len(data := wf.readframes(CHUNK_SIZE)): 
        stream.write(data)
      # Sleep to make sure playback has finished before closing
      sleep(1)
      stream.close()
      p.terminate()
  else:
    response.raise_for_status()
  
  
  
  ######-CODE FOR OPENAI TEXT-TO-SPEECH WITHOUT STREAMING-######
  # response = openai.OpenAI(api_key='REDACTED_OPENAI_API_KEY').audio.speech.create(
  #     model="tts-1",
  #     voice="onyx", #"onyx" for male voice, "nova" for female voice
  #     input=f"{GPT_response}"
  # )
  # response.stream_to_file("output.mp3")
  # audio = AudioSegment.from_mp3("output.mp3")
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
  
  ######-CODE FOR MICROSOFT PYTTSX3-######
  # engine = pyttsx3.init()
  # engine.say(GPT_response)
  # engine.runAndWait()

def stasis_protocol(queue):
        
  #If whisper doesn't detect any speech in the alloted time window, you will be sent to this function.
  #It waits for the wake-word "JARVIS" to be said, and then picks up the conversation where you left off.
  #I am using pvporcupine to do this.      
        
  #constants that will be changed later      
  porcupine = None
  pa = None
  audio_stream = None
  
  #Running the speech factories to be used on wake-up
  speak = create_speak_process("At your service, sir.")
  my_speech = create_my_speech_process(queue)

  try:
    
    #Changes the constants into usable executable statements
    porcupine = pvporcupine.create(keywords = ['jarvis'], sensitivities= [0.4])
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
        while True:
          
          #Begins the two processes and uses .join() to end them at the same time
          speak.start()
          my_speech.start()
          speak.join()
          my_speech.join()
          
          #gets the user input from the storage queue
          user_result_string = queue.get()
          
          #appends the results to a list and sends to chat gpt to process
          messages.append({"role": "user", "content": f"{user_result_string}"})
          jarvis_response = send_to_chatGPT(messages)
          
          #saves the input and response to the memory and starts the process factory to start the process over
          memory.save_conversation(user_result_string, jarvis_response)
          speak = create_speak_process(jarvis_response)
          my_speech = create_my_speech_process(queue)

  finally:
  
    #Deletes all of the saved files it has run through, so everything is safe and secure.
    if porcupine is not None:
      porcupine.delete()
          
    if audio_stream is not None:
      audio_stream.close()
      
    if pa is not None:
      pa.terminate()

def executable_functions(result, timeout, queue):
  
  #This is where all of the magic happens. Based on the input of 
  #the user, Jarvis will perform different tasks regarding what is
  #in the text provided. (eg. if "mute" is in the text, then Jarvis
  #will automatically switch to stasis_protocol)
  
  if "Timeout: No speech detected within the specified time." in result:
    print(f"Timeout: No speech detected within the specified time of {timeout} seconds.\nSwitching to stasis protocols and will await your command.")
    stasis_protocol(queue)
    
  elif "mute" in result:
    print("\nCole: " + result)
    print("Switching to stasis protocols and will await your command.")
    stasis_protocol(queue)
  
  elif ("Generate" in result or "generate" in result 
        or "give me" in result or "Give me" in result 
        or "Create" in result or "create" in result) and ("image" in result or "picture" in result):
    
    print("\nCole: " + result)
    Speak('Certainly sir. Generating your image now.')
    image_generation(result)
    result = 'Say: "Image successfully generated, is there anything else I can do for you sir?"'
    queue.put(result)
  
  elif ("internet" in result or "web" in result or "Selenium" in result):
    
    length = 20
    print("\nCole: " + result)
    text = internet_accessability(result)
    result = f'Give me a {length} word summary of this text: {text} and then say: Is there anything else I can do for you sir?'
    queue.put(result)
    
  else:
    print("\nCole: " + result)
    queue.put(result)

def internet_accessability(result):
  
  if "youtube" in result or "Youttube" in result or "YouTube" in result or "youTube" in result or "you too" in result:
    Speak("Certainly sir. Opening the page now.")
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)
    driver=webdriver.Chrome(options=options)
    driver.get("https://www.youtube.com/")
    
  elif "topic" in result:
    
    speak = create_speak_process("Certainly sir. Opening the page now. What topic would you like to research?")
    my_speech = create_my_speech_process(queue)
    speak.start()
    my_speech.start()
    speak.join()
    my_speech.join()
    result = queue.get()
    
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)
    driver=webdriver.Chrome(options=options)
    driver.get('https://www.google.com/')
    search_query = driver.find_element(By.NAME, 'q')
    search_query.send_keys(result + 'wikipedia')
    search_query.send_keys(Keys.RETURN)
    
    wikipedia_page = driver.find_element(By.CSS_SELECTOR, 'h3[class="LC20lb MBeuO DKV0Md"]')
    wikipedia_page.click()

    text = driver.find_element(By.XPATH, '//*[@id="mw-content-text"]/div[1]/p[2]').text
    if text=='':
      text = driver.find_element(By.XPATH, f'//*[@id="mw-content-text"]/div[1]/p[3]').text
    text = re.sub("[\(\[].*?[\)\]]", "", text)
    driver.close()
    #print(text)
    return text

def image_generation(prompt):

  client = openai.OpenAI(api_key='REDACTED_OPENAI_API_KEY')

  response = client.images.generate(
    model="dall-e-3",
    prompt=prompt,
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

def spotify_player():
  pass

class Memory:
  
  #Creates a class that saves the two most recent lines from the user and from JARVIS
  #into a .txt file called "JARVIS_memory.txt". Upon start up, this file will be pushed into
  #chat gpt and will return no output, but primes the model to remember every conversation it
  #had previously. This will be optimized eventually, but for now, this is a good start.
  
  #Initializes the class
  def __init__(self, file_path):
    self.file_path = file_path

  #Saves the conversation to the .txt file with dates and times as well as the conversation
  def save_conversation(self, user_input, jarvis_response):
    with open(self.file_path, 'a') as file:
      timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      file.write(f"{timestamp} - User: {user_input}\n")
      file.write(f"{timestamp} - Jarvis: {jarvis_response}\n")
      file.write("\n")

  #calls the .txt file so that it can be sent to chat gpt later.
  def get_conversations(self):
    with open(self.file_path, 'r') as file:
      conversations = file.readlines()
    return conversations
  
  def restore_memory():
  
    #Sends the previous logs from the "JARVIS_memory.txt" file to chat gpt
    #to give it the concept of a "memory". It splits the entire log into
    #seperate lines to give bite sized info to chat gpt. I used threading 
    #in order to allow the main JARVIS function to run while also having
    #his memory reuploaded in the background.
    
    #WARNING! HAVING THIS OPEN WILL CONSUME A LARGE AMOUNT OF TOKENS
    #BASED ON HOW BIG THE MEMORY FILE IS. USE ONLY IF YOU HAVE A LOT OF
    #DISPENSIBLE MONEY THAT YOU CAN THROW AWAY ON A MEMORY FUNCTIONALITY.
    
    #Memory control switch is "restoration_module.start()". 
    #Find this by using Ctrl + F to look for it.
    
    print("Accessing memory logs...")
    memory_log = memory.get_conversations()
    for content in memory_log:
      content = content.strip()
      messages.append({"role": "user", "content": f"{content}"})
      send_to_chatGPT(messages)
    print("Memory successfully restored")

##############################################
##########-CONSTANTS AND API KEYS-############
##############################################

#API keys and initializing the memory send file
openai.api_key = 'REDACTED_OPENAI_API_KEY'
elevenlabs.set_api_key("c70867fd4ab0c0aef2d52da29aa1137e")
memory = Memory("JARVIS_memory.txt")

#Constants for different parts of the program
loop = False
dictate = False
count = 1
queue = mp.Queue()

#Gives JARVIS the inital start-up response, his prompt, and uses datetime to change the initial response accordingly
time_of_day = find_time()
timeout = 10 #controls how long whisper waits for speech before quitting, eg. 10 = 10 seconds of waiting
mic = WhisperMic(model="base", english=False, verbose=False, energy=300, pause=0.8, dynamic_energy=False, save_file=False, device=("cuda" if torch.cuda.is_available() else "cpu"),mic_index=None,implementation="whisper",hallucinate_threshold=000)
messages = [{"role": "user", "content": "You are a incredibly intelligent assistant that can give insightful answers in a very short response, but also have a sense of humor. Your name is Jarvis, and you also call me sir. You have a certain list of commands you can execute, and based on my input you can ask follow up questions that may help me and suit my needs for any projects I may come to you with. Here is the list of things you can do: Access the internet, generate an image, play music, and mute yourself."}]
initial_JARVIS_speech = mp.Process(target=Speak, args=[f"Good {time_of_day} sir! I am accounted for and ready to work, how can we get started?"])
initial_my_speech = mp.Process(target=Listen, args=[loop, dictate, queue])


##############################################
##########-PROGRAM INITIALIZATION-############
##############################################

def main(count):
  #Sends a thread to the restore_memory function to restore 
  #previous conversations to JARVIS
  restoration_module = threading.Thread(target=Memory.restore_memory, args=[])
  
  #Runs the processes of whisper and text-to-speech to simulate that
  #fluid conversational experience. I used multiprocessing to run the
  #two functions at the same time to make it seem more fluid than 
  #syncronous processing.
  print("Initializing startup sequence...")
  while True:
    #Using "count" variable to determine if this is a start-upsequence or not.
    #once count is changed, then it runs the loop using the users inputs.
    if count == 1:
      
      #Begins the two processes and uses .join() to end them at the same time
      initial_JARVIS_speech.start()
      initial_my_speech.start()
      #restoration_module.start()  <-- controls JARVIS's memory functionality.
      initial_JARVIS_speech.join()
      initial_my_speech.join()
      
      #gets the user input from the storage queue
      user_result_string = queue.get()
      
      #appends the results to a list and sends to chat gpt to process
      messages.append({"role": "user", "content": f"{user_result_string}"})
      jarvis_response = send_to_chatGPT(messages)
      
      #saves the input and response to the memory and starts the process factory to start the process over
      memory.save_conversation(user_result_string, jarvis_response)
      speak = create_speak_process(jarvis_response)
      my_speech = create_my_speech_process(queue)
      
      #Increase the count to move out of the start-up stages
      count += 1
    else:
      
      #Begins the two processes and uses .join() to end them at the same time
      speak.start()
      my_speech.start()
      speak.join()
      my_speech.join()
      
      #gets the user input from the storage queue
      user_result_string = queue.get()
      
      #appends the results to a list and sends to chat gpt to process
      messages.append({"role": "user", "content": f"{user_result_string}"})
      jarvis_response = send_to_chatGPT(messages)
      
      #saves the input and response to the memory and starts the process factory to start the process over
      memory.save_conversation(user_result_string, jarvis_response)
      speak = create_speak_process(jarvis_response)
      my_speech = create_my_speech_process(queue)

if __name__ == '__main__':
  main(count)