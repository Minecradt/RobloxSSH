import json
import uuid, time
import socket
import threading
import paramiko, os, hashlib
from flask import Flask, request

KEY_FILE = 'server_key.rsa'
if not os.path.exists(KEY_FILE):
    key = paramiko.RSAKey.generate(2048)
    key.write_private_key(open(KEY_FILE, 'w'))  # Use write_private_key method
    print(f"RSA key pair generated and saved as '{KEY_FILE}'")
else:
    print(f"Using existing RSA key from '{KEY_FILE}'")
HOST_KEY = paramiko.RSAKey(filename=KEY_FILE)
#USERNAME = "test"
#PASSWORD = "1234"
GAME_AUTH = {}


class SSHServer(paramiko.ServerInterface):

    def __init__(self):
        self.is_new = False
        self.username = b''
        self.password = b''
        self.key_auth = False

    def check_auth_password(self, username, password):
        self.username = username
        self.password = password
        if username in GAME_AUTH:
            password = hashlib.sha512(
                password.encode()).hexdigest()
            success = password == GAME_AUTH[username]
            if not success:
                #print(games[username],password,games[username]==password)
                success = password == games[username]
                self.key_auth = success
            if success:
                return paramiko.AUTH_SUCCESSFUL
            else:
                return paramiko.AUTH_FAILED
        else:
            self.is_new = True
            return paramiko.AUTH_SUCCESSFUL

        #if username == USERNAME and password == PASSWORD:
        #    return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_global_request(self, kind, msg):
        # print(kind,msg)
        return False

    def get_allowed_auths(self, username):
        #print(username)
        return "password"

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel):
        return True

    def check_channel_pty_request(self, channel, term, width, height,
                                  pixelwidth, pixelheight, modes):
        return True


channels = []


def handle_client(client):
    global channels
    transport = paramiko.Transport(client)
    transport.add_server_key(HOST_KEY)

    server = SSHServer()
    try:
        transport.start_server(server=server)
    except paramiko.SSHException:
        #print("SSH negotiation failed")
        return

    channel = transport.accept(20)
    if channel is None:
        #print("No channel")
        return
    entering_pw = 0
    if server.key_auth:
        channel.send('-------- YOU ARE USING KEY AUTHENTICATION --------\r\n')
    if not server.username in games.keys():
        channel.send("This game is NOT running RoSSH\r\n")
        channel.close()
        transport.close()
        return
    confirming_pw = 0
    exec_enviroment = 'global'
    console_format = '({exec}) '
    format_console = lambda: console_format.format(exec=exec_enviroment)

    if server.is_new:
        channel.send(
            "RoSSH password hasn't been setup yet, please enter a password.\r\n: "
        )
        entering_pw = 1
    else:
        channel.send("You have entered RoSSH\r\n")
        channel.send(format_console())
        channels.append(channel)

    #channel.send("Welcome to the Python SSH server!\r\n")
    #channel.send("> ")
