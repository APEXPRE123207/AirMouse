from pynput.mouse import Controller
import time
mouse = Controller()

y=500
for i in range(0,1500):
    mouse.position = (i,y)
    time.sleep(0.01)