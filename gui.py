
# img_viewer.py

import PySimpleGUI as sg
# import cv2
from PIL import Image
import base64
import io

import os.path
import warnings

sg.theme('Dark Blue 3')

# todo: JAUGE, print elapsed time, delete image, parameter seuil, param skipframe, graph of distances?

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


class GUI:

	def __init__(self):
		self.threshold = default_threshold
		self.skipframe = default_skipframe
		self.valid_skipframe = False
		self.valid_threshold = False

		converter = None

		# First the window layout in 2 columns
		file_list_column = [
			[sg.Text("Select an input folder")],
			[
				sg.In(size=(40, 1), enable_events=True, key="-FOLDER IN-"),
				sg.FolderBrowse(),
			],
			[sg.Text("Found videos (supported extensions are: %s."%(", ".join(EXTENSIONS))),],
			[
				sg.Listbox(
					values=[], enable_events=True, size=(40, 10), key="-FILES IN-", select_mode="LISTBOX_SELECT_MODE_SINGLE",
				)
			],
			[sg.Text("Select an output folder")],
			[
				sg.In(size=(40, 1), enable_events=True, key="-FOLDER OUT-"),
				sg.FolderBrowse(),
			],
			[
				sg.Text("Look every X frames", key="-SKIPFRAME TITLE-"),
				sg.In("", key="-SKIPFRAME-", size=(8,1), enable_events=True),
				place(sg.Text("Please enter a number > 0 (default: %s)"%default_skipframe, key="-SKIPFRAME WARNING-", text_color="red", visible=False)),
			],
			[
				sg.Text("Frame threshold", key="-THRESHOLD TITLE-"),
				sg.In("", key="-THRESHOLD-", size=(8,1), enable_events=True),
				place(sg.Text("Please enter a number > 0 (default: %s)"%default_threshold, key="-THRESHOLD WARNING-", text_color="red", visible=False)),
			],
			[
				sg.Button("Submit", key="-PROCESS-"),
				place(sg.ProgressBar(max_value=100, orientation='h', size=(20, 20), key='-PROGRESS-', visible=False)),
			],
			[sg.Text("", size=(50,1), text_color="red", key="-SUBMIT WARNING-")],
		]

		# For now will only show the name of the file that was chosen
		image_viewer_column = [
			[sg.Text("Processed frames")],
			[sg.Listbox(
					values=[], enable_events=True, size=(40, 10), key="-FILES OUT-", select_mode="LISTBOX_SELECT_MODE_SINGLE",
				)
			],
			[sg.Text("Selected frame")],
			[sg.Image(key="-IMAGE-", size=(192,108))],
			[
				place(sg.Text("Analysis details:", key="-METADATA OUT TITLE-")),
				place(sg.Text("", size=(30,7), key="-METADATA OUT-")),
			],
		]

		self.advanced_keys = [
			"-METADATA OUT-", "-METADATA OUT TITLE-",
			"-SKIPFRAME TITLE-", "-SKIPFRAME-", "-SKIPFRAME WARNING-",
			"-THRESHOLD TITLE-", "-THRESHOLD-", "-THRESHOLD WARNING-",
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

		self.window = sg.Window("Image Viewer", layout)

		initialize = True

		# Run the Event Loop
		while True:
			if converter is not None and converter.running:
				running, metadata = converter.step()
				if running:
					self.window["-PROGRESS-"].update(current_count=int(metadata["progress"]*100))
				else:
					text = ""
					for _ in metadata:
						text += str(_) + ": " + str(metadata[_]) + "\n"
					self.window["-METADATA OUT-"].update(text)
					try:
						# Get list of files in folderto-slides/outp
						outfile_list = os.listdir(outdir)
					except:
						outfile_list = []
					outfnames = [
						f
						for f in outfile_list
						if os.path.isfile(os.path.join(outdir, f)) and f.lower().endswith(OUTPUT_EXTENTION)
					]
					outfnames = sorted(outfnames)
					self.window["-FILES OUT-"].update(outfnames)
					f = os.path.join(outdir, outfnames[0])
					try:
						self.window["-IMAGE-"].update(data=load_image(f))
					except RuntimeError as e:
						warnings.warn(str(e), UserWarning)

			event, values = self.window.read(1)
			if initialize:
				self.set_advanced_stuff(False)
				initialize = False

			if event == "Exit" or event == sg.WIN_CLOSED:
				break
			# Folder name was filled in, make a list of files in the folder

			if event == "-FOLDER IN-":
				folder = values["-FOLDER IN-"]
				try:
					# Get list of files in folder
					infile_list = os.listdir(folder)
				except:
					infile_list = []

				infnames = [
					f
					for f in infile_list
					if os.path.isfile(os.path.join(folder, f))
				]
				filtered_infnames = []
				for ext in EXTENSIONS:
					filtered_infnames += [f for f in infnames if f.lower().endswith(".%s"%ext)]
				filtered_infnames = sorted(filtered_infnames)
				self.window["-FILES IN-"].update(filtered_infnames)
				self.window["-FOLDER OUT-"].update(os.path.join(folder, "output"))
				self.window["-PROGRESS-"].update(visible=False, current_count=0)
			elif event == "-PROCESS-":
				valid = self.valid_skipframe and self.valid_threshold
				if not values["-FOLDER IN-"]:
					self.window["-SUBMIT WARNING-"].update("Please select an input folder")
				elif not values["-FILES IN-"]:
					self.window["-SUBMIT WARNING-"].update("Please select a video from the list")
				elif not values["-FOLDER OUT-"]:
					self.window["-SUBMIT WARNING-"].update("Please select an output folder")
				elif not valid:
					pass
				else:
					from video2slides import ConvertVideo
					self.window["-PROGRESS-"].update(visible=True, current_count=0)
					file = os.path.join(values["-FOLDER IN-"], values["-FILES IN-"][0])
					outdir = values["-FOLDER OUT-"]
					converter = ConvertVideo(file, outdir, autorun=False)
			elif event == "-FILES OUT-":
				self.window["-PROGRESS-"].update(visible=False, current_count=0)
				f = os.path.join(outdir, values["-FILES OUT-"][0])
				try:
					self.window["-IMAGE-"].update(data=load_image(f))
				except RuntimeError as e:
					warnings.warn(str(e), UserWarning)
			elif event == "-SKIPFRAME-":
				self.valid_skipframe = False
				if values["-SKIPFRAME-"].isnumeric():
					self.skipframe = int(values["-SKIPFRAME-"])
					if self.skipframe > 0:
						self.valid_skipframe = True
				self.window["-SKIPFRAME WARNING-"].update(visible=self.valid_skipframe)
			elif event == "-THRESHOLD-":
				self.valid_threshold = False
				if values["-THRESHOLD-"].isnumeric():
					self.threshold = int(values["-THRESHOLD-"])
					if self.threshold > 0:
						self.valid_threshold = True
				self.window["-THRESHOLD WARNING-"].update(visible=self.valid_threshold)
			elif event == "-ADVANCED-":
				self.set_advanced_stuff(bool(values["-ADVANCED-"]))

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

gui = GUI()