#
    set_pw = ''
    prevcmd = ''
    buffer = ""
    prevchar = ''
    prevprevchar = ''
    idx = 0
    in_code = False
    while True:
        data = channel.recv(1024)
        if not data:
            break

        for ch in data.decode(errors="ignore"):
            if exec_enviroment != 'global':
                #print(ids,server.username)
                filter_thing = 0
                for i in ids[server.username]:
                    if i[0] == exec_enviroment:
                        filter_thing = 1
                if filter_thing == 0:
                    exec_enviroment = 'global'
                #if not exec_enviroment in ids[server.username].keys():
                #    exec_enviroment = 'global'
                # channel.send("Yo")
            if (prevprevchar == '\x1b') and (prevchar == '['):
                # hex codes handled here
                if ch == 'A':
                    buffer = prevcmd
                    channel.send('\x1b[2K\r' + format_console() + buffer)
                    prevprevchar = prevchar
                    prevchar = ch
                    continue
            # Enter = execute

            #print(ch.encode())
            if ch in ["\r", "\n"]:
                cmd = buffer.strip()
                buffer = ""
                if entering_pw:
                    if confirming_pw:
                        if cmd != set_pw:
                            channel.send(
                                "\r\nPasswords do not match, try again.\r\n: ")
                        else:
                            GAME_AUTH[server.username] = hashlib.sha512(
                                cmd.encode()).hexdigest()
                            channel.send(
                                "\r\nCorrect password. Please reconnect.\r\n")
                            channel.close()
                            transport.close()
                            save_games()
                            return
                                

                    else:
                        set_pw = cmd
                        channel.send('\r\nPlease confirm your password\r\n: ')
                        confirming_pw = 1
                elif in_code and (not cmd.startswith('!')):
                        channel.send("\r\n")

                        #if cmd=='!exit':
                        #    in_code = False
                        #    console_format = '({exec}) '
                        prevcmd = cmd
                        if True:
                            if exec_enviroment == 'global':
                                for i in ids[server.username]:
                                    players = ask_server(server.username, i[0],
                                                         {"type": "code","code":cmd})
                                    channel.send('----' + i[0] + '----\r\n')
                                    if players[1] == 1:
                                        channel.send('Error fetching.\r\n')
                                    else:
                                        out = json.loads(players[0])
                                        send_message = ""
                                        if out['success']==0:
                                            send_message = 'Error: '
                                        else:
                                            send_message = 'Output: '
                                        if not 'msg' in out.keys():
                                            out['msg'] = ''
                                        send_message += out['msg']
                                        channel.send(send_message + '\r\n')
                                        #channel.send(
                                        #    f'Players ({len(players)}): {", ".join(players)}\r\n'
                                        #)
                            else:
                                players = ask_server(server.username,
                                                     exec_enviroment,
                                                     {"type": "players"})
                                if players[1] == 1:
                                    channel.send('Error fetching.\r\n')
                                else:
                                    out = json.loads(players[0])
                                    send_message = ""
                                    if out['success']==0:
                                        send_message = 'Error: '
                                    else:
                                        send_message = 'Output: '
                                    send_message += out['msg']
                                    channel.send(send_message + '\r\n')
                            channel.send(format_console())
                        
                    
                else:
                    channel.send("\r\n")
                    prevcmd = cmd

                    if cmd.startswith('!') and in_code:
                        cmd = cmd[1:]
                    command = cmd.split(' ')[0].lower()
                    args = cmd.split(' ')[1:]
                    if command=='code':
                        in_code = 1
                        console_format = "({exec}) [Exec] "
                        channel.send('To run regular commands, use !<regular command>.\r\n')
                    if command=='terminal' and in_code:
                        in_code=0
                        console_format='({exec}) '
                    if command == 'help':
                        channel.send("""list - Lists all the servers.\r
exit - Exits the terminal\r
quit - alias for exit\r
logout - alias for exit\r
help - this page xd\r
server serverid/global - goes into a server\r
players - lists out players\r
kick player [reason]- Kicks player\r
kickall [reason] - Kicks everyone\r
terminal (Code enviroment only) - Exits the code enviroment\r
code - Enters the code enviroment. \r
""")
                    if command in ["exit", "quit", "logout"]:
                        channel.send("Bye!\r\n")
                        channel.close()
                        transport.close()
                        return
                    if command == 'kickall':
                        enter_help = False
                        #enter_help = len(args)
                        if len(args) > 0:
                            enter_help = args[0] == '--help'
                        if enter_help:
                            channel.send("kickall [reason]\r\n")
                        else:
                            if exec_enviroment == 'global':
                                new_thing = ids[server.username]
                                for i in new_thing:
                                    success = ask_server(
                                        server.username, i[0], {
                                            "type": "kickall",
                                            "msg": ' '.join(args[0:])
                                        })
                                    channel.send('----' + i[0] + '----\r\n')

                                    if success[1]:
                                        channel.send('Error fetching...\r\n')
                                    else:
                                        success = json.loads(success[0])['msg']
                                        channel.send(success + '\r\n')
                            else:
                                success = ask_server(
                                    server.username, exec_enviroment, {
                                        "type": "kickall",
                                        "msg": ' '.join(args[0:])
                                    })
                                #channel.send('----' + i[0] + '----\r\n')
                                if success[1]:
                                    channel.send('Error fetching...\r\n')
                                else:
                                    success = json.loads(success[0])['msg']
                                    channel.send(success + '\r\n')

                    if command == 'kick':
                        enter_help = False
                        enter_help = len(args) < 1
                        if not enter_help:
                            enter_help = args[0] == '--help'
                        if enter_help:
                            channel.send("kick username [reason]\r\n")
                        else:
                            if exec_enviroment == 'global':
                                new_thing = ids[server.username]
                                for i in new_thing:
                                    success = ask_server(
                                        server.username, i[0], {
                                            "type": "kick",
                                            "player": args[0],
                                            "msg": ' '.join(args[1:])
                                        })
                                    channel.send('----' + i[0] + '----\r\n')

                                    if success[1]:
                                        channel.send('Error fetching...\r\n')
                                    else:
                                        success = json.loads(success[0])['msg']
                                        channel.send(success + '\r\n')
                            else:
                                success = ask_server(
                                    server.username, exec_enviroment, {
                                        "type": "kick",
                                        "player": args[0],
                                        "msg": ' '.join(args[1:])
                                    })
                                #channel.send('----' + i[0] + '----\r\n')
                                if success[1]:
                                    channel.send('Error fetching...\r\n')
                                else:
                                    success = json.loads(success[0])['msg']
                                    channel.send(success + '\r\n')

                    if command == 'players':

                        # if we are in global
                        if exec_enviroment == 'global':
                            for i in ids[server.username]:
                                players = ask_server(server.username, i[0],
                                                     {"type": "players"})
                                channel.send('----' + i[0] + '----\r\n')
                                if players[1] == 1:
                                    channel.send('Error fetching.\r\n')
                                else:
                                    players = json.loads(players[0])['players']
                                    channel.send(
                                        f'Players ({len(players)}): {", ".join(players)}\r\n'
                                    )
                        else:
                            players = ask_server(server.username,
                                                 exec_enviroment,
                                                 {"type": "players"})
                            if players[1] == 1:
                                channel.send('Error fetching.\r\n')
                            else:
                                players = json.loads(players[0])['players']

                                channel.send(
                                    f'Players ({len(players)}): {", ".join(players)}\r\n'
                                )

                    #if command=='ping':
                    #    channel.send(str(ask_server(server.username,exec_enviroment,{"type":"ping"})) + '\r\n')
                    if command == 'list':
                        for i in ids[server.username]:
                            channel.send(i[0] + ' - ' + i[1] + '\r\n')
                    #if command=='changepw'
                    if command == 'server':
                        server_name = ' '.join(args)
                        if server_name == 'global':
                            exec_enviroment = 'global'
                            channel.send("Success.\r\n")

                        else:
                            if len([
                                    element for element in ids[server.username]
                                    if element[0] == server_name
                            ]) != 0:
                                exec_enviroment = server_name
                                channel.send("Success.\r\n")

                            else:
                                channel.send("Server name not valid.\r\n")
                    channel.send(format_console())
                    #channel.send(cmd)


