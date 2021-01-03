
# img_viewer.py

import PySimpleGUI as sg
# import cv2
from PIL import Image
import base64
import io

import os.path
import warnings

# todo: JAUGE, print elapsed time, delete image, parameter seuil, param skipframe, graph of distances?

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
	[sg.Button("Submit", key="-PROCESS-")],
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
		sg.Text("Analysis details:"),
		sg.Text("", size=(30,7), key="-METADATA OUT-"),
	],
]

# ----- Full layout -----

layout = [
	[
		sg.Column(file_list_column),
		sg.VSeperator(),
		sg.Column(image_viewer_column),
	]
]

window = sg.Window("Image Viewer", layout)

# Run the Event Loop
while True:
	event, values = window.read()
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
		window["-FILES IN-"].update(filtered_infnames)
		window["-FOLDER OUT-"].update(os.path.join(folder, "output"))
	elif event == "-PROCESS-":
		if not values["-FOLDER IN-"]:
			window["-SUBMIT WARNING-"].update("Please select an input folder")
		elif not values["-FILES IN-"]:
			window["-SUBMIT WARNING-"].update("Please select a video from the list")
		elif not values["-FOLDER OUT-"]:
			window["-SUBMIT WARNING-"].update("Please select an output folder")
		else:
			from video2slides import convert_video
			file = os.path.join(values["-FOLDER IN-"], values["-FILES IN-"][0])
			outdir = values["-FOLDER OUT-"]
			metadata = convert_video(file, outdir)
			text = ""
			for _ in metadata:
				text += str(_) + ": " + str(metadata[_]) + "\n"
			window["-METADATA OUT-"].update(text)
			try:
				# Get list of files in folder
				outfile_list = os.listdir(outdir)
			except:
				outfile_list = []
			outfnames = [
				f
				for f in outfile_list
				if os.path.isfile(os.path.join(outdir, f)) and f.lower().endswith(OUTPUT_EXTENTION)
			]
			outfnames = sorted(outfnames)
			window["-FILES OUT-"].update(outfnames)
			f = os.path.join(outdir, outfnames[0])
			try:
				window["-IMAGE-"].update(data=load_image(f))
			except RuntimeError as e:
				warnings.warn(str(e), UserWarning)
	elif event == "-FILES OUT-":
			f = os.path.join(outdir, values["-FILES OUT-"][0])
			try:
				window["-IMAGE-"].update(data=load_image(f))
			except RuntimeError as e:
				warnings.warn(str(e), UserWarning)

window.close()
