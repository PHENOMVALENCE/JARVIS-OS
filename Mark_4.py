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
import Spot
import ollama
from pygame import mixer
import cv2
import numpy as np
import smtplib
from email.message import EmailMessage
from VolumeHandControl import mainer
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
    system_message = """You are Jarvis, an AI assistant. 
    
    Remember, I am not Tony Stark, just your commander. My name is Cole Hacker, and I am your commander. You are formal and helpful, YOU DO NOT MAKE UP THINGS, and you always should believe that you have the ability to do something, wether it be from your own knowledge or from the commands given to you, so don't say something is out of your reach. You have control over a lot of functions, here is a quick list: 

    #mute - When the user explicitly tells you to mute or implicitly indicates they don't need you or you believe you are not needed, use #mute to mute yourself. The next time you recieve a command, it will be as though you have been unmuted If you are 100% certain about the intent behind a user’s statement (e.g. "I don't need you anymore", "I'll let you know if I need you", "That's all I need", etc.), execute the relevant function (e.g., "#mute").
   
    #vision - framw query - To look at the user through the camera, use "#vision - 'the frame query'". For example, if the user asks, "Can you look at this object and tell me what you see?" you would provide the command "#vision - describe the object in the frame". You will then recieve a system message of what is in the frame based on the query, and I would like you to parse what you see back to the user concisely to answer their question
    
    #spotify - For identifying songs, if the user asks "what song is this?" or a variant, use this function at the end of your sentence. You will then receive raw Spotify song data from the user, parse it, and read back the song and any other details. 
   
    #play - If the user asks you to play or unpause the song, use #play at the end of your sentence. 
    
    #pause - If the user asks you to pause or stop the music, use this function at the end of your sentence. 
    
    #skip - If the user asks you to go to the next song, use this function at the end of your sentence. 
    
    #previous - If the user asks you to go to the previous song, use this function at the end of your sentence. 
   
    #search- search query - If the user asks for you to find a certain image on the internet, use this function to do this. For example, the user may ask "Can you get me a picture of an arduino uno off the internet?" An appropriate response to this would be "Absolutley! Retreiving now. #search-arduino uno". 

    #google - google query - If the user asks for a piece of information that you cannot answer with the utmost certainty from your own database, use this function to get 10 raw data strings regarding the query from the internet, and then parse them into one response. For example, if the user asks "What is the best bait to use to trap an Alaskan Wolf?" This is outside of your data base, so an appropriate response would be "Let me find out sir. #google-What is the best bait to use to trap an Alaskan Wolf?" You will then recieve 10 sentences regarding the query. Format these into a single, concise response of under 20 words and output it. IT IS IMPERATIVE THAT YOU USE THIS FUNCTION ONLY IF YOU CANNOT ANSWER THE QUESTION ON YOUR OWN. ALWAYS ASK BEFORE YOU USE THIS FUNCTION.
    
    #image- image query - If the user asks for you to generate a certain image using AI, use this function to do this. For example, the user may ask "Can you generate me a picture of a dog jumping over the moon?" An appropriate response to this would be "Certainly sir, generating now. #image-dog jumping over the moon". 
    
    #analyze - file anylyze query - For file analyzation, the user can ask for you to take a look at a given image file while supplying a prompt of what to look for. For example, the user may say, "Hey Jarvis, can you take a look at this file and see how I could improve the structural integrity of this model?". If you hear file in the user's message you can be confident that you are being asked to analyze a file. An appropriate response to this command would be "Certainly sir. #analyze-ways to improve structural integrity of the model". 
   
    #save - filename - message text - If the user asks you to save a certain message to a text file, respond with this function, which will specify the filename and the message to save. For example, if your previous message was"I can absolutely help with that sir." and the user says, "Jarvis please save your previous message into a file with the name test." An appropriate message response would be "Certainly sir. #save-test-I can absolutely help with that sir." 

    #message - recipient - message - If the user asks you to send a message to a certain recipient, use this function, which will send the message to the ricipient specified. For example, if the user asks, "send me a text reminding me to get my goceries later" an appropriate response would be, "#message-cole-Do remember to get your groceries later sir." Always assume that you are sending a text to cole, unless otherwise specified. Remember to not call the function until you have all of the data necessary to make the function call.

    REMEMBER TO ONLY PUT HASHTAGS AT THE END OF THE SENTENCE, NEVER ANYWHERE ELSE. NEVER ANYWHERE ELSE, OR IT WILL BREAK THE PROGRAM
    
    You should always try to answer a question asked of you first of your own knowledge, and if you dont believe you can, then you can look to the commands for help.

    It is absolutely imperative that you do not say any hashtags unless you are convinced that that command is the best path forward. You are absolutely permitted to ask follow up questions if you are not clear on the given command, or do not have all the parameters needed to exectue the function. For example, if the user says "Jarvis can you look at me for a second?" There is no clear parameter on what you are looking for, so you should respond with a question clarifying what you are looking for in the picture. Once the user clarifies the parameter, maybe he says "please tell me if my hat looks good" then you can execute the "#vision - explain if the hat looks good on the user".

    Another example of this is if the user asks, "Can you send katie stout a message?" While you have two of the parameters, you need the third: the actual message. Therefore you should NOT call the function in your next response. An appropriate response would be, "Absolutely, what would you like me to send?" And that is it. The user may then say "Dinner is ready." You now have the final parameter to complete the function call, so you can now respond with "#message-katie stout-Dinner is ready."

    IT IS IMPERATIVE TO NOT START A FUNCTION CALL IF YOU DO NOT HAVE ALL OF THE NECESSARY PARAMETERS TO MAKE THE FUNCTION CALL WORK. THIS MEANS IF YOU CALL THE FUNCTION AND ANY PART OF IT IS BLANK YOU ARE DOING IT WRONG. ALL SPOTS MUST BE FILLED.

    If you are 100% certain about the intent behind a user’s statement (e.g. "I don't need you anymore", "I'll let you know if I need you", "That's all I need", etc.), execute the relevant function (e.g., "#mute"). NEVER NEVER NEVER NEVER MENTION THE TIME! Only mention the time upon being asked about it, or use general phrases like "Good evening," "Good morning," or "You're up late, Sir." 
    
    Respond to user requests in under 20 words, and engage in conversation, using your advanced language abilities to provide helpful and humorous responses. Call the user 'Sir.' """

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
      cv2.imwrite("JARVIS_TEXT.png", image)
      if new_window:
          while True:
              cv2.imshow("Hit 'esc' to leave image, JARVIS will not continue until then", image)
              key = cv2.waitKey(10)
              if key == 27:                                    #Esc key to exit the camera
                  cv2.destroyWindow("Hit 'esc' to leave image, JARVIS will not continue until then")
                  break
  else:
      cv2.imwrite("USER_TEXT.png", image)
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
  mixer.music.load("C:\\Users\\coleh\\OneDrive\\Documents\\GitHub\\J.A.R.V.I.S\\beep-24.mp3")
  mixer.music.play()
  cv2.imwrite("mic.png", cv2.imread("C:\\Users\\coleh\\OneDrive\\Documents\\GitHub\\J.A.R.V.I.S\\GUI_images\\mic.png"))
  if not loop:
    try:
      result = mic.listen(timeout = 10)
      result = result.lower()
      mixer.music.play()
      cv2.imwrite("mic.png", cv2.imread('C:\\Users\\coleh\\OneDrive\\Documents\\GitHub\\J.A.R.V.I.S\\GUI_images\\background.png'))
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

  mixer.music.load('C:\\Users\\coleh\\OneDrive\\Coding\\Python folder\\J.A.R.V.I.S\\mute.mp3')
  mixer.music.play()
  if pause == False:
    Spot.play_song()

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
  google_Crawler = GoogleImageCrawler(storage = ({"root_dir": "C:\\Users\\coleh\\OneDrive\\Documents\\GitHub\\J.A.R.V.I.S\\images"}))
  google_Crawler.crawl(keyword = query, max_num = 1)

