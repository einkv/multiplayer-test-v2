from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
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
    username = data['username']
    room = data['room']
    join_room(room)
    
    if room not in rooms:
        rooms[room] = {'users': []}
    
    current_sid = request.sid  # 正確的 SocketIO sid
    
    # 避免重複
    if not any(u['name'] == username for u in rooms[room]['users']):
        rooms[room]['users'].append({'name': username, 'sid': current_sid})
    
    emit('status', {'msg': f'{username} 加入房間！'}, room=room)
    emit('user_list', [u['name'] for u in rooms[room]['users']], room=room)

@socketio.on('send_message')
def on_message(data):
    room = data['room']
    msg = data['message']
    username = data['username']
    emit('new_message', {'username': username, 'message': msg}, room=room)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    for room in list(rooms.keys()):
        rooms[room]['users'] = [u for u in rooms[room]['users'] if u['sid'] != sid]
        if not rooms[room]['users']:
            del rooms[room]
        else:
            emit('user_list', [u['name'] for u in rooms[room]['users']], room=room)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))