#
#if cmd:
#    channel.send(f"You ran: {cmd}\r\n")
#channel.send("> ")

# Backspace
            elif ch in ("\b", "\x7f"):
                if buffer:
                    buffer = buffer[:-1]
                    channel.send("\b \b")

            # Ctrl+C (ASCII 3)
            elif ch == "\x03":
                channel.close()
                transport.close()
                return

            # Normal character
            else:
                buffer += ch
                #channel.send(ch)
                if entering_pw:
                    channel.send('*')
                else:
                    channel.send(ch)
            prevprevchar = prevchar
            prevchar = ch


def start_ssh_server(host="0.0.0.0", port=2323):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    sock.listen(100)
    print(f"SSH server running on {host}:{port}")

    while True:
        client, addr = sock.accept()
        print(f"Connection from {addr}")
        threading.Thread(target=handle_client, args=(client, )).start()


app = Flask(__name__)


def is_all(args, required):
    for i in required:
        if not i in args.keys():
            return False
    return 1


def ask_server(gid, sid, data):
    global requests, responses, reqids
    requestuuid = str(uuid.uuid4())
    reqids.append(requestuuid)
    dta = data
    dta['requestid'] = requestuuid
    requests[gid][sid].append(dta)
    currtime = time.time()
    while not requestuuid in responses[gid].keys():
        if time.time() - currtime >= 30:
            return ['', 1]
    response = responses[gid][requestuuid]
    del responses[gid][requestuuid]
    return [response, 0]


games = {}
ids = {}
requests = {}
responses = {}
reqids = []


@app.route('/game/register')
def slash():
    global games
    # print(request.args,)
    if not is_all(request.args, ['key', 'gameid']):
        return 'Missing arguments!', 503
    if request.args['gameid'] in games.keys():
        return 'Game already used.'
    games[request.args['gameid']] = hashlib.sha512(
        request.args['key'].encode()).hexdigest()
    save_games()
    return 'Hello from flask!'


