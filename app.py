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
        user_id = request.args.get('user_id')
        user = users.find_one({'_id': user_id})
        profile = user.get('profile', {})
        condition = user.get('condition', {})
        return render_template('index.html', profile=profile, condition=condition)


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
        self.url = '<a href="http://www.nipc.org.cn:24255/user_info?user_id=' + msg.source + '">点击此处</a>'

    def text_reply(self, content):
        return TextReply(content=content, message=self.msg).render()

    def download_img(self):
        r_chunk = requests.get(self.msg.image, stream=True)
        # Throw an error for bad status codes
        r_chunk.raise_for_status()
        with open('static/picture/' + self.msg.media_id + '.jpg' , 'wb') as handle:
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
                return self.text_reply('感谢你关注本订阅号，我们承诺不泄露隐私信息，你的信息将会在取消关注本订阅号后自动删除，回复“资料”即可开始填写，也可以通过我们的网站填写%s。由于公众号的限制我们不能主动给你发消息，只能被动恢复消息，所以并不是我们不理你。有事儿没事儿多回复“在吗”，将会有不一样的惊喜等着你哦。' % self.url)
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
                    return self.text_reply('已经回答过该问题, 查看资料请' + self.url)

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
            elif self.msg.content == '匹配':
                self.match()

            elif self.msg.content == '查看资料':
                self.look()

            elif self.msg.content == '修改资料':
                self.edit()

            if not user.get('profile'):
                return self.text_reply('你好，是不是有点无聊了，你好像还没上传资料，要不然回复“资料”启动信息采集程序？')
            if not user.get('condition'):
                return self.text_reply('你好，是不是有点无聊了，你好像还没上传择偶条件，要不然回复“条件”启动信息采集程序？')
            return self.text_reply('没事儿干了吗，可以回答问题玩哦，你的回答将会被我们推送到我们算法给你匹配到的跟你合适的人的那里，如果Ta对你的回答感兴趣，我们也会推送他的消息给你哦，当你们的熟悉程度到达一定值后，我们将互相推送微信号，在此之前你们所有信息都是匿名的哦，回复“问题”查看问题列表')

    def answer(self, question_id, question_index):
        last_qu, next_qu = questions.find_one({
            '_id': question_id}, {'content': {'$slice': [question_index, 2]}})['content']

        if self.msg.type == 'text' and self.msg.content == '过':
            users.update_one({
                '_id': self.msg.source}, {
                '$set': {
                    'answering.question_index': question_index + 1}
            })
        else:
            # 下面是验证答案的有效性。
            # 类型验证
            if last_qu.get('type') != self.msg.type:
                return self.text_reply('你的回答类型有误, 回答要求是%s类型。' % last_qu.get('type'))

            # 正则验证
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
                return self.text_reply('嗯嗯，再来一张？回复“过”跳过该问题')


            users.update_one({
                '_id': self.msg.source}, {
                '$set': {
                    question_id + '.' + last_qu['filed']: self.msg.content,
                    'answering.question_index': question_index + 1}
            })

        if not next_qu.get('filed'):  # 间接判断是否为最后一问，但最好还是直接判断(idx==len)以增强可读性和代码健壮性。
            users.update_one({
                '_id': self.msg.source}, {
                '$unset': {
                    'answering': ''}  # 最后一个问题没有答案，所以在回复之前即可删掉answering状态字段。
            })

        return self.text_reply(next_qu['question'])

    def match(self):
        users.find({})

    def look_info(self):
        users.find({})

if __name__ == '__main__':
    app.run()
