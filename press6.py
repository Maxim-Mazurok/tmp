import time
import random
import pydirectinput

pydirectinput.FAILSAFE = True

while True:
    pydirectinput.press("6")
    delay = random.uniform(25, 27)
    time.sleep(delay)
