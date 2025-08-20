import socket
import threading
import paramiko,os
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
    def check_auth_password(self, username, password):
        self.username = username
        self.password = password
        if username in GAME_AUTH:

            if password==GAME_AUTH[username]:
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
        print(kind,msg)
        return False
    def get_allowed_auths(self, username):
        print(username)
        return "password"

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel):
        return True

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
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
        print("SSH negotiation failed")
        return

    channel = transport.accept(20)
    if channel is None:
        print("No channel")
        return
    entering_pw = 0
    if not server.username in games.keys():
        channel.send("This game is NOT running RoSSH\r\n")
        channel.close()
        transport.close()
        return
    confirming_pw = 0
    exec_enviroment = 'global'

    if server.is_new:
        channel.send("RoSSH password hasn't been setup yet, please enter a password.\r\n: ")
        entering_pw=1
    else:
        channel.send("You have entered RoSSH\r\n")
        channel.send('(' + exec_enviroment + ') ')
        channels.append(channel)

    #channel.send("Welcome to the Python SSH server!\r\n")
    #channel.send("> ")
#
    set_pw = ''

    buffer = ""
    
    while True:
        data = channel.recv(1024)
        if not data:
            break

        for ch in data.decode(errors="ignore"):
            # Enter = execute
            #print(ch)
            if ch in ["\r", "\n"]:
                cmd = buffer.strip()
                buffer = ""
                if entering_pw:
                    if confirming_pw:
                        if cmd!=set_pw:
                            channel.send("\r\nPasswords do not match, try again.\r\n: ")
                        else:
                            GAME_AUTH[server.username] = cmd
                            channel.send("\r\nCorrect password. Please reconnect.\r\n")
                            channel.close()
                            transport.close()
                            return
                    else:
                        set_pw = cmd
                        channel.send('\r\nPlease confirm your password\r\n: ')
                        confirming_pw = 1
                else:
                    channel.send("\r\n")
                    command = cmd.split(' ')[0]
                    args = cmd.split(' ')[1:]
                    if command=='help':
                        channel.send("""list - Lists all the servers.\r
exit - Exits the terminal\r
quit - alias for exit\r
logout - alias for exit\r
help - this page xd\r
server - goes into a server\r
""")
                    if command=='list':
                        for i in ids[server.username]:
                            channel.send(i[0] + ' - ' + i[1] + '\r\n')
                    if command=='server':
                        server_name = ' '.join(args)
                        if server_name == 'global':
                            exec_enviroment = 'global'
                            channel.send("Success.\r\n")

                        else:
                            if len([element for element in elements if element[0] == server_name])!=0:
                                exec_enviroment = server_name
                                channel.send("Success.\r\n")

                            else:
                                channel.send("Server name not valid.\r\n")
                    channel.send('(' + exec_enviroment + ") ")
                    #channel.send(cmd)


                if cmd.lower() in ["exit", "quit", "logout"]:
                    channel.send("Bye!\r\n")
                    channel.close()
                    transport.close()
                    return
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

def start_ssh_server(host="0.0.0.0", port=4545):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    sock.listen(100)
    print(f"SSH server running on {host}:{port}")

    while True:
        client, addr = sock.accept()
        print(f"Connection from {addr}")
        threading.Thread(target=handle_client, args=(client,)).start()

app = Flask(__name__)

def is_all(args, required):
    for i in required:
        if not i in args.keys():
            return False
    return 1
games = {}
ids = {}
@app.route('/game/register')
def slash():
    global games
   # print(request.args,)
    if not is_all(request.args,['key','gameid']):
        return 'Missing arguments!',503
    if request.args['gameid'] in games.keys():
        return 'Game already used.'
    games[request.args['gameid']] = request.args['key']
    
    return 'Hello from flask!'

@app.route('/game/remove')
def gameremove():
    global games, ids
    if not is_all(request.args,['key','gameid','serverid','type']):
        return 'Missing arguments!',503
    args = request.args
    if not args['gameid'] in games.keys():
        return 'Game not found',404
    if games[args['gameid']]!=args['key']:
        return "Invalid key",403
    if not args['gameid'] in ids.keys():
        ids[args['gameid']] = set()
    if not (args['serverid'],args['type']) in ids[args['gameid']]:
        return 'Not found',404
    ids[args['gameid']].remove((args['serverid'],args['type']))
    #set().remove()#
    return 'Success'
@app.route('/game/add')
def gameadd():
    global games, ids
    if not is_all(request.args,['key','gameid','serverid','type']):
        return 'Missing arguments!',503
    args = request.args
    if not args['gameid'] in games.keys():
        return 'Game not found',404
    if games[args['gameid']]!=args['key']:
        return "Invalid key",403
    if not args['gameid'] in ids.keys():
        ids[args['gameid']] = set()
    ids[args['gameid']].add((args['serverid'],args['type']))
    return 'Success'
#@app.route('/game/request')
@app.route('/game/exist')
def gameexist():
    if not is_all(request.args,['gameid','serverid','type']):
        return 'Missing arguments!',503
    #print(games, ids)
    #print((request.args['gameid'] in games.keys()), (request.args['serverid'] in ids[request.args['gameid']]), ids, games)
    success = (request.args['gameid'] in games.keys())
    if success:
        success =((request.args['serverid'],request.args['type']) in ids[request.args['gameid']])
    return ['no','yes'][success]
if __name__ == "__main__":
    threading.Thread(target=app.run,daemon=1).start()
    start_ssh_server()
