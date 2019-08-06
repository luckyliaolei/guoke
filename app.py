from flask import Flask, render_template, request
from db import users
app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def hello_world():
    if request.method == 'POST':
        users.insert_one(dict(request.form))
        return 'success'
    else:
        return render_template('index.html')


if __name__ == '__main__':
    app.run()