@app.route('/game/respond')
def gamerespond():
    global games, responses, reqids
    if not is_all(request.args, ['key', 'gameid', 'reqid', 'data']):
        return 'Missing arguments!', 503
    rid = request.args['reqid']
    key = request.args['key']
    gid = request.args['gameid']

    if not gid in games.keys():
        return "Game not found", 404
    if games[gid] != hashlib.sha512(
        key.encode()).hexdigest():
        return "Invalid key", 403
    if not rid in reqids:
        return 'Invalid request ID', 404
    if not gid in responses.keys():
        responses[gid] = {}
    responses[gid][rid] = request.args['data']
    reqids.remove(rid)

    return 'Success'


@app.route('/game/request')
def gamerequest():
    global games, requests, responses
    if not is_all(request.args, ['key', 'gameid', 'serverid', 'type']):
        return 'Missing arguments!', 503
    args = request.args
    if not args['gameid'] in games.keys():
        return 'Game not found', 404
    if hashlib.sha512(
        args['key'].encode()).hexdigest() != games[args['gameid']]:
        return 'Invalid key', 403

    if not (args['serverid'], args['type']) in ids[args['gameid']]:
        return 'Not found', 404
    gid = args['gameid']
    sid = args['serverid']
    stype = args['type']
    if not gid in requests.keys():
        requests[gid] = {}
    if not gid in responses.keys():
        responses[gid] = {}
    if not sid in requests[gid].keys():
        requests[gid][sid] = []
    requests[gid][sid] = requests[gid][sid][::-1]
    if len(requests[gid][sid]) == 0:
        req = {"success": 0}
    else:
        req = requests[gid][sid].pop()
        req['success'] = 1
        requests[gid][sid] = requests[gid][sid][::-1]
    return req


@app.route('/game/remove')
def gameremove():
    global games, ids
    if not is_all(request.args, ['key', 'gameid', 'serverid', 'type']):
        return 'Missing arguments!', 503
    args = request.args
    if not args['gameid'] in games.keys():
        return 'Game not found', 404
    if games[args['gameid']] != hashlib.sha512(
        args['key'].encode()).hexdigest():
        return "Invalid key", 403
    if not args['gameid'] in ids.keys():
        ids[args['gameid']] = set()
    if not (args['serverid'], args['type']) in ids[args['gameid']]:
        return 'Not found', 404
    ids[args['gameid']].remove((args['serverid'], args['type']))
    save_games()
    #set().remove()#
    return 'Success'


@app.route('/game/add')
def gameadd():
    global games, ids
    if not is_all(request.args, ['key', 'gameid', 'serverid', 'type']):
        return 'Missing arguments!', 503
    args = request.args
    if not args['gameid'] in games.keys():
        return 'Game not found', 404
    if games[args['gameid']] != hashlib.sha512(
        args['key'].encode()).hexdigest():
        return "Invalid key", 403
    if not args['gameid'] in ids.keys():
        ids[args['gameid']] = set()
    ids[args['gameid']].add((args['serverid'], args['type']))
    save_games()
    return 'Success'


#@app.route('/game/request')


def save_games():
    global games, GAME_AUTH
    json.dump(GAME_AUTH, open('auth.json', 'w'))
    json.dump(games, open('game.json', 'w'))


@app.route('/game/exist')
def gameexist():
    if not is_all(request.args, ['gameid', 'serverid', 'type']):
        return 'Missing arguments!', 503
    #print(games, ids)
    #print((request.args['gameid'] in games.keys()), (request.args['serverid'] in ids[request.args['gameid']]), ids, games)
    success = (request.args['gameid'] in games.keys())
    if success:
        success = ((request.args['serverid'], request.args['type'])
                   in ids[request.args['gameid']])
    return ['no', 'yes'][success]


if os.path.isfile('auth.json'):
    GAME_AUTH = json.load(open('auth.json', 'r'))
if os.path.isfile('game.json'):
    games = json.load(open('game.json', 'r'))
    for i in games.keys():
        if not i in ids.keys():
            ids[i] = set()
if __name__ == "__main__":
    threading.Thread(target=app.run, daemon=1).start()
    start_ssh_server()
#e