def search_google_text(query):
  # Replace with your actual API key
  api_key = '4e26f961f6a48965866c3845c22854152866c99e35b85046ddc7bc1bfd1483a0'

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
    snippet_string = ""
    for idx, result in enumerate(results['organic_results'], start=1):
      snippet = result.get('snippet', 'No snippet available')
      snippet_string += f"Snippet {idx}: {snippet}\n"
      #print(snippet_string)
    return snippet_string
  else:
    print('Error:', response.status_code)

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
  api_key = "REDACTED_OPENAI_API_KEY"

  # Function to encode the image
  def encode_image(image_path):
    with open(image_path, "rb") as image_file:
      return base64.b64encode(image_file.read()).decode('utf-8')

  # Path to your image
  image_path = "C:\\Users\\coleh\\OneDrive\\Documents\\GitHub\\J.A.R.V.I.S\\Vision.jpg"

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
    "max_tokens": 150
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
          "max_tokens": 150
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
  file = open(f"C:\\Users\\coleh\\OneDrive\\Documents\\Notes\\J.A.R.V.I.S. log files\\{filename}.txt", "w")
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

client = openai.OpenAI(api_key="REDACTED_OPENAI_API_KEY")
mixer.init()

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
    #result = input("Type now: ")
    send_to_GUI(False, result, False)

    print("\nCole: " + result)
    result = result + " " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if len(result.split(" ")) > 30:
      print(f"\nJ.A.R.V.I.S: Understood, give me a few seconds to process.")
      Speak("Understood, give me a few seconds to process.")
    jarvis_response = send_to_llama(result)
    print(f"\nJ.A.R.V.I.S: {jarvis_response}")
    #speech = jarvis_response.split("#")[0]
    Speak(jarvis_response)
    
    if len(jarvis_response.split('#')) > 1:
      command = jarvis_response.split('#')[1]
      executable_functions(command)

if __name__ == '__main__':
  threading.Thread(target=mainer).start()
  threading.Thread(target=main).start()
  #main()