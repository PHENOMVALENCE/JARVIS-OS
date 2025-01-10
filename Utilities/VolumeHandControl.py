import cv2
import time
import numpy as np
from cvzone.HandTrackingModule import HandDetector
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
try:
    import constants
except:
    from . import constants

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


#############################
wCam, hCam = 640, 480
#############################

cap = cv2.VideoCapture(0)
cap.set(3, wCam)
cap.set(4, hCam)
previousTime = 0

detector = HandDetector(staticMode = False, 
                        maxHands = 2, 
                        modelComplexity= 1, 
                        detectionCon= .95, 
                        minTrackCon= 0.6
                        )

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

def mainer():
    while True:
        success, img = cap.read()
        
        hands, img = detector.findHands(img, draw = True)
        
        if hands:
            hand1 = hands[0]
            lmlist1 = hand1["lmList"] # (x, y, z) list of 21 landmarks for the first hand
            bbox1 = hand1["bbox"]
            center = hand1["center"]
            handType1 = hand1["type"]
            volume_control(img, hand1, lmlist1, volume)
            
                    
        if len(hands) == 2:
            hand2 = hands[1]
            lmlist2 = hand2["lmList"] # (x, y, z) list of 21 landmarks for the first hand
            bbox2 = hand2["bbox"]
            center2 = hand2["center"]
            handType2 = hand2["type"]
            
            volume_control(img, hand2, lmlist2, volume)
            

        # ######-FPS CALCULATOR-#######
        # currentTime = time.time()
        # fps = 1 / (currentTime - previousTime)
        # previousTime = currentTime
        # cv2.putText(img, f'FPS: {int(fps)}', (40, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 3)
        # #############################
        
        
        #cv2.imshow("camera", img)
        cv2.imwrite(constants.vision_image, img)
        key = cv2.waitKey(10)                            #Delays program 10 milliseconds for improved efficiency
        if key == 27:                                    #Esc key to exit the camera
            break

if __name__ == '__main__':
    mainer()