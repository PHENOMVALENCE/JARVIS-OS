import cv2
import time
import numpy as np
from cvzone.HandTrackingModule import HandDetector
from pynput.mouse import Controller, Button
import wx
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

def volume_control(img, hand1, lmlist, volume):
    fingerList = detector.fingersUp(hand1)
    if fingerList[0] + fingerList[1] == 2 and fingerList[2] + fingerList[3] + fingerList[4] == 0:
        
        length, info, img = detector.findDistance(lmlist[4][0:2], lmlist[8][0:2], img, (255, 0, 0), 10)
        #Hand range 30 - 175
        #volume range -65 - 0
        vol =  np.interp(length, [65, 175], [-25, maxVolume])
        volBar = np.interp(length, [65, 175], [360, 80])
        volPer = np.interp(length, [65, 175], [0, 100])
        
        cv2.rectangle(img, (40, 80), (150, 360), (255, 0, 0), 5)
        cv2.rectangle(img, (40, int(volBar)), (150, 360), (255, 0, 0), cv2.FILLED)
        cv2.putText(img, f'{int(volPer)}%', (40, 400), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 3)
        
        if length < 65:
            x1, y1 = lmlist[4][0:2]
            x2, y2 = lmlist[8][0:2]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.circle(img, (cx, cy), 10, (0, 255, 0) , cv2.FILLED)
            volume.SetMasterVolumeLevel(minVolume, None)
            #print(int(length), minVolume)
        
        elif length > 175:
            length, info, img = detector.findDistance(lmlist[4][0:2], lmlist[8][0:2], img, (0, 255, 0), 10)
            volume.SetMasterVolumeLevel(maxVolume, None)
            #print(int(length), maxVolume)
            
        else:
            volume.SetMasterVolumeLevel(vol, None)
            #print(int(length), vol)

devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(
    IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume = interface.QueryInterface(IAudioEndpointVolume)

#volume.GetMute()
currentVolume = volume.GetMasterVolumeLevel()
volumeRange = volume.GetVolumeRange()
minVolume = volumeRange[0]
maxVolume = volumeRange[1]
#print(minVolume)

detector = HandDetector(staticMode = False, 
                    maxHands = 1, 
                    modelComplexity= 1, 
                    detectionCon= 0.8, 
                    minTrackCon= 0.8
                    )

def mainer():
    #############################
    wCam, hCam = 640, 480
    frameR = 100
    smoothening = 3.5
    #############################

    cap = cv2.VideoCapture(0)
    cap.set(3, wCam)
    cap.set(4, hCam)
    previousTime = 0
    app = wx.App(False)
    wScr, hScr = wx.GetDisplaySize()
    mouse = Controller()
    plocX, plocY = 0, 0
    clocX, clocY = 0, 0
    first_time = True
    prevLength = 100
    
    while True:
        #1. find hand landmarks
        success, img = cap.read()
        hands, img = detector.findHands(img, draw = True)
        cv2.rectangle(img, (frameR, frameR - 100), (wCam - frameR, hCam - frameR - 100), (255, 0, 255), 2)
        #print(hands)
        if len(hands) == 1:
            hand1 = hands[0]
            lmlist = hand1["lmList"] # (x, y, z) list of 21 landmarks for the first hand
            bbox1 = hand1["bbox"]
            handType1 = hand1["type"]
            volume_control(img, hand1,lmlist, volume)
            
            x1, y1 = lmlist[8][0:2]
            x2, y2 = lmlist[12][0:2]
            cx, cy  = (x1 + x2) / 2, (y1 + y2) / 2
            fingerList = detector.fingersUp(hand1)
            x3 = np.interp(cx, (frameR, wCam - frameR), (0, wScr))
            y3 = np.interp(cy, (frameR -100, hCam - frameR -100), (0, hScr))
            clocX = plocX + (x3 - plocX) / smoothening
            clocY = plocY + (y3 - plocY) / smoothening

            if fingerList[1] + fingerList[2] == 2 and fingerList[0] + fingerList[3] + fingerList[4] == 0:
                mouse.position = (wScr - clocX, clocY)
                cv2.circle(img, (x1, y1), 15, (255, 0, 255), cv2.FILLED)
                plocX, plocY = clocX, clocY

                length, info, img = detector.findDistance((x1, y1), (x2, y2), img, (0, 0, 255), 10)

                if length < 40 and first_time == True:
                    mouse.press(Button.left)
                    first_time = False
                elif length < 40:
                    cv2.circle(img, (x1, y1), 10, (0, 255, 0) , cv2.FILLED)
                elif prevLength < 40:
                    mouse.release(Button.left)
                    first_time = True
                
                prevLength = length

            if fingerList[0] + fingerList[1] + fingerList[2] == 3 and fingerList[3] + fingerList[4] == 0:
                mouse.position = (wScr - clocX, clocY)
                cv2.circle(img, (x1, y1), 15, (255, 0, 255), cv2.FILLED)
                plocX, plocY = clocX, clocY

                length, info, img = detector.findDistance((x1, y1), (x2, y2), img, (0, 0, 255), 10)
                
                if length < 40 and first_time == True:
                    mouse.press(Button.right)
                    first_time = False
                elif length < 40:
                    cv2.circle(img, (x1, y1), 10, (0, 255, 0) , cv2.FILLED)
                elif prevLength < 40:
                    mouse.release(Button.right)
                    first_time = True
                prevLength = length

            if fingerList[1] + fingerList[2] + fingerList[3]== 3 and fingerList[0] + fingerList[4] == 0:
                if y3 > 550:
                    mouse.scroll(0, -2)
                    time.sleep(.1)

                if y3 < 200:
                    mouse.scroll(0, 2)
                    time.sleep(.05) 
                    

    
        # ######-FPS CALCULATOR-#######
        # currentTime = time.time()
        # fps = 1 / (currentTime - previousTime)
        # previousTime = currentTime
        # cv2.putText(img, f'FPS: {int(fps)}', (40, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 3)
        # #############################
        
        
        #cv2.imshow("J.A.R.V.I.S.", img)
        cv2.imwrite("Vision.jpg", img)
        key = cv2.waitKey(10)                            #Delays program 10 milliseconds for improved efficiency
        if key == 27:                                    #Esc key to exit the camera
            break

if __name__ == '__main__':
    mainer()