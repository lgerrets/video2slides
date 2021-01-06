
# img_viewer.py

import PySimpleGUI as sg
# import cv2
from PIL import Image
import base64
import io

import os.path
import warnings
import time
from datetime import datetime
import traceback
import shutil

sg.theme('Dark Blue 3')

default_threshold = 10000
default_skipframe = 50

EXTENSIONS = ["mp4"]
OUTPUT_EXTENTION = ".png"

def load_image(path):
	# image = cv2.imread(path)
	# image = cv2.resize(image, (192, 108), interpolation=cv2.INTER_LINEAR)
	# image = base64.b64encode(image)

	im_pil = Image.open(path)
	im_pil = im_pil.resize((192,108), resample=Image.BICUBIC)

	with io.BytesIO() as output:
		im_pil.save(output, format="PNG")
		data = output.getvalue()

	image = base64.b64encode(data)
	return image

def place(elem):
	'''
	Places element provided into a Column element so that its placement in the layout is retained.
	:param elem: the element to put into the layout
	:return: A column element containing the provided element
	'''
	return sg.Column([[elem]], pad=(0,0))

def log_error(e, do_raise):
	tb = traceback.format_exc()
	endl = "\r\n"
	with open("logs.txt", "a+") as f:
		f.write(str(datetime.fromtimestamp(time.time())) + endl)
		f.write(str(tb) + endl)
		f.write(str(e) + endl)
		f.write(endl)
	if do_raise:
		raise RuntimeError(str(e))
	else:
		warnings.warn(str(e), RuntimeWarning)

