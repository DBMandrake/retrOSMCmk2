#!/usr/bin/python

import os, signal, subprocess, sys, time, xbmc, xbmcgui
from os import path
import xml.etree.ElementTree as ET
from xml.dom import minidom as MD
from shutil import copyfile
from subprocess import check_output



#
# FUNCTION DEFINITIONS
#

def cec_client(mode):
  global cecc_proc
  global cecc_iter

  if mode == "START":
    cecc_proc = subprocess.Popen(CLIENT, stdout=subprocess.PIPE, universal_newlines=True)
    cecc_iter = iter(cecc_proc.stdout.readline, "")
  elif mode == "STOP":
    cecc_proc.terminate()
  elif mode == "CODE":
    while True:
      line = next(cecc_iter)
      if all(["TRAFFIC" in line, ">>" in line]): # looking for key code
        # extract inbound CEC frame
        keycode = line.split(">>")[-1].strip()
        # ignore key release code that spams the output
        if keycode == "01:45":
          continue
        else:
          return keycode
  elif mode == "DESC":
    while True:
      line = next(cecc_iter)
      if "TRAFFIC" in line:
        return "No description available"
      elif all(["DEBUG" in line, "key pressed:" in line]):
        return "%s)" % (line.split("key pressed:")[-1].strip().split(")")[0])


# blocks Kodi response to main remote navigation buttons
def remote_jammer(toggle):
  if toggle == "START": # disable common navigation buttons on the remote, to avoid GUI conflict during the mapping
    # hide an existing user keymap
    if os.path.exists(REMOTE):
      copyfile(REMOTE, HIDDEN)
    # replace with a preset NOOP config to disable to buttons
    copyfile(HOBBLE, REMOTE)
    xbmc.executebuiltin("Action(reloadkeymaps)")

  elif toggle == "STOP": # re-enable the back button
    if os.path.exists(HIDDEN):
      copyfile(HIDDEN, REMOTE)
      os.remove(HIDDEN)
    else:
      os.remove(REMOTE)

    xbmc.executebuiltin("Action(reloadkeymaps)")
  return


# reads a single line from a FIFO
def readFIFO():
  global FIFO_PATH
  global MODE

  while True:
    with open(FIFO_PATH) as fifo:
      for line in fifo:
        line = line.rstrip()
        if line == "NOPADS":
          dialog.ok("Program Exit Buttons", "No gamepads detected!")
          exit()
        elif line == "TIMEOUT":
          if MODE == "PROGRAM":
            dialog.ok("Program Exit Buttons", "No button pressed!")
          else:
            dialog.ok("Test Exit Buttons", "Did not detect exit combination!")
          exit()
        elif ':' in line:
          if line.count(':') == 1:
            return line
        elif line == "EXIT":
          return line



#
# EXECUTION STARTS HERE
#

# init constant paths
CLIENT="/usr/osmc/bin/cec-client"
EVHELPER="/home/osmc/RetroPie/scripts/evdev-exit.sh"
DATA="/home/osmc/.kodi/userdata/addon_data/script.launch.retropie/data.xml"
HIDDEN="/home/osmc/.kodi/userdata/keymaps/remote.xml.hidden"
HOBBLE="/home/osmc/.kodi/addons/script.launch.retropie/resources/data/hobble.xml"
REMOTE="/home/osmc/.kodi/userdata/keymaps/remote.xml"
SETTINGS="/home/osmc/.kodi/userdata/addon_data/script.launch.retropie/settings.xml"
FIFO_PATH="/tmp/evdev-exit.fifo"

# init dialog handle for all popups
dialog = xbmcgui.Dialog()
cecc_proc = ""
cecc_iter = ""

# check an arg was actually passed to the script so it's all addon settings-page related
if len(sys.argv) > 1:
  MODE = sys.argv[1]
  INPUTTYPE = sys.argv[2]

  # load data file/tree
  try: # read in the settings file
    settings_file = ET.parse(DATA)
    settings = settings_file.getroot()
    keycode = settings.find("keycode").text
    keydesc = settings.find("keydesc").text
    gamepad = settings.find("gamepad").text
    hotbtncode = settings.find("hotbtncode").text
    exitbtncode = settings.find("exitbtncode").text
  except (IOError, AttributeError): # no file or corrupt
    xbmc.log("retrOSMCmk2 Launcher: \"%s\" missing or corrupt on this run" % (DATA), level=xbmc.LOGNOTICE)
    # create temporary default tree
    keycode = "No keycode set yet!"
    keydesc = "Use the \"Program exit key\" option above."
    gamepad = "Setup still required:"
    hotbtncode = "No button code set yet!"
    exitbtncode = "Use the \"Program exit key\" option above."
    settings = ET.Element("settings")
    ET.SubElement(settings, "keycode").text = keycode
    ET.SubElement(settings, "keydesc").text = keydesc
    ET.SubElement(settings, "gamepad").text = gamepad
    ET.SubElement(settings, "hotbtncode").text = hotbtncode
    ET.SubElement(settings, "exitbtncode").text = exitbtncode


