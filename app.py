import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
import redis
import json
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 連線 Redis
r = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))

ROOMS_KEY = 'multiplayer:rooms'

def get_rooms():
    data = r.get(ROOMS_KEY)
    return json.loads(data) if data else {}

def save_rooms(rooms):
    r.set(ROOMS_KEY, json.dumps(rooms))

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    username = data.get('username', '匿名')
    room = data.get('room', 'lobby')
    sid = request.sid
    
    join_room(room)
    
    rooms = get_rooms()
    if room not in rooms:
        rooms[room] = {}
    
    # 移除舊用戶
    rooms[room] = {k: v for k, v in rooms[room].items() if v != username}
    rooms[room][sid] = username
    save_rooms(rooms)
    
    emit('user_list', list(rooms[room].values()), room=room)
    emit('status', f'{username} 加入了房間！', room=room)

@socketio.on('send_message')
def on_message(data):
    room = data.get('room')
    msg = data.get('message')
    username = data.get('username')
    rooms = get_rooms()
    if room in rooms:
        emit('new_message', {'username': username, 'message': msg}, room=room)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    rooms = get_rooms()
    for room in list(rooms.keys()):
        if sid in rooms[room]:
            username = rooms[room].pop(sid)
            if not rooms[room]:
                del rooms[room]
            else:
                emit('user_list', list(rooms[room].values()), room=room)
            save_rooms(rooms)
            break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