class GUI:

	def __init__(self):
		# if true, the processing will be slightly faster, but the user won't see the progress bar
		self.freeze_while_running = True

		self.threshold = default_threshold
		self.skipframe = default_skipframe
		self.valid_skipframe = False
		self.valid_threshold = False
		self.valid_outdir = False
		self.valid = False

		converter = None
		self.running = False
		self.folder_in = None
		self.folder_out = ""
		self.files_in = None
		self.outfnames = []

		# First the window layout in 2 columns
		file_list_column = [
			# required inputs
			[sg.Text("Select an input folder")],
			[
				sg.In(size=(40, 1), enable_events=True, key="-FOLDER IN-"),
				sg.FolderBrowse(),
			],
			[sg.Text("Found videos (supported extensions are: %s)"%(", ".join(EXTENSIONS))),],
			[
				sg.Listbox(
					values=[], enable_events=True, size=(40, 10), key="-FILES IN-", select_mode="LISTBOX_SELECT_MODE_SINGLE",
				)
			],
			[sg.Text("Select an output folder")],
			[
				sg.InputText(size=(40, 1), enable_events=True, key="-FOLDER OUT-"),
			],
			[place(sg.Text("This folder already exists!", size=(40,1), key="-FOLDER OUT WARNING-", text_color="red", visible=False))],
			# advanced mode inputs
			[place(sg.Text("Look every X frames (increase to speed up, but note that slides that are shown for a too short period of time will be missed)", key="-SKIPFRAME TITLE-", size=(50,3), visible=False)),],
			[place(sg.InputText("", key="-SKIPFRAME-", size=(8,1), enable_events=True, visible=False)),],
			[place(sg.Text("Please enter a number > 0 (default: %s)"%default_skipframe, size=(40,1), key="-SKIPFRAME WARNING-", text_color="red", visible=False))],
			[place(sg.Text("Threshold (aim for a high gap between 'largest rejected' and 'smallest accepted'; decrease this if some slides are missing)", key="-THRESHOLD TITLE-", size=(50,3), visible=False)),],
			[place(sg.InputText("", key="-THRESHOLD-", size=(8,1), enable_events=True, visible=False)),],
			[place(sg.Text("Please enter a number > 0 (default: %s)"%default_threshold, size=(50,1), key="-THRESHOLD WARNING-", text_color="red", visible=False))],
			# process
			[
				sg.Button("Convert", key="-PROCESS-"),
				place(sg.ProgressBar(max_value=100, orientation='h', size=(20, 20), key='-PROGRESS-', visible=False)),
			],
			[sg.Text("", size=(50,1), text_color="red", key="-SUBMIT WARNING-")],
		]

		# For now will only show the name of the file that was chosen
		image_viewer_column = [
			[sg.Text("Found slides")],
			[sg.Listbox(
					values=[], enable_events=True, size=(40, 10), key="-FILES OUT-", select_mode="LISTBOX_SELECT_MODE_SINGLE",
				)
			],
			[sg.Text("Selected slide")],
			[sg.Image(key="-IMAGE-", size=(192,108))],
			[sg.Button("Delete this slide", key="-DELETE-")],
			[
				place(sg.Text("Analysis details:", key="-METADATA OUT TITLE-")),
				place(sg.Text("", size=(30,9), key="-METADATA OUT-")),
			],
		]

		self.advanced_keys = [
			"-METADATA OUT-", "-METADATA OUT TITLE-",
			"-SKIPFRAME TITLE-", "-SKIPFRAME-", "-SKIPFRAME WARNING-",
			"-THRESHOLD TITLE-", "-THRESHOLD-", "-THRESHOLD WARNING-",
		]

		# will be disabled while the app is running (ie processing)
		self.input_keys = [
			"-FOLDER IN-", "-FILES IN-", "-FOLDER OUT-", "-PROCESS-", "-SKIPFRAME-", "-THRESHOLD-",
			"-DELETE-",
		]

		# ----- Full layout -----

		layout = [
			[
				sg.Column(file_list_column),
				sg.VSeperator(),
				sg.Column(image_viewer_column),
			],
			[sg.Checkbox("Advanced mode", key="-ADVANCED-", enable_events=True)],
		]

		self.window = sg.Window("Video to slides", layout)

		initialize = True

		# Run the Event Loop
		while True:
			if converter is not None and converter.running:
				try:
					if self.freeze_while_running:
						while self.running:
							self.running, metadata = converter.step()
					else:
						self.running, metadata = converter.step()
				except Exception as e:
					log_error(e, True)
				if self.running:
					self.window["-PROGRESS-"].update(current_count=int(metadata["progress"]*100))
				else:
					self.set_input_stuff(False)
					text = ""
					for _ in metadata:
						text += str(_) + ": " + str(metadata[_]) + "\n"
					self.window["-METADATA OUT-"].update(text)
					self.scan_folder_out()

			event, values = self.window.read(1)
			if initialize:
				self.set_advanced_stuff(False)
				initialize = False

			if event == "Exit" or event == sg.WIN_CLOSED:
				break
			# Folder name was filled in, make a list of files in the folder

			if event == "-FOLDER IN-":
				self.folder_in = values["-FOLDER IN-"]
				self.folder_out = os.path.join(self.folder_in, "output")
				self.window["-FOLDER OUT-"].update(self.folder_out)
			elif event == "-FOLDER OUT-":
				self.folder_out = values["-FOLDER OUT-"]
			elif event == "-PROCESS-":
				if not self.folder_in:
					self.window["-SUBMIT WARNING-"].update("Please select an input folder")
				elif not values["-FILES IN-"]:
					self.window["-SUBMIT WARNING-"].update("Please select a video from the list")
				elif not values["-FOLDER OUT-"]:
					self.window["-SUBMIT WARNING-"].update("Please select an output folder")
				elif not self.valid:
					pass
				else:
					from video2slides import ConvertVideo
					self.window["-SUBMIT WARNING-"].update("")
					self.window["-PROGRESS-"].update(visible=True, current_count=0)
					file = os.path.join(self.folder_in, values["-FILES IN-"][0])
					converter = ConvertVideo(file, self.folder_out, seuil=self.threshold, skipframes=self.skipframe, autorun=False)
					self.set_input_stuff(True)
					self.running = True
			elif event == "-FILES OUT-":
				f = os.path.join(self.folder_out, values["-FILES OUT-"][0])
				try:
					self.window["-IMAGE-"].update(data=load_image(f))
				except Exception as e:
					log_error(e, False)
			elif event == "-SKIPFRAME-":
				self.valid_skipframe = False
				if values["-SKIPFRAME-"].isnumeric():
					self.skipframe = int(values["-SKIPFRAME-"])
					if self.skipframe > 0:
						self.valid_skipframe = True
				self.window["-SKIPFRAME WARNING-"].update(visible=not self.valid_skipframe)
			elif event == "-THRESHOLD-":
				self.valid_threshold = False
				if values["-THRESHOLD-"].isnumeric():
					self.threshold = int(values["-THRESHOLD-"])
					if self.threshold > 0:
						self.valid_threshold = True
				self.window["-THRESHOLD WARNING-"].update(visible=not self.valid_threshold)
			elif event == "-ADVANCED-":
				self.set_advanced_stuff(bool(values["-ADVANCED-"]))
			elif event == "-DELETE-":
				if len(values["-FILES OUT-"]) > 0:
					os.remove(os.path.join(self.folder_out, values["-FILES OUT-"][0]))
					self.scan_folder_out()

			if self.folder_out:
				self.scan_folder_out()

			if not self.running:
				# refresh files
				if self.folder_in:
					self.scan_folder_in()

				# can we hit 'process'?
				self.valid_outdir = not os.path.exists(self.folder_out)
				self.valid = not (converter is not None and converter.running) and \
								self.valid_skipframe and self.valid_threshold and \
								self.valid_outdir
				self.window["-PROCESS-"].update(disabled=not self.valid)
				self.window["-FOLDER OUT WARNING-"].update(visible=not self.valid_outdir)
				self.window["-DELETE-"].update(disabled=(len(values["-FILES OUT-"]) == 0))

		self.window.close()

	def set_advanced_stuff(self, visible):
		for key in self.advanced_keys:
			if "WARNING" in key:
				if not visible:
					self.window[key].update(visible=visible)
			else:
				self.window[key].update(visible=visible)	
		self.valid_skipframe = True
		self.valid_threshold = True
		if not visible:
			self.skipframe = default_skipframe
			self.threshold = default_threshold
		else:
			self.window["-SKIPFRAME-"].update(self.skipframe)
			self.window["-THRESHOLD-"].update(self.threshold)

	def set_input_stuff(self, disabled):
		for key in self.input_keys:
			self.window[key].update(disabled=disabled)
		if not disabled:
			self.window["-PROGRESS-"].update(current_count=0, visible=False)

	def scan_folder_in(self):
		try:
			# Get list of files in folder
			infile_list = os.listdir(self.folder_in)
		except:
			infile_list = []

		infnames = [
			f
			for f in infile_list
			if os.path.isfile(os.path.join(self.folder_in, f))
		]
		filtered_infnames = []
		for ext in EXTENSIONS:
			filtered_infnames += [f for f in infnames if f.lower().endswith(".%s"%ext)]
		filtered_infnames = sorted(filtered_infnames)
		if self.files_in != filtered_infnames:
			self.files_in = filtered_infnames
			self.window["-FILES IN-"].update(self.files_in)

	def scan_folder_out(self):
		try:
			# Get list of files in folderto-slides/outp
			outfile_list = os.listdir(self.folder_out)
		except:
			outfile_list = []
		outfnames = [
			f
			for f in outfile_list
			if os.path.isfile(os.path.join(self.folder_out, f)) and f.lower().endswith(OUTPUT_EXTENTION)
		]
		outfnames = sorted(outfnames)
		if self.outfnames != outfnames:
			self.outfnames = outfnames
			self.window["-FILES OUT-"].update(self.outfnames)
			self.window["-IMAGE-"].update(data=None)

gui = GUI()
