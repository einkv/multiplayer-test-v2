from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
import os
import eventlet

eventlet.monkey_patch()  # 關鍵！修復 worker timeout

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

rooms = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    username = data.get('username', '匿名')
    room = data.get('room', 'lobby')
    sid = request.sid
    
    join_room(room)
    
    if room not in rooms:
        rooms[room] = []
    
    # 移除舊的同名用戶
    rooms[room] = [u for u in rooms[room] if u['name'] != username]
    
    # 加入新用戶
    rooms[room].append({'name': username, 'sid': sid})
    
    # 廣播給房間所有人
    emit('status', f'{username} 加入房間！', room=room)
    emit('user_list', [u['name'] for u in rooms[room]], room=room, include_self=True)

@socketio.on('send_message')
def on_message(data):
    room = data.get('room')
    msg = data.get('message')
    username = data.get('username')
    if room in rooms:
        emit('new_message', {'username': username, 'message': msg}, room=room)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    for room in list(rooms.keys()):
        before_count = len(rooms[room])
        rooms[room] = [u for u in rooms[room] if u['sid'] != sid]
        if len(rooms[room]) < before_count:  # 有人離開
            if rooms[room]:
                emit('user_list', [u['name'] for u in rooms[room]], room=room)
            else:
                del rooms[room]

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
