import os
os.environ['PYUSB_DEBUG'] = 'debug'
import usb.core
usb.core.find()