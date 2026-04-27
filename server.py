'''
This module defines the behaviour of server in your Chat Application
'''
import sys
import getopt
import socket
from threading import Thread
import util
from reliable_socket import ReliableSocket


class Server:
    '''
    This is the main Server Class.
    '''

    def __init__(self, dest: str, port: int, window: str):
        self.server_addr = dest
        self.server_port = port
        self.reliable_sock = ReliableSocket(dest, port, int(window))
        self.clients = list()

    def start(self):
        # This is the main loop of the server that runs infinitely and receives messages from the clients and responds accordingly.
        while True:
            message, address = self.reliable_sock.recvfrom()
            # print(f"got {message} from {address}")
            message_parts = message.split(" ")

            if message_parts[0] == "join":
                self.join(message_parts, address)
            elif message_parts[0] == "request_users_list":
                self.request_users_list(address)
            elif message_parts[0] == "send_message":
                self.send_message(message_parts, address)
            elif message_parts[0] == "disconnect":
                self.disconnect(message_parts, address)
            elif message_parts[0] == "send_file":
                self.send_file(message_parts, address)

    def send_file(self, message_parts, address):
        # Extracts the username from the list of clients given the address of the client
        username = str()
        for client in self.clients:
            if address == client["address"]:
                username = client["username"]

        # Error handling in case the client did not follow the format and specified a non-integer value
        # Sends a err_unknown_message back to the client and the client disconnects
        try:
            num_of_users = int(message_parts[1])
        except:
            message_to_send = util.make_message(
                msg_type="err_unknown_message", msg_format=2)
            self.reliable_sock.sendto(address, message_to_send)
            print("disconnected:", username, "sent unknown command")
            return

        # Error handling if the user does not mention the names of all recepients-users
        # Sends a err_unknown_message back to the client and the client disconnects
        if len(message_parts) < num_of_users + 4:
            message_to_send = util.make_message(
                msg_type="err_unknown_message", msg_format=2)
            self.reliable_sock.sendto(address, message_to_send)
            print("disconnected:", username, "sent unknown command")
            return

        # Makes a message with the file to be forwarded to the specified clients
        message_to_send = util.make_message(msg_type="forward_file", msg_format=4,
                                            message="1 " + username + " " + " ".join(message_parts[1 + num_of_users + 1:]))
        print("file:", username)

        # Maintains a list of usernames of users that have already received the file to ensure that each user gets the file at most once
        sent_to_clients = list()
        for i in range(0, num_of_users):
            # To check whether a particular user was online and sent the file
            sent = False
            for client in self.clients:
                if message_parts[2+i] == client["username"] and client["username"] not in sent_to_clients:
                    self.reliable_sock.sendto(
                        client["address"], message_to_send)
                    sent = True
                    sent_to_clients.append(client["username"])
            # In case, a specified user is not sent the file
            if not sent and message_parts[2+i] not in sent_to_clients:
                print("file:", username, "to non-existent user",
                      message_parts[2+i])

    def disconnect(self, message_parts, address):
        # Extracts the username from the message
        username = message_parts[1]
        # Make a dictionary of client to remove later from the list of client
        client = {"username": username, "address": address}

        # Error handling in case the client is already removed and the server does not crash
        try:
            self.clients.remove(client)
            print("disconnected:", username)
        except:
            # print(username, "already disconnected")
            pass

    def send_message(self, message_parts, address):
        # Extracts the username from the list of clients given the address of the client
        username = str()
        for client in self.clients:
            if address == client["address"]:
                username = client["username"]

        # Error handling in case the client did not follow the format and specified a non-integer value
        # Sends a err_unknown_message back to the client and the client disconnects
        try:
            num_of_users = int(message_parts[1])
        except:
            message_to_send = util.make_message(
                msg_type="err_unknown_message", msg_format=2)
            self.reliable_sock.sendto(address, message_to_send)
            print("disconnected:", username, "sent unknown command")
            return

        # Error handling if the user does not mention the names of all recepients-users
        # Sends a err_unknown_message back to the client and the client disconnects
        if len(message_parts) < num_of_users + 3:
            message_to_send = util.make_message(
                msg_type="err_unknown_message", msg_format=2)
            self.reliable_sock.sendto(address, message_to_send)
            print("disconnected:", username, "sent unknown command")
            return

        # Makes a message with the message to be forwarded to the specified clients
        message_to_send = util.make_message(msg_type="forward_message", msg_format=4,
                                            message="1 " + username + " " + " ".join(message_parts[1 + num_of_users + 1:]))
        print("msg:", username)

        # Maintains a list of usernames of users that have already received the message to ensure that each user gets the message at most once
        sent_to_clients = list()
        for i in range(0, num_of_users):
            # To check whether a particular user was online and sent the message
            sent = False
            for client in self.clients:
                if message_parts[2+i] == client["username"] and client["username"] not in sent_to_clients:
                    self.reliable_sock.sendto(
                        client["address"], message_to_send)
                    sent = True
                    sent_to_clients.append(client["username"])
            # In case, a specified user is not sent the message
            if not sent and message_parts[2+i] not in sent_to_clients:
                print("msg:", username, "to non-existent user",
                      message_parts[2+i])

    def request_users_list(self, address):
        # Extracts the username from the list of clients given the address of the client
        username = str()
        for client in self.clients:
            if address == client["address"]:
                username = client["username"]

        # Constructs a string of online usernames from the client list
        list_of_users = str(len(self.clients))
        for client in self.clients:
            list_of_users = list_of_users + " " + client["username"]

        # Makes the packet containing the list of users and sends it to the client who requested it
        message_to_send = util.make_message(
            msg_type="response_users_list", msg_format=3, message=list_of_users)
        self.reliable_sock.sendto(address, message_to_send)
        print("request_users_list:", username)

    def join(self, message_parts, address):
        # Extracts the username from the message received
        username = message_parts[1]
        # Makes a dictionary of client to add later to the list of clients
        client = {"username": username, "address": address}

        # Send a err_server_full message to the client if server is full
        if len(self.clients) >= util.MAX_NUM_CLIENTS:
            print("disconnected: server full")
            message_to_send = util.make_message(
                msg_type="err_server_full", msg_format=2)
            self.reliable_sock.sendto(address, message_to_send)
        # Sends a err_username_unavailable to the client if the username is already taken
        elif client in self.clients:
            print("disconnected: username not available")
            message_to_send = util.make_message(
                msg_type="err_username_unavailable", msg_format=2)
            self.reliable_sock.sendto(address, message_to_send)
        # Adds the client to the list of clients
        else:
            self.clients.append(client)
            print("join:", username)

# Do not change this part of code


if __name__ == "__main__":
    def helper():
        '''
        This function is just for the sake of our module completion
        '''
        print("Server")
        print("-p PORT | --port=PORT The server port, defaults to 15000")
        print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
        print("-w WINDOW | --window=WINDOW The window size, default is 3")
        print("-h | --help Print this help")

    try:
        OPTS, ARGS = getopt.getopt(sys.argv[1:],
                                   "p:a:w", ["port=", "address=", "window="])
    except getopt.GetoptError:
        helper()
        exit()

    PORT = 15000
    DEST = "127.0.0.1"
    WINDOW = 3

    for o, a in OPTS:
        if o in ("-p", "--port="):
            PORT = int(a)
        elif o in ("-a", "--address="):
            DEST = a
        elif o in ("-w", "--window="):
            WINDOW = a

    SERVER = Server(DEST, PORT, WINDOW)
    try:
        SERVER.start()
    except (KeyboardInterrupt, SystemExit):
        # for i in SERVER.clients:
        #     print("disconnected:", i["username"])
        exit()
