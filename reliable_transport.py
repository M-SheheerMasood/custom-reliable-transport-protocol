from queue import Queue, Empty #empty is for error handling
from typing import Tuple
from socket import socket
# added these
import util
import random

Address = Tuple[str, int]


class MessageSender:
    '''
    DO NOT EDIT ANYTHING IN THIS CLASS
    '''

    def __init__(self, sock: socket, receiver_addr: Address, msg_id: int):
        self.__sock: socket = sock
        self.__receiver_addr = receiver_addr
        self.__msg_id = msg_id

    def send(self, packet: str):
        self.__sock.sendto(
            (f"s:{str(self.__msg_id)}:{packet}").encode("utf-8"),
            self.__receiver_addr)


class ReliableMessageSender(MessageSender):
    '''
    This class reliably delivers a message to a receiver.
    You have to implement the send_message and on_packet_received methods.
    You can use self.send(packet) to send a packet to the receiver.
    You can add as many helper functions as you want.
    '''

    def __init__(self, sock: socket, receiver_addr: Address, msg_id: int,
                 window_size: int):
        MessageSender.__init__(self, sock, receiver_addr, msg_id)
        self.window_size = window_size
        self.ack_que = Queue()
        '''
        This is the constructor of the class where you can define any class attributes.
        window_size is the size of your message transport window (the number of in-flight packets during message transmission).
        Ignore other arguments; they are passed to the parent class.
        You should immediately return from this function and not block.
        '''

    def on_packet_received(self, packet: str):
        '''
        TO BE IMPLEMENTED BY STUDENTS

        This method is invoked whenever a packet is received from the receiver.
        Ideally, only ACK packets should be received here.
        You would have to use a way to communicate these packets to the send_message method.
        One way is to use a queue: you can enqueue packets to it in this method, and dequeue them in send_message.
        You can also use the timeout argument of a queue’s dequeue method to implement timeouts in this assignment.
        You should immediately return from this method and not block.
        '''
        # checking checksum
        if util.validate_checksum(packet):
            # getting type
            packet_type, num, _, _ = util.parse_packet(packet)
            # check for acknolodgement
            if packet_type == "ack":
                self.ack_que.put(int(num))

    def send_message(self, message: str):
        ''''
        TO BE IMPLEMENTED BY STUDENTS

        This method reliably sends the passed message to the receiver. 
        This method does not need to spawn a new thread and return immediately; it can block indefinitely until the message is completely received by the receiver. 
        You can send a packet to the receiver by calling self.send(...).

        Sender's logic:
        1) Break down the message into util.CHUNK_SIZE sized chunks.
        2) Choose a random sequence number to start the communication from.
        3) Reliably send a start packet. (i.e. wait for its ACK and resend the packet if the ACK is not received within util.TIME_OUT seconds.)
        4) Send out a window of data packets and wait for ACKs to slide the window appropriately.
        5) How to slide the window? Suppose that the current window starts at sequence number j. If you receive an ACK of sequence number k, such that k > j, send the subsequent k – j number of chunks. Note that the window now starts from sequence number j + (k – j).
        6) If you receive no ACKs for util.TIME_OUT seconds, resend all the packets in the current window.
        7) Once all the chunks have been reliably sent, reliably send an end packet.
        '''
        chunks = []
        idx = 0
        while idx < len(message):
            next_idx = idx + util.CHUNK_SIZE
            chunk = message[idx:next_idx]
            chunks.append(chunk)
            idx += util.CHUNK_SIZE
        total_chunks = len(chunks)
        seq = random.randint(1,1000)
        #starting the connection
        while True:
            packet = util.make_packet("start", seq)
            self.send(packet)
            try:
                ack_seq = self.ack_que.get(timeout=util.TIME_OUT)
                if ack_seq == seq + 1:
                    break
            except Empty:
                pass
        # the window mechanism
        base = seq + 1
        next_seq = base
        jump = seq + total_chunks + 1
        while base < jump:
            # sending data pckts
            while next_seq < base + self.window_size and next_seq < jump:
                chunk_idx = next_seq - (seq + 1)
                pkt = util.make_packet("data", next_seq, chunks[chunk_idx])
                self.send(pkt)
                next_seq += 1
            # acknoledgemnt stuff
            try:
                ack_seq = self.ack_que.get(timeout=util.TIME_OUT)
                if ack_seq > base:
                    base = ack_seq
            except Empty:
                next_seq = base
        # ending the connection
        end = jump
        while True:
            end_pkt = util.make_packet("end", end)
            self.send(end_pkt)
            try:
                ack_seq = self.ack_que.get(timeout=util.TIME_OUT)
                if ack_seq == end + 1:
                    break
            except Empty:
                pass

