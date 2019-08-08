from flask import Flask, render_template, request
from wechatpy.utils import check_signature
from wechatpy.exceptions import InvalidSignatureException
from wechatpy import parse_message
from wechatpy.replies import TextReply
from db import users, questions
import requests

import re
app = Flask(__name__)


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


@app.route('/', methods=['GET', 'POST'])
def handle():
    data = request.args
    if len(data) == 0:
        return "hello, this is handle view"
    signature = data['signature']
    timestamp = data['timestamp']
    nonce = data['nonce']
    token = "xhn"
    try:
        check_signature(token, signature, timestamp, nonce)
    except InvalidSignatureException:
        return ''
    # echostr = data['echostr']
    msg = parse_message(request.data)
    return Msg_handle(msg).msg_hendle()
    # if msg.type == 'text':
    #     reply = TextReply(content=msg.content, message=msg)
    #     return reply.render()


class Msg_handle:

    def __init__(self, msg):
        self.msg = msg

    def text_reply(self, content):
        return TextReply(content=content, message=self.msg).render()

    def download_img(self):
        r_chunk = requests.get(self.msg.image, stream=True)
        # Throw an error for bad status codes
        r_chunk.raise_for_status()
        with open('picture/' + self.msg.media_id + '.jpg' , 'wb') as handle:
            for block in r_chunk.iter_content(1024):
                handle.write(block)

    def msg_hendle(self):
        user = users.find_one({
            '_id': self.msg.source})
        if not user:
            user = {
                "_id": self.msg.source,
                "profile": {},
                "condition": {}
            }
            users.insert_one(user)

        if self.msg.type == 'event':
            if self.msg.event == 'subscribe' :
                return self.text_reply('感谢你关注本订阅号，我们承诺不泄露隐私信息，你的信息将会在取消关注本订阅号后自动删除，回复“资料”即可开始填写，你也可以通过访问<a href="www.nipc.org.cn:24250">个人资料填写</a>通过网页填写。')
            elif self.msg.event == "unsubscribe":
                pass
            else:
                pass


        if user.get('answering'):  # 用户正在回答问题, 调用anwser函数处理答案。
            return self.answer(user['answering']['question_id'], user['answering']['question_index'])
        else:  # 用户发了段新信息，判断是否为key
            if self.msg.type != 'text':
                return self.text_reply('额，看不是很懂耶。')
            question = questions.find_one({
                'key': self.msg.content}, {
                '_id': 1})

            if question:
                if user.get(question['_id']):
                    return self.text_reply('已经回答过该问题')

                users.update_one({
                    '_id': self.msg.source}, {
                    '$set': {
                        'answering': {
                            "question_time": self.msg.create_time,
                            "question_id": question['_id'],
                            "question_index": 0}}})
                first_qu = questions.find_one({
                    '_id': question['_id']}, {
                    'content': {
                        '$slice': [0, 1]}})['content'][0]

                return self.text_reply(first_qu['question'])
            elif self.msg.content == '':
                # todo
                pass

            return self.text_reply('你好，是不是有点无聊了，你好像还没上传资料，要不然回复“资料”开始上传？你也可以通过用我们的网页进行填写。<a href="http://www.nipc.org.cn:24255?user_id=' + self.msg.source + '">点我试试</a>')


    def answer(self, question_id, question_index):
        last_qu, next_qu = questions.find_one({
            '_id': question_id}, {'content': {'$slice': [question_index, 2]}})['content']

        # 下面是验证答案的有效性。
        if self.msg.type == 'text' and self.msg.content.lower() == 'j':
            users.update_one({
                '_id': self.msg.source}, {
                '$set': {
                    'answering.question_index': question_index + 1}
            })
        else:

            if last_qu.get('type') != self.msg.type:
                return self.text_reply('你的回答类型有误')

            regex = last_qu.get('regex')
            if regex and not re.match(regex, self.msg.content):
                return self.text_reply(last_qu['error'])


            if last_qu.get('type') == 'image':
                self.download_img()
                users.update_one({
                    '_id': self.msg.source}, {
                    '$push': {
                        'profile.' + last_qu['filed']: self.msg.media_id}
                })
                return self.text_reply('再来一张？回复“j”跳过。')


            users.update_one({
                '_id': self.msg.source}, {
                '$set': {
                    question_id + '.' + last_qu['filed']: self.msg.content,
                    'answering.question_index': question_index + 1}
            })

        if not next_qu.get('filed'):
            users.update_one({
                '_id': self.msg.source}, {
                '$unset': {
                    'answering': ''}
            })

        return self.text_reply(next_qu['question'])


if __name__ == '__main__':
    app.run()
