from flask import request, Flask
from flask import render_template
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import (TextField, validators, SubmitField, 
                    DecimalField, IntegerField)
from werkzeug.datastructures import CombinedMultiDict

import video2slides
import os

app = Flask(__name__)
Bootstrap(app)
app.config['SECRET_KEY'] = 'ayayayay'
app.config['UPLOAD_FOLDER'] = '/tmp/video2slides/videos'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def _get_buttonclick(request):
    buttonclick = request.form.getlist('submit')
    # print(buttonclick)
    buttonclick = 'Enter' in buttonclick
    return buttonclick

# Home page
@app.route("/", methods=['GET', 'POST'])
def home():
    """Home page of app with form"""

    return render_template('home.html')

@app.route("/video2slides", methods=['GET', 'POST'])
def home_video2slides():
    # Create form
    form = video2slides.ReusableForm(CombinedMultiDict((request.files, request.form)))

    print('request.method', request.method)
    print('request.args', request.args)
    print('request.form', request.form)
    print('request.files', request.files)

    if request.method == 'POST' and form.validate():
        result = video2slides.run_video2slides(form, app.config['UPLOAD_FOLDER'])
        buttonclick = _get_buttonclick(request)
        return render_template('video2slides/video2slides.html', form=form, input=result, buttonclick=buttonclick)
    else:
        # Send template information to index.html
        return render_template('video2slides/video2slides.html', form=form, buttonclick=False)

app.run(host='127.0.0.1', port=5000, debug=True)
app.run()
