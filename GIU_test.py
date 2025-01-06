import cv2
import numpy as np

# Add text
text = "Excellent choice, Sir! Here's a more detailed breakdown of the 'Asymmetrical Balance' layout: *  **Dominant Image:** Position the 5x7 inch photo slightly off-center to the left side. This creates a visual anchor and focal point. \n \n\n*   **Overlapping Corner:** Place the 3.5x5 inch image overlapping the lower right corner of the larger photo. This adds depth and visual interest. *   **Vertical Placement:** Position the 4x6 inch picture directly below the 5x7 \n\n\ninch one, leaving a small gap between them for breathing room. *   **Complementary Pieces:**  Fill the remaining space with the two smaller pictures. You could place one to the right of the 3.5x5 image and the other above or below the 4x6 inch picture, dependi\n\n\nng on your preference. This creates a dynamic composition. Does this more detailed layout help visualize the arrangement, Sir?  mute"
jarvis_text = True
new_window = True

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
                break
else:
    cv2.imwrite("USER_TEXT.png", image)
    if new_window:
        while True:
            cv2.imshow("Hit 'esc' to leave image, JARVIS will not continue until then", image)
            key = cv2.waitKey(10)
            if key == 27:                                    #Esc key to exit the camera
                break