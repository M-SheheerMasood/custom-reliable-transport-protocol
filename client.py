'''
This module defines the behaviour of a client in your Chat Application
'''
import sys
import getopt
import socket
import random
from threading import Thread
import os
import util
from reliable_socket import ReliableSocket
import time


class Client:
    '''
    This is the main Client Class. 
    '''

    def __init__(self, username, dest, port, window_size):
        self.server_addr = dest
        self.server_port = port
        self.dest, self.port = ('', random.randint(10000, 40000))
        self.reliable_sock = ReliableSocket(
            self.dest, self.port, int(window_size))
        self.name = username
        # This variable is used for inter-thread communication and to simultaneously close both the threads
        self.connected = True

    def start(self):

        # A join message is created, enclosed in a packet and then sent to the server to let it know that a new client came online
        message_to_send = util.make_message(
            msg_type="join", msg_format=1, message=self.name)
        self.reliable_sock.sendto(
            (self.server_addr, self.server_port), message_to_send)

        # This is the main loop that reads user input and acts accordingly.
        # It only goes into the loop as long as the bool "connected" is True and the client is online
        while self.connected:
            user_input = input("")
            # As input() function is blocking, there is a possibility that as the server sent some error message and the client has disconnected while the user was inputting his command. So, this is ensures that no user input is processed if the client has disconnected.
            if not self.connected:
                break

            index_of_first_space = user_input.find(" ")

            if user_input == "list":
                message_to_send = util.make_message(
                    msg_type="request_users_list", msg_format=2)

            # checks that the user input contains atleast something after the first space for error handling, otherwise it will give an incorrect userinput format error
            elif user_input[:index_of_first_space] == "msg" and len(user_input) >= index_of_first_space + 2:
                message_to_send = util.make_message(
                    msg_type="send_message", msg_format=4, message=user_input[index_of_first_space + 1:])
            # Closes the client application by changing the bool "connected" which will break the main loops of start and receive handler functions.
            elif user_input == "quit":
                self.connected = False
                print("quitting")
                message_to_send = util.make_message(
                    msg_type="disconnect", msg_format=1, message=self.name)
                time.sleep(1) # Ensure that all preceeding messages are received by the server
            # checks that the user input contains atleast something after the first space for error handling, otherwise it will give an incorrect userinput format error
            elif user_input[:index_of_first_space] == "file" and len(user_input) >= index_of_first_space + 2:
                self.forward_file(user_input)
                continue
            elif user_input == "help":
                self.help()
                continue
            else:  # Lets the user know that it has used an incorrect format
                print("incorrect userinput format")
                continue

            self.reliable_sock.sendto(
                (self.server_addr, self.server_port), message_to_send)

        time.sleep(1)  # Ensure all the messages are received by the server

    def receive_handler(self):

        # This is the main loop that receives messages from the server and acts accordingly.
        # It only goes into the loop as long as the bool "connected" is True and the client is online
        while self.connected:
            message, _ = self.reliable_sock.recvfrom()
            # print(f"Received           {message}")

            message_parts = message.split(" ")

            if message_parts[0] == "err_server_full":
                self.connected = False
                print("disconnected: server full")
            elif message_parts[0] == "err_username_unavailable":
                self.connected = False
                print("disconnected: username not available")
            elif message_parts[0] == "err_unknown_message":
                self.connected = False
                print("disconnected: server received an unknown command")
            elif message_parts[0] == "response_users_list":
                list_of_users = message_parts[2:]
                list_of_users.sort()
                print("list:", " ".join(list_of_users))
            elif message_parts[0] == "forward_message":
                print("msg:", message_parts[2]+":",
                      " ".join(message_parts[3:]))
            elif message_parts[0] == "forward_file":
                filename = message_parts[3]
                file = open(self.name + "_" + filename, "w")
                file.write(" ".join(message_parts[4:]))
                file.close()
                print("file:", message_parts[2]+":", filename)

    def help(self):
        # This function prints a list of all possible user inputs and their formats
        help_output = """This is a list of all possible user inputs and their formats.

		Message function format:
		msg <number_of_users> <username1> <username2> … <message>

		Available users function format:
		list

		File Sharing function format:
		file <number_of_users> <username1> <username2> … <file_name>

		Help function:
		help

		Quitting function:
		quit
		"""
        print(help_output)

    # This function makes a message which includes the content of a specified text file and the intended recipients users of the file to send to the server
    def forward_file(self, user_input):
        index_of_first_space = user_input.find(" ")
        user_input_parts = user_input.split(" ")
        # This is the specified filename to be opened, read and then sent
        filename = user_input_parts[-1]

        # Error handling in case the user did not follow the format and specified a non-integer value
        try:
            num_of_users = int(user_input_parts[1])
        except:
            print("Number of users specified is not an integer.")
            return
        # Error handling if the user does not mention the names of all recepients-users
        if len(user_input_parts) != num_of_users + 3:
            print("Number of users specified are not mentioned")
            return
        # To avoid crashing of application if the specified file does not exist and cannot be opened
        try:
            file = open(filename, "r")
            file_content = file.read()
            file.close()
            message_to_send = util.make_message(
                msg_type="send_file", msg_format=4, message=user_input[index_of_first_space + 1:] + " " + file_content)
            # packet_to_send = util.make_packet(msg=message_to_send)
            self.reliable_sock.sendto(
                (self.server_addr, self.server_port), message_to_send)
        except:
            print("The specified file does not exist.")


# Do not change this part of code
if __name__ == "__main__":
    def helper():
        '''
        This function is just for the sake of our Client module completion
        '''
        print("Client")
        print("-u username | --user=username The username of Client")
        print("-p PORT | --port=PORT The server port, defaults to 15000")
        print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
        print("-w WINDOW_SIZE | --window=WINDOW_SIZE The window_size, defaults to 3")
        print("-h | --help Print this help")
    try:
        OPTS, ARGS = getopt.getopt(sys.argv[1:],
                                   "u:p:a:w", ["user=", "port=", "address=", "window="])
    except getopt.error:
        helper()
        exit(1)

    PORT = 15000
    DEST = "127.0.0.1"
    USER_NAME = None
    WINDOW_SIZE = 3
    for o, a in OPTS:
        if o in ("-u", "--user="):
            USER_NAME = a
        elif o in ("-p", "--port="):
            PORT = int(a)
        elif o in ("-a", "--address="):
            DEST = a
        elif o in ("-w", "--window="):
            WINDOW_SIZE = a

    if USER_NAME is None:
        print("Missing Username.")
        helper()
        exit(1)

    S = Client(USER_NAME, DEST, PORT, WINDOW_SIZE)
    try:
        # Start receiving Messages
        T = Thread(target=S.receive_handler)
        T.daemon = True
        T.start()
        # Start Client
        S.start()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
