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

seuil = 10000

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
		convert_video(new_filename)
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
		convert_video(file, outdir_vid)

def convert_video(file, outdir):
	capt = cv2.VideoCapture(file)
	totalFrames = capt.get(cv2.CAP_PROP_FRAME_COUNT)
	fps = capt.get(cv2.CAP_PROP_FPS)
	print(outdir, "fps: %.2f"%fps, "n_frames: %d"%totalFrames)

	csv_file = open(os.path.join(outdir, "stats.csv"), "w")
	csv_writer = csv.DictWriter(csv_file, fieldnames=["frame_id", "timestamp", "unique_frame_id", "difference"])
	csv_writer.writeheader()
	distances = []

	start0 = start = time.time()
	n_logs = 0

	i = 0
	success = True
	images = []
	while success:
		if i > totalFrames:
			break
		prof.reset()
		capt.set(cv2.CAP_PROP_POS_FRAMES, i)
		prof.time("set")
		success, image = capt.read()
		prof.time("read")
		if i == 0:
			ds = cv2.resize(image, (48, 27), interpolation=cv2.INTER_LINEAR)
			images.append((i,ds))
			cv2.imwrite(os.path.join(outdir, "frame_00001_00m_00s.jpg"), image)
		else:
			ds = cv2.resize(image, (48, 27), interpolation=cv2.INTER_LINEAR)
			prof.time("resize")
			found = -1
			for it, (i_o,o) in enumerate(images[-1:-2:-1]):
				d = np.power((ds - o), 2).sum()
				if it == 0:
					csv_writer.writerow({
						"frame_id": i,
						"timestamp": int(i/fps),
						"unique_frame_id": i_o,
						"difference": d,
					})
					distances.append(d)
					csv_file.flush()
				if d < seuil:
					found = i_o
					break
			prof.time("check")
			if found == -1:
				images.append((i,ds))
				seconds = int(i/fps)
				minutes = int(seconds // 60)
				seconds = int(seconds % 60)
				cv2.imwrite(os.path.join(outdir, "frame_%05d_%03dm_%02ds.jpg" % (len(images), minutes, seconds)), image)
				prof.time("write")
			#if i == 2:
			#	print(image.shape, image.max())
			#	break
		prof.print()
		i += 50
		t = time.time()
		if t - start > 60:
			start = t
			print("elapsed: %.2f"%(t-start0), "timestamp: %.2f"%(i/fps), "n_images: %d"%len(images))
	csv_file.close()
	distances = np.array(distances)
	maxmin = np.max(distances[distances<seuil])
	minmax = np.min(distances[distances>=seuil])
	print("Differences no-mans-range: %.2f - %.2f"%(maxmin, minmax))

if __name__ == '__main__':
	main()
