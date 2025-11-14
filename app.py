import eventlet
eventlet.monkey_patch()  # 必須在最上面！

from flask import Flask, render_template
from flask_socketio import SocketIO, join_room, emit, send
import os

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
        rooms[room] = {}
    
    # 移除舊用戶（同名）
    rooms[room] = {k: v for k, v in rooms[room].items() if v != username}
    rooms[room][sid] = username  # 用 sid 當 key
    
    # 廣播給整個房間（包含自己）
    emit('user_list', list(rooms[room].values()), room=room)
    emit('status', f'{username} 加入了房間！', room=room)

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
        if sid in rooms[room]:
            username = rooms[room].pop(sid)
            if not rooms[room]:
                del rooms[room]
            else:
                emit('user_list', list(rooms[room].values()), room=room)
            break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