class MessageReceiver:
    '''
    DO NOT EDIT ANYTHING IN THIS CLASS
    '''

    def __init__(self, sock: socket, sender_addr: Address, msg_id: int,
                 completed_message_q: Queue):
        self.__sock: socket = sock
        self.__sender_addr = sender_addr
        self.__msg_id = msg_id
        self.__completed_message_q = completed_message_q

    def send(self, packet: str):
        self.__sock.sendto(
            (f"r:{str(self.__msg_id)}:{packet}").encode("utf-8"),
            self.__sender_addr)

    def on_message_completed(self, message: str):
        self.__completed_message_q.put(message)


class ReliableMessageReceiver(MessageReceiver):
    '''
    This class reliably receives a message from a sender. 
    You have to implement the on_packet_received method. 
    You can use self.send(packet) to send a packet back to the sender, and will have to call self.on_message_completed(message) when the complete message is received.
    You can add as many helper functions as you want.
    '''

    def __init__(self, sock: socket, sender_addr: Address, msg_id: int,
                 completed_message_q: Queue):
        MessageReceiver.__init__(self, sock, sender_addr, msg_id,
                                 completed_message_q)
        # trackers
        self.exp_seq = -1
        self.buffer = {}
        # flags
        self.is_started = False
        self.is_ended = False
        '''
        This is the constructor of the class where you can define any class attributes to maintain state.
        You should immediately return from this function and not block.
        '''

    def on_packet_received(self, packet: str):
        '''
        TO BE IMPLEMENTED BY STUDENTS

        This method is invoked whenever a packet is received from the sender.
        You have to inspect the packet and determine what to do.
        You should immediately return from this method and not block.
        You can either ignore the packet, or send a corresponding ACK packet back to the sender by calling self.send(packet).
        If you determine that the sender has completely sent the message, call self.on_message_completed(message) with the completed message as its argument.

        Receiver’s logic:
        1) When you receive a packet, validate its checksum and ignore it if it is corrupted.
        2) Inspect the packet_type and sequence number.
        3) If the packet type is "start", prepare to store incoming chunks of data in some data structure and send an ACK back to the sender with the received packet’s sequence number + 1.
        4) If the packet type is "data", store it in an appropriate data type (if it is not a duplicate packet you already have stored), and send a corresponding cumulative ACK. (ACK with the sequence number for which all previous packets have been received).
        5) If the packet type is "end", assemble all the stored chunks into a message, call self.on_message_received(message) with the completed message, and send an ACK with the received packet’s sequence number + 1.
        '''
        #safety check
        if not util.validate_checksum(packet):
            return
        # getting the info from the message
        packet_type, num, data, _ = util.parse_packet(packet)
        seqno = int(num)
        # for start packets
        if packet_type == "start":
            # checking for safety
            if not self.is_started:
                # starting
                self.exp_seq = seqno + 1
                self.is_started = True
            self.send(util.make_packet("ack", seqno + 1))
        # handle data packets
        # gotta make sure the connection was started yk
        elif packet_type == "data" and self.is_started:
            if seqno >= self.exp_seq:
                self.buffer[seqno] = data
                # buffering
                while self.exp_seq in self.buffer:
                    self.exp_seq += 1
            self.send(util.make_packet("ack", self.exp_seq))
        # for end packets
        elif packet_type == "end" and self.is_started:
            self.send(util.make_packet("ack", seqno + 1))
            # indeed it has ended
            #safety check again
            if not self.is_ended:
                self.is_ended = True
                sorted_seqs = sorted(self.buffer.keys())
                msg_parts = [self.buffer[s] for s in sorted_seqs]
                full_message = "".join(msg_parts)
                self.on_message_completed(full_message)
