import socket
from typing import Dict, Tuple
from queue import Queue
from threading import Thread
from random import randint
from reliable_transport import ReliableMessageSender, ReliableMessageReceiver

Address = Tuple[str, int]
MsgID = int


class ReliableSocket:
    """
    This is a socket that reliably transports messages.

    Description:
        This socket uses a UDP socket and builds reliability on top of it. For
        each message transport, this class maintains a ReliableMessageSender and
        a ReliableMessageReceiver that implement the reliable transport logic.
        ReliableMessageSender and ReliableMessageReceiver are implemented in 
        reliable_transmission.py

    APIs:
        ReliableSocket.send(receiver_addr, message)
            Sends a message to an address
        ReliableSocket.recvfrom()
            Receives a message sent to the socket
    """
    def __init__(self, dest, port, window_size, bufsize=4096):
        self.__dest = dest
        self.__port = port
        self.__window_size = window_size
        self.__bufsize = bufsize
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__sock.settimeout(None)
        self.__sock.bind((self.__dest, self.__port))

        self.__senders: Dict[Tuple[Address, MsgID], ReliableMessageSender] = {}
        self.__receivers: Dict[Tuple[Address, MsgID], ReliableMessageReceiver] = {}

        self.__received_messages = Queue()

        # start the thread for receiving packets
        Thread(target=self.__receive_handler, args=(), daemon=True).start()

    def recvfrom(self,
                 block: int = True,
                 timeout: int = None) -> Tuple[str, Address]:
        """
        Returns a reliably received message on the socket.

        Args:
            block (bool, optional):
                Notifies if this function should block to wait for a value.
                Defaults to True.
            timeout (int, optional):
                The amount of time in seconds the function waits for a value.
                Defaults to None.

        Returns:
            Tuple[str, Address]:
                A tuple of
                    (i)  the received message, and
                    (ii) the address from where the message is received from

        Note:
            If optional args block is true and timeout is None (the default), it
            blocks if necessary until a message is received. If timeout is a positive
            number, it blocks at most timeout seconds and raises the queue.Empty
            exception if no message is received within that time. Otherwise (block is
            false), return a received message if one is immediately available, else
            raise the queue.Empty exception (timeout is ignored in that case).
        """

        return self.__received_messages.get(block=block, timeout=timeout)

    def sendto(self, receiver_addr: Address, message: str):
        """
        Send message to an address reliably.

        Args:
            receiver_addr (Address): Address of destination
            message (str): Message to send to the destination

        Note:
            This function call is syncronous. It blocks until the message is
            reliably transported to the destination (which can take arbitrary
            time).
        """

        self.__send_message_reliably(receiver_addr, message)

    @staticmethod
    def __is_from_a_receiver(sender_type: str) -> bool:
        return sender_type == "r"

    @staticmethod
    def __parse_raw_packet(raw_packet: str) -> Tuple[str, int, str]:
        raw_packet = raw_packet.split(':')
        return raw_packet[0], int(raw_packet[1]), ':'.join(raw_packet[2:])

    def __receive_handler(self):
        """
        Receives packets on the socket and redirects them to the their particular
        reliable message sender/receivers.
        """

        while True:

            # recieve a packet for a message from a client
            byte_packet, addr = self.__sock.recvfrom(self.__bufsize)
            raw_packet = byte_packet.decode("utf-8")
            sender_type, msg_id, packet = self.__parse_raw_packet(raw_packet)

            if self.__is_from_a_receiver(sender_type):
                # this belongs to a sender
                self.__send_to_a_sender(addr, msg_id, packet)
            else:
                # this belongs to a receiver
                self.__send_to_a_receiver(addr, msg_id, packet)

    def __send_to_a_sender(self, addr, msg_id: int, ack_packet: str):
        """
        Redirects received ack packet to the corresponding message sender
        """

        if (addr, msg_id) in self.__senders:
            sender: ReliableMessageSender = self.__senders[(addr, msg_id)]
            sender.on_packet_received(ack_packet)
        else:
            print("Warning: no sender identified for", (addr, msg_id))

    def __send_to_a_receiver(self, addr, msg_id: int, packet: str):
        """
        Redirects received packet to the corresponding message receiver.
        If no such receiver is found, a new message receiver is initialized.
        """

        if not (addr, msg_id) in self.__receivers:
            # this is a new transmission, set up new receiver
            self.__setup_new_receiver(addr, msg_id)

        receiver: ReliableMessageReceiver = self.__receivers[(addr, msg_id)]
        receiver.on_packet_received(packet)

    def __setup_new_receiver(self, new_addr, msg_id: int):
        """
        Initializes new message receiver.
        Initialization involves making a queue in which the message receiver can enqueue the message
        once it is completely (and reliably) received. ReliableSocket needs to start a thread that
        dequeues this queue to get the completed message.
        """

        completed_msg_q: Queue = Queue()
        self.__receivers[(new_addr, msg_id)] = ReliableMessageReceiver(
            self.__sock, new_addr, msg_id, completed_msg_q)

        Thread(target=self.__process_completed_message,
               args=(new_addr, completed_msg_q),
               daemon=True).start()

    def __process_completed_message(self, sender_addr, completed_msg_q: Queue):
        """
        Waits for a completed message to be received by a reliable message receiver
        and then processes it
        """

        # blocks here for message
        received_msg = completed_msg_q.get()

        # act on completed message
        self.__received_messages.put((received_msg, sender_addr))

        # # delete this message receiver (as its of no use now, message has been completely received)
        # del self.__receivers[(sender_addr, msg_id)]

    def __get_unique_msg_id(self, recvr_addr):
        msg_id = randint(50000, 99999)
        while (recvr_addr, msg_id) in self.__senders:
            msg_id = randint(50000, 99999)
        return msg_id

    def __send_message_reliably(self, recvr_addr, message):
        """
        Sends a message reliably.
        - Initializes a reliable message sender instance that can reliably send this message.
        - Stores this in a dictionary so that we can send acks to it from our receive_handler.
        - Notiifies the reliable message sender to start sending.
        - Deletes the reliable message sender instance as the message has been completey sent. 
        """

        msg_id = self.__get_unique_msg_id(recvr_addr)

        sender = ReliableMessageSender(self.__sock, recvr_addr, msg_id,
                                       self.__window_size)

        self.__senders[(recvr_addr, msg_id)] = sender

        sender.send_message(message)

        # del self.__senders[(recvr_addr, msg_id)]