# default action = launch ES +/- fast switch +/- CEC exit button +/- disable Kodi exit signals
else:
  # load addon settings
  cec_exit = "false"
  evdev_exit = "false"
  kodi_signals = "false"
  fast_switching = "false"
  fix_4k = "false"

  try:
    settings_file = ET.parse(SETTINGS)
    settings = settings_file.getroot()
    for setting in settings:
      if setting.get("id") == "cec-exit":
        cec_exit = setting.text
      elif setting.get("id") == "evdev-exit":
        evdev_exit = setting.text
      elif setting.get("id") == "kodi-signals":
        kodi_signals = setting.text
      elif setting.get("id") == "fast-switching":
        fast_switching = setting.text
      elif setting.get("id") == "4k-fix":
        fix_4k = setting.text
  except (IOError, AttributeError): # no file or corrupt so leave blank
    xbmc.log("retrOSMCmk2 Launcher: \"%s\" missing or corrupt on this run" % (SETTINGS), level=xbmc.LOGNOTICE)

  # give the scared people something to look at
  if (kodi_signals == "false" and fast_switching == "false"):
    xbmc.executebuiltin("ActivateWindow(busydialognocancel)")

  # start the CEC exit button watchdog?
  if cec_exit == "true":
    os.system('systemctl start cec-exit')

  # start the evdev exit button watchdog?
  if evdev_exit == "true":
    os.system('systemctl start evdev-exit')

  # launch Emulationstation +/- fast switching which is needed to block CEC shutdown signals too
  if (kodi_signals == "true" or fast_switching == "true"):
    os.system('echo "es fast %s" >/tmp/app-switcher.fifo' % (fix_4k))
  else:
    os.system('echo "es slow %s" >/tmp/app-switcher.fifo' % (fix_4k))

  exit()


# otherwise parse arguments for required mode in settings page
if INPUTTYPE == "CEC":
  if MODE == "PROGRAM":
    dialog.ok("Program Exit Key", "1. Press OK\n\n2. Repeatedly press the button on your TV remote that you want to exit RetroPie.")
    remote_jammer("START")
    cec_client("START")
    dialog.notification("CEC-client", "listening...", xbmcgui.NOTIFICATION_INFO, 1000)

    # collect 2 presses of the same key and the description that follows if it exists
    keys = [keycode]
    while not keys.count(keys[-1]) == 2:
      keys.append(cec_client("CODE"))

    keycode = keys[-1]
    keydesc = cec_client("DESC")

    # write out addon data.xml
    settings.find("keycode").text = keycode
    settings.find("keydesc").text = keydesc
    xmlstr = ET.tostring(settings).decode()
    newxml = MD.parseString(xmlstr)
    with open(DATA,"w+") as outfile:
        outfile.write(newxml.toprettyxml(indent="",newl=""))

    cec_client("STOP")
    remote_jammer("STOP")
    dialog.ok("CEC-client", "Keycode = %s\nDescription = %s" % (keycode, keydesc))


  elif MODE == "SETTING":
    dialog.ok("Current CEC Keycode", "Code = %s\nDescription = %s" % (keycode, keydesc))

  elif MODE == "TEST":
    if keycode == "No keycode set yet!":
      dialog.ok("Test Exit Key", "Code = %s\nDescription = %s" % (keycode, keydesc))
    else:
      dialog.ok("Test Exit Key", "1. Press OK\n\n2. Repeatedly press the button on your TV remote that you have set to exit RetroPie.")
      remote_jammer("START")
      cec_client("START")
      dialog.notification("CEC-client", "listening...", xbmcgui.NOTIFICATION_INFO, 1000)

      attempts = 3
      for press in range(0, attempts):
        if cec_client("CODE") == keycode:
          msg = "Correct keycode detected!"
          break
        elif press < (attempts - 1):
          continue
        else:
          msg = "The programmed keycode was not detected..."

      cec_client("STOP")
      remote_jammer("STOP")
      dialog.ok("CEC-client", msg)

  else:
    xbmc.log("ERROR!\n\"%s\" is a bad argument for %s" % (MODE, sys.argv[0]), level=xbmc.LOGNOTICE)

