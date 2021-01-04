import os
import sys
import numpy as np
import cv2
import time
import csv
import shutil
import zipfile
import warnings

try:
	from flask import send_from_directory
	from flask_wtf import FlaskForm
	from flask_wtf.file import FileRequired, FileField
	from wtforms import (TextField, validators, SubmitField, 
						DecimalField, IntegerField)
	from wtforms.validators import ValidationError
	from werkzeug.utils import secure_filename
except ImportError as e:
	warnings.warn(str(e), RuntimeWarning)

class TimeProfiler:
	def __init__(self, verbose):
		self.timers = {}
		self.t = 0
		self.verbose = verbose

	def reset(self):
		self.t = time.perf_counter()
		self.timers = {}

	def time(self, key):
		t = time.perf_counter()
		self.timers[key] = t - self.t
		self.t = t

	def print(self):
		if self.verbose > 0:
			for _ in self.timers:
				print(_, self.timers[_])

prof = TimeProfiler(0)


def is_video_file(form, field):
	filename = field.data
	valid = '.' in filename and \
	   filename.rsplit('.', 1)[1].lower() in ['mp4']
	print(filename, sys.stderr)
	if not valid:
		raise ValidationError("Your file must have extension .mp4")

def zipdir(archive_path, to_compress):
    zipf = zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED)
    for root, dirs, files in os.walk(to_compress):
        for file in files:
            zipf.write(os.path.join(root, file))
    zipf.close()

class ReusableForm(FlaskForm):
	"""User entry form for entering specifics for generation"""
	file = FileField('Video file',
							validators=[FileRequired(),
								is_video_file])
	# Submit button
	submit = SubmitField("Enter")

def run_video2slides(request, upload_folder):
	file = request.files.data
	filename = secure_filename(file.filename)
	new_filename = os.path.join(upload_folder, filename)
	file.save(new_filename)
	try:
		outdir_vid = os.path.join(upload_folder, "out")
		os.makedirs(outdir_vid, exist_ok=True)
		ConvertVideo(new_filename)
		archive_path = os.path.join(upload_folder, "output.zip")
		zipdir(archive_path, outdir_vid)
		send_from_directory(upload_folder, archive_path, as_attachment=True)
	except RuntimeError as e:
		warnings.warn(str(e), RuntimeWarning)
		shutils.rmtree(new_filename)

def main():
	base_dir = '/tmp/video2slides'
	video_dir = os.path.join(base_dir, "videos")
	out_dir = os.path.join(base_dir, "out")
	files = os.listdir(video_dir)
	print(files)
	os.makedirs(out_dir, exist_ok=True)
	for file in files:
		file = os.path.join(video_dir, file)
		if not os.path.isfile(file):
			continue
		ext = file.split('/')[-1].split('.')[-1]
		if ext != 'mp4':
			continue
		basename = file.split('/')[-1].split('.')[-2]
		outdir_vid = os.path.join(out_dir, basename)
		os.makedirs(outdir_vid, exist_ok=True)
		ConvertVideo(file, outdir_vid)

class ConvertVideo:

	def __init__(self, file, outdir, seuil=10000, skipframes=50, autorun=True):
		self.outdir = outdir
		self.capt = cv2.VideoCapture(file)
		self.totalFrames = self.capt.get(cv2.CAP_PROP_FRAME_COUNT)
		self.fps = self.capt.get(cv2.CAP_PROP_FPS)
		print(self.outdir, "fps: %.2f"%self.fps, "n_frames: %d"%self.totalFrames)

		self.csv_file = open(os.path.join(self.outdir, "stats.csv"), "w")
		self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=["frame_id", "timestamp", "unique_frame_id", "difference"])
		self.csv_writer.writeheader()
		self.distances = []

		self.start0 = self.start = time.time()
		n_logs = 0

		self.i = 0
		self.running = True
		self.images = []
		self.seuil = seuil
		self.skipframes = skipframes
		if autorun:
			while self.running:
				self.step()
			self.stop()

	def step(self):
		if self.running:
			if self.i > self.totalFrames:
				self.running = False
			else:
				prof.reset()
				self.capt.set(cv2.CAP_PROP_POS_FRAMES, self.i)
				prof.time("set")
				self.running, image = self.capt.read()
				prof.time("read")
				if self.i == 0:
					ds = cv2.resize(image, (48, 27), interpolation=cv2.INTER_LINEAR)
					self.images.append((self.i,ds))
					cv2.imwrite(os.path.join(self.outdir, "frame_00001_00m_00s.png"), image)
				else:
					ds = cv2.resize(image, (48, 27), interpolation=cv2.INTER_LINEAR)
					prof.time("resize")
					found = -1
					for it, (i_o,o) in enumerate(self.images[-1:-2:-1]):
						d = np.power((ds - o), 2).sum()
						if it == 0:
							self.csv_writer.writerow({
								"frame_id": self.i,
								"timestamp": int(self.i/self.fps),
								"unique_frame_id": i_o,
								"difference": d,
							})
							self.distances.append(d)
							self.csv_file.flush()
						if d < self.seuil:
							found = i_o
							break
					prof.time("check")
					if found == -1:
						self.images.append((self.i,ds))
						seconds = int(self.i/self.fps)
						minutes = int(seconds // 60)
						seconds = int(seconds % 60)
						cv2.imwrite(os.path.join(self.outdir, "frame_%05d_%03dm_%02ds.png" % (len(self.images), minutes, seconds)), image)
						prof.time("write")
					#if i == 2:
					#	print(image.shape, image.max())
					#	break
				prof.print()
				self.i += self.skipframes
				t = time.time()
				if t - self.start > 60:
					self.start = t
					print("elapsed: %.2f"%(t-self.start0), "timestamp: %.2f"%(self.i/self.fps), "n_images: %d"%len(self.images))
			return self.running, {
				"progress": self.i/self.totalFrames,
			}
		else:
			return self.stop()
	
	def stop(self):
		self.csv_file.close()
		self.distances = np.array(self.distances)
		if len(self.distances[self.distances < self.seuil]) == 0:
			maxmin = "None were rejected"
		else:
			maxmin = np.max(self.distances[self.distances<self.seuil])
		if len(self.distances[self.distances >= self.seuil]) == 0:
			minmax = "None were accepted"
		else:
			minmax = np.min(self.distances[self.distances>=self.seuil])
		metadata = {
			"fps": self.fps,
			"Number of frames": self.totalFrames,
			"Look every x frames": self.skipframes,
			"Smallest accepted": minmax,
			"Largest rejected": maxmin,
		}
		return self.running, metadata

if __name__ == '__main__':
	main()
