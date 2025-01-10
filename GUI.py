import time #download current time for sleep function
import pygame #Library for running graphical interface
import datetime #Library for getting current date and time
import sys
from pygame.locals import QUIT
import cv2
from Utilities import constants

######################################## - GUI -###########################
#Initialises the display-------------------------------------------------------
pygame.display.init() # Initiates the display pygame
screen = pygame.display.set_mode((1200,800), pygame.RESIZABLE) # Sets the size of the display

background = pygame.image.load(constants.background_png)
background = pygame.transform.scale(background, (1200, 800))
background.fill((0, 0, 0))  # Assume the background color is black

hacker = pygame.image.load(constants.hacker_image)
hacker = pygame.transform.scale(hacker, (600, 400))

pygame.font.init()
smallfont = pygame.font.Font(constants.font_file, 15)
bigfont = pygame.font.Font(constants.font_file, 22)

system = bigfont.render("SYSTEM:", True, (255, 255, 255))
speakers = bigfont.render("SPEAKERS:", True, (255, 255, 255))
memory = bigfont.render("MEMORY:", True, (255, 255, 255))
camera = bigfont.render("CAMERA:", True, (255, 255, 255))
processors = bigfont.render("PROCESSORS:", True, (255, 255, 255))
online = bigfont.render("ONLINE", True, (0, 255, 0))
offline = bigfont.render("OFFLINE", True, (255, 0, 0))
jarvis = bigfont.render("JARVIS:", True, (255, 255, 255))
user = bigfont.render("USER:", True, (255, 255, 255))

pygame.event.set_blocked(pygame.MOUSEBUTTONDOWN)
pygame.event.set_blocked(pygame.MOUSEBUTTONUP)

initial_vision_img = cv2.imread(constants.loading_image)
initial_JARVIS_img = cv2.imread(constants.background_png)
initial_user_img = cv2.imread(constants.background_png)
initial_mic_img = cv2.imread(constants.background_png)

cv2.imwrite(constants.GUI_mic_png, initial_mic_img)
cv2.imwrite(constants.vision_image, initial_vision_img)
cv2.imwrite(constants.jarvis_text_image, initial_JARVIS_img)
cv2.imwrite(constants.user_text_image, initial_user_img)

###########################################################################

def initialization():
  
  background = pygame.Surface(processors.get_rect().size)
  screen.blit(hacker, (700, -150))
  
  for i in range(2):
    screen.blit(system, (10, 10))
    pygame.display.flip()
    time.sleep(0.5)
    
    screen.blit(background, (10, 10))
    pygame.display.flip()
    time.sleep(0.5)
  
  screen.blit(system, (10, 10))
  pygame.display.flip()
  time.sleep(0.5)
  
  screen.blit(online, (200, 10))
  pygame.display.flip()
  time.sleep(0.2)
  
  ######
  
  screen.blit(speakers, (10, 40))
  pygame.display.flip()
  time.sleep(0.2)
  
  screen.blit(online, (200, 40))
  pygame.display.flip()
  time.sleep(0.2)
  
  #####
  
  screen.blit(memory, (10, 70))
  pygame.display.flip()
  time.sleep(0.2)
  
  screen.blit(online, (200, 70))
  pygame.display.flip()
  time.sleep(0.2)
  
  ######
  
  screen.blit(processors, (10, 100))
  pygame.display.flip()
  time.sleep(0.2)
  
  screen.blit(online, (200, 100))
  pygame.display.flip()
  time.sleep(0.2)
  
  ######
  
  screen.blit(camera, (10, 130))
  pygame.display.flip()
  time.sleep(0.2)
  screen.blit(online, (200, 130))
  
  ininitializing = bigfont.render("INITIALIZING...", True, (255, 255, 255))
  screen.blit(ininitializing, (10, 160))
  pygame.display.flip()
  time.sleep(2)

def face():
  initialization()
  running = True
  clock = pygame.time.Clock()
  while running:
    for event in pygame.event.get():
      if event.type == QUIT:
        pygame.quit()
        sys.exit()
      elif event.type == pygame.MOUSEBUTTONDOWN:
          None
      elif event.type == pygame.MOUSEBUTTONUP:
          None
      elif event.type == pygame.MOUSEMOTION:
          None
      elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
          running = False

    for j in range(1, 64):
      screen.blit(background, (0, 0), (0, 0, 1200, 800))
    
      jarvis_gif = pygame.image.load(constants.GUI_image_dir + f"\\{j}.gif")
      try:
        vision_image = pygame.image.load(constants.vision_image)
        user_text = pygame.image.load(constants.user_text_image)
        jarvis_text = pygame.image.load(constants.jarvis_text_image)
        mic_image = pygame.image.load(constants.GUI_mic_png)
        vision_image = pygame.transform.scale(vision_image, (320, 240))
        mic_image = pygame.transform.scale(mic_image, (66.666, 100))
      except:
        pass
      screen.blit(jarvis_gif, (260, 0), (0, 0, 1200, 800))
      screen.blit(hacker, (700, -150))

      screen.blit(system, (10, 10))
      screen.blit(speakers, (10, 40))
      screen.blit(memory, (10, 70))
      screen.blit(processors, (10, 100))
      screen.blit(camera, (10, 130))
      
      screen.blit(online, (200, 10))
      screen.blit(online, (200, 40))
      screen.blit(online, (200, 70))
      screen.blit(online, (200, 100))
      screen.blit(online, (200, 130))
      
      screen.blit(user, (10, 490))
      screen.blit(jarvis, (10, 650))
      screen.blit(mic_image, (560, 190))
      
      current_time = datetime.datetime.now().ctime()
      current_time = bigfont.render(current_time, True, (255, 255, 255))
      screen.blit(current_time, (830, 125))
      try:
        screen.blit(user_text, (110, 480))
        screen.blit(jarvis_text, (130, 640))
        screen.blit(vision_image, (10, 175))
        screen.blit
      except:
        pass
      pygame.display.flip()
      clock.tick(15)


if __name__ == '__main__':
  face()