elif INPUTTYPE == "EVDEV":
  # helper will automatically grab the device when testing to avoid a clash with Kodi - no jammer needed here

  # ensure FIFO is in place for evdev-helper comms
  if not path.exists(FIFO_PATH):
    os.mkfifo(FIFO_PATH)

  if MODE == "PROGRAM":
    dialog.textviewer("Program Exit Buttons", "These will work like RetroPie.\n\nYou configure a hotkey enable button and an exit button.  For example to exit back to EMulationstation most people are configured to hold down \"select\" and press \"start\".\n\nThe enable button could be the same as RetroPie, but the switch button MUST NOT ALREADY BE ASSIGNED to anything else in RetroPie e.g. exit, reset, save/load gamestate.\n\nProgramming instructions\n1. Press OK\n2. When requested press the hotkey enable button on the gamepad.\n3. Then when requested press the gamepad button you will use for the switching function.")

    # collect controller name and hotkey enable button
    subprocess.Popen([EVHELPER, "SCANMULTI"])
    dialog.notification("Program Exit Buttons", "Press hotkey enable button...", xbmcgui.NOTIFICATION_INFO, 3000)
    msg = readFIFO()
    # validate output = gamepad-id:button-id
    gamepad = msg.split(':', 1)[0]
    hotbtncode = msg.split(':', 1)[1]
    dialog.notification("Program Exit Buttons", "Button captured!", xbmcgui.NOTIFICATION_INFO, 2000)
    time.sleep(3)

    # collect exit button for the same controller
    subprocess.Popen([EVHELPER, "SCANSINGLE", gamepad, "PARENT"])
    dialog.notification("Program Exit Buttons", "Press exit button...", xbmcgui.NOTIFICATION_INFO, 3000)
    msg = readFIFO()
    # validate output - gamepad id, button id
    if not msg.split(':', 1)[0] == gamepad:
      dialog.ok("Program Exit Buttons", "\"Exit Button\" must be on the same controller as the \"Hotkey Enable Button\"!")
      exit()
# TODO exit button cannot be the same as the hotkey enable button...
    exitbtncode = msg.split(':', 1)[1]

    # write out addon data.xml
    settings.find("gamepad").text = gamepad
    settings.find("hotbtncode").text = hotbtncode
    settings.find("exitbtncode").text = exitbtncode
    xmlstr = ET.tostring(settings).decode()
    newxml = MD.parseString(xmlstr)
    with open(DATA,"w+") as outfile:
        outfile.write(newxml.toprettyxml(indent="",newl=""))

    dialog.ok("New EVDEV Exit Settings", "Gamepad:\n%s\nHotkey enable button = %s\nExitkey enable button = %s" % (gamepad, hotbtncode, exitbtncode))


  elif MODE == "SETTING":
    dialog.ok("Current EVDEV Exit Settings", "Gamepad:\n%s\nHotkey enable button = %s\nExitkey enable button = %s" % (gamepad, hotbtncode, exitbtncode))


  elif MODE == "TEST":
    if hotbtncode == "No button code set yet!":
      dialog.ok("Test Exit Buttons", "%s" % (hotbtncode))
    else:
      dialog.ok("Test Exit Buttons", "1. Press OK\n\n2. On the gamepad hold the hotkey enable button, then press the exit button.")

      # test exit button combination
      subprocess.Popen([EVHELPER, "CATCHCOMBO", "TEST", gamepad, hotbtncode, exitbtncode])
      dialog.notification("Testing Exit Buttons", "Press exit combination...", xbmcgui.NOTIFICATION_INFO, 3000)
      msg = readFIFO()
      if msg == "EXIT":
        dialog.ok("Test Exit Buttons", "Exit combination detected correctly!")
      elif msg == "TIMEOUT":
        dialog.ok("Test Exit Buttons", "Exit combination was not detected!")

  else:
    xbmc.log("ERROR!\n\"%s\" is a bad argument for %s" % (MODE, sys.argv[0]), level=xbmc.LOGNOTICE)

else:
  xbmc.log("ERROR!\n\"%s\" is a bad argument for %s" % (INPUTTYPE, sys.argv[0]), level=xbmc.LOGNOTICE)
