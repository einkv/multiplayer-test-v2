import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
import redis
import json
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'poker-secret-2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Redis 連線
r = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))
ROOMS_KEY = 'poker:rooms'

# 撲克牌
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
DECK = [f"{rank}{suit}" for suit in SUITS for rank in RANKS]

def get_rooms():
    data = r.get(ROOMS_KEY)
    return json.loads(data) if data else {}

def save_rooms(rooms):
    r.set(ROOMS_KEY, json.dumps(rooms))

def create_deck():
    deck = DECK[:]
    random.shuffle(deck)
    return deck

def card_value(card):
    rank = card[:-1]
    if rank in ['J', 'Q', 'K']: return 10
    if rank == 'A': return 14
    return int(rank)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('create_room')
def create_room(data):
    username = data['username']
    room = data['room']
    sid = request.sid
    
    rooms = get_rooms()
    if room in rooms:
        emit('error', '房間已存在！')
        return
    
    # 建立新房間
    deck = create_deck()
    rooms[room] = {
        'players': {sid: {'name': username, 'hand': deck[:13], 'ready': False}},
        'deck': deck[13*4:],
        'current_player': None,
        'played_cards': [],
        'round': 0,
        'status': 'waiting'  # waiting, playing, finished
    }
    save_rooms(rooms)
    join_room(room)
    
    emit('room_created', {
        'room': room,
        'players': list(rooms[room]['players'].values())
    })
    emit('hand', deck[:13], to=sid)

@socketio.on('join_room')
def join_room_event(data):
    username = data['username']
    room = data['room']
    sid = request.sid
    
    rooms = get_rooms()
    if room not in rooms:
        emit('error', '房間不存在！')
        return
    if len(rooms[room]['players']) >= 4:
        emit('error', '房間已滿！')
        return
    if any(p['name'] == username for p in rooms[room]['players'].values()):
        emit('error', '名字重複！')
        return
    
    # 發牌
    hand = rooms[room]['deck'][:13]
    rooms[room]['deck'] = rooms[room]['deck'][13:]
    rooms[room]['players'][sid] = {'name': username, 'hand': hand, 'ready': False}
    save_rooms(rooms)
    join_room(room)
    
    emit('joined', {
        'players': list(rooms[room]['players'].values()),
        'status': rooms[room]['status']
    }, room=room)
    emit('hand', hand, to=sid)

@socketio.on('ready')
def player_ready():
    sid = request.sid
    rooms = get_rooms()
    for room, data in rooms.items():
        if sid in data['players']:
            data['players'][sid]['ready'] = True
            save_rooms(rooms)
            
            # 檢查是否全員準備
            if all(p['ready'] for p in data['players'].values()) and len(data['players']) == 4:
                data['status'] = 'playing'
                data['current_player'] = random.choice(list(data['players'].keys()))
                data['played_cards'] = []
                data['round'] += 1
                save_rooms(rooms)
                emit('game_start', {
                    'current_player': data['players'][data['current_player']]['name']
                }, room=room)
            else:
                emit('players_update', list(data['players'].values()), room=room)
            break

@socketio.on('play_card')
def play_card(data):
    sid = request.sid
    card = data['card']
    rooms = get_rooms()
    
    for room, data in rooms.items():
        if sid in data['players'] and data['status'] == 'playing':
            player = data['players'][sid]
            if sid != data['current_player']:
                emit('error', '不是你的回合！')
                return
            if card not in player['hand']:
                emit('error', '你沒有這張牌！')
                return
            
            # 出牌
            player['hand'].remove(card)
            data['played_cards'].append({'sid': sid, 'card': card})
            save_rooms(rooms)
            
            # 廣播
            emit('card_played', {
                'player': player['name'],
                'card': card,
                'remaining': len(player['hand'])
            }, room=room)
            
            # 下一位
            player_sids = list(data['players'].keys())
            next_idx = (player_sids.index(sid) + 1) % 4
            data['current_player'] = player_sids[next_idx]
            save_rooms(rooms)
            
            emit('next_turn', {
                'current_player': data['players'][data['current_player']]['name']
            }, room=room)
            break

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    rooms = get_rooms()
    for room in list(rooms.keys()):
        if sid in rooms[room]['players']:
            del rooms[room]['players'][sid]
            if not rooms[room]['players']:
                del rooms[room]
            save_rooms(rooms)
            break