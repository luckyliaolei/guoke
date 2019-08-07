from flask import Flask, render_template, request
from db import users
app = Flask(__name__)
import hashlib

@app.route('/user_info', methods=['GET', 'POST'])
def hello_world():
    if request.method == 'POST':
        user_info = dict(request.form)
        users.insert_one(user_info)
        f = request.files['picture']
        f.save('picture/' + str(user_info['_id']) + '.jpg')
        return render_template('success.html')
    else:
        return render_template('index.html')


@app.route('/')
def handle():
    data = request.args
    if len(data) == 0:
        return "hello, this is handle view"
    signature = data.signature
    timestamp = data.timestamp
    nonce = data.nonce
    echostr = data.echostr
    token = "xxxx"  # 请按照公众平台官网\基本配置中信息填写

    list = [token, timestamp, nonce]
    list.sort()
    sha1 = hashlib.sha1()
    map(sha1.update, list)
    hashcode = sha1.hexdigest()
    print("handle/GET func: hashcode, signature: ", hashcode, signature)
    if hashcode == signature:
        return echostr
    else:
        return ""

if __name__ == '__main__':
    app.run()
