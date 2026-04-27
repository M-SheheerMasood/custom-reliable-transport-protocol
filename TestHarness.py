#!/usr/bin/python
from dataclasses import dataclass, field
import os
import socket
import subprocess
import time
import random
import util
import argparse
from tests import BasicTest, BasicFunctionalityTest, PacketLossTest, DuplicatePacketsTest, OutOfOrderPacketsTest, WindowSizeTest
import signal
import concurrent.futures
import threading
import ast


ALLOWED_IMPORTS = [
    "queue", "typing", "socket",
    "util", "collections", "time", "random", "dataclasses"
]

total_marks = 0
lock = threading.Lock()


def analyze_code(file_path: str) -> bool:
    """
    Analyze the student's code for restricted imports or functions.
    Deduct marks for violations.
    """
    with open(file_path, "r") as f:
        code = f.read()

    # Mapping of aliases (e.g., "o" -> "os") cuz students can do weird import os as o
    alias_map = {}

    try:
        # Parse the code into an AST (Abstract Syntax Tree) best thing ever
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    alias_map[alias.asname or alias.name] = alias.name
                    if alias.name not in ALLOWED_IMPORTS:
                        print(f"\033[91m[RESTRICTED IMPORT]\033[0m {alias.name} found!")
                        return True

            elif isinstance(node, ast.ImportFrom):
                # we will flag all "from os ..." imports
                if node.module not in ALLOWED_IMPORTS:
                    print(
                        f"\033[91m[RESTRICTED IMPORT]\033[0m from {node.module} import ... is not allowed!")
                    return True
    except Exception as e:
        print(f"Error analyzing code: {e}")
        return False

    return False


def delete_with_rm_rf():
    """Delete outputs from previous runs using rm -rf."""
    patterns = ["./client_*", "./test_*", "./*_test_*", "./server_out*"]
    try:
        for pattern in patterns:
            subprocess.run(f"rm -rf {pattern}", shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to delete files matching pattern: {e}")


@dataclass
class Forwarder:
    sender_path: str
    receiver_path: str
    port: int

    # Default attributes
    tests: dict = field(default_factory=dict)  # test object => testName
    current_test: object = None
    out_queue: list = field(default_factory=list)
    in_queue: list = field(default_factory=list)
    tick_interval: float = 0.001  # 1ms
    last_tick: float = field(default_factory=time.time)
    timeout: float = 60.0  # seconds

    # Network-related attributes
    cli_ports: dict = field(default_factory=dict)
    middle: dict = field(default_factory=dict)  # Man in the Middle Sockets
    sender_addr: dict = field(default_factory=dict)
    senders: dict = field(default_factory=dict)
    receiver_port: int = field(init=False)
    receiver_addr: tuple = None

    def __post_init__(self):
        # Validate file paths
        if not os.path.exists(self.sender_path):
            raise ValueError(f"Could not find sender path: {self.sender_path}")
        if not os.path.exists(self.receiver_path):
            raise ValueError(f"Could not find receiver path: {self.receiver_path}")

        # Initialize derived attributes
        self.receiver_port = self.port + 1

    def _tick(self):
        self.current_test.handle_tick(self.tick_interval)
        for p, user in self.out_queue:
            self._send(p, user)
        self.out_queue = []

    def _send(self, packet, user):
        packet.update_packet(seqno=packet.seqno, update_checksum=False)
        self.middle[user].sendto(packet.full_packet, packet.address)

    def register_test(self, testcase, testName):
        assert isinstance(testcase, BasicTest.BasicTest)
        self.tests[testcase] = testName

    def execute_tests(self):
        try:
            for t in self.tests:
                self.current_test = t
                self.current_test.set_state()
                self.middle = {}
                i = 0
                for client in sorted(self.current_test.client_stdin.keys()):
                    self.middle[client] = socket.socket(
                        socket.AF_INET, socket.SOCK_DGRAM)
                    # make this a very short timeout
                    self.middle[client].settimeout(0.01)
                    self.middle[client].bind(('', self.port - i))
                    self.cli_ports[client] = self.port - i
                    i += 1
                print(("Testing %s" % self.tests[t]))
                self.start()
        except Exception as e:
            print(f"\033[91mTest {self.tests[t]} Failed due to an exception!\033[0m {e}")

    def handle_receive(self, message, address, user):
        if address[1] == self.receiver_port and user in self.sender_addr:
            p = Packet(message, self.sender_addr[user])
        else:
            if user not in self.sender_addr:
                self.sender_addr[user] = address
            p = Packet(message, self.receiver_addr)

        self.in_queue.append((p, user))
        self.current_test.handle_packet()

    def start(self):
        self.sender_addr = {}
        self.receiver_addr = ('127.0.0.1', self.receiver_port)
        self.recv_outfile = f"server_out_{self.tests[self.current_test]}"

        recv_out = open(self.recv_outfile, "w")
        receiver = subprocess.Popen(["python3", self.receiver_path,
                                     "-p", str(self.receiver_port)], stdout=recv_out)
        time.sleep(0.2)  # make sure the receiver is started first
        self.senders = {}
        sender_out = {}
        for i in list(self.current_test.client_stdin.keys()):
            sender_out[i] = open("client_"+i, "w")
            self.senders[i] = subprocess.Popen(["python3", self.sender_path,
                                                "-p", str(self.cli_ports[i]),
                                                "-u", i], stdin=subprocess.PIPE, stdout=sender_out[i])
        try:
            start_time = time.time()
            self.last_tick = time.time()
            while None in [self.senders[s].poll() for s in self.senders]:
                for i in list(self.middle.keys()):
                    try:
                        message, address = self.middle[i].recvfrom(4096)
                        self.handle_receive(message, address, i)
                    except socket.timeout:
                        pass
                    if time.time() - self.last_tick > self.tick_interval:
                        self.last_tick = time.time()
                        self._tick()
                    if time.time() - start_time > self.timeout:
                        raise Exception("Test timed out!")
            self._tick()
        except (KeyboardInterrupt, SystemExit):
            exit()
        finally:
            for sender in self.senders:
                if self.senders[sender].poll() is None:
                    self.senders[sender].send_signal(signal.SIGINT)
                sender_out[sender].close()
            receiver.send_signal(signal.SIGINT)
            recv_out.flush()
            recv_out.close()

        if not os.path.exists(self.recv_outfile):
            raise RuntimeError("No data received by receiver!")
        time.sleep(1)
        rigorous_passed = False
        try:
            if self.tests[self.current_test] == "WindowSize":
                result, rigorous_passed = self.current_test.result() 
            else:
                result = self.current_test.result()
            if result:
                global total_marks
                with lock:
                    if self.tests[self.current_test] == "WindowSize":
                        total_marks += 5
                        if rigorous_passed:
                            total_marks += 5
                    else:
                        total_marks += 5
        except Exception as e:
            print(f"\033[91mTest {self.tests[self.current_test]} Failed due to an exception!\033[0m {e}")

    @staticmethod
    def tests_to_run(forwarder, selected_tests, verbose):
        """Runs the selected tests or all tests if none specified."""
        test_map = {
            "BasicFunctionality": BasicFunctionalityTest.BasicFunctionalityTest,
            "PacketLoss": PacketLossTest.PacketLossTest,
            "DuplicatePackets": DuplicatePacketsTest.DuplicatePacketsTest,
            "OutOfOrderPackets": OutOfOrderPacketsTest.OutOfOrderPacketsTest,
            "WindowSize": WindowSizeTest.WindowSizeTest
        }

        if selected_tests:
            for test_name in selected_tests:
                if test_name in test_map:
                    test_map[test_name](forwarder, verbose, test_name)
                else:
                    print(f"Unknown test: {test_name}")
        else:
            for test_name, test_class in test_map.items():
                test_class(forwarder, verbose, test_name)


class Packet(object):
    def __init__(self, packet, address):
        self.full_packet = packet
        self.address = address
        self.seqno = 0
        try:
            pieces = packet.split('|')
            self.msg_type, self.seqno = pieces[0:2]
            self.checksum = pieces[-1]
            self.data = '|'.join(pieces[2:-1])
            self.seqno = int(self.seqno)
            assert (self.msg_type in ["start", "data", "ack", "end"])
            int(self.checksum)
            self.bogon = False
        except Exception as e:
            self.bogon = True

    def update_packet(self, msg_type=None, seqno=None, data=None, full_packet=None, update_checksum=True):
        if not self.bogon:
            if msg_type is None:
                msg_type = self.msg_type
            if seqno is None:
                seqno = self.seqno
            if data is None:
                data = self.data

            if msg_type == "ack":
                body = "%s|%d|" % (msg_type, seqno)
                checksum_body = "%s|%d|" % (msg_type, seqno)
            else:
                body = "%s|%d|%s|" % (msg_type, seqno, data)
                checksum_body = "%s|%d|%s|" % (msg_type, seqno, data)
            if update_checksum:
                checksum = util.generate_checksum(checksum_body)
            else:
                checksum = self.checksum

            self.msg_type = msg_type
            self.seqno = seqno
            self.data = data
            self.checksum = checksum
            if full_packet:
                self.full_packet = full_packet
            else:
                self.full_packet = "%s%s" % (body, checksum)

    def __repr__(self):
        return "%s|%s|...|%s" % (self.msg_type, self.seqno, self.checksum)


if __name__ == "__main__":
    delete_with_rm_rf()
    
    
    if analyze_code("reliable_transport.py"):
        print("Code contains restricted imports or functions. Skipping tests.")
        print("Final Score: 0/35")
        exit(0)

    def usage():
        print("Tests for Reliable Tranport")
        print("-p PORT | --port PORT Base port value (default: 33123)")
        print("-c CLIENT | --client CLIENT The path to Client implementation (default: client.py)")
        print("-s SERVER | --server SERVER The path to the Server implementation (default: server.py)")
        print("-h | --help Print this usage message")

    parser = argparse.ArgumentParser(
        description="Tests for Chat Application", add_help=False)
    parser.add_argument(
        "-p", "--port",
        type=str,
        default=random.randint(1000, 65500),
        help="Base port value. If not provided, a random port will be used."
    )
    parser.add_argument(
        "-c", "--client",
        type=str,
        default="client.py",
        help="The path to Client implementation (default: client.py)"
    )
    parser.add_argument(
        "-s", "--server",
        type=str,
        default="server.py",
        help="The path to the Server implementation (default: server.py)"
    )
    parser.add_argument(
        "-t", "--tests",
        type=str,
        nargs="*",
        default=None,
        help="The tests to run. If not provided, all tests will be run."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose output"
    )

    parser.add_argument(
        "-h", "--help",
        action="store_true",
        help="Print this usage message"
    )

    args = parser.parse_args()

    if args.help:
        usage()
        exit(0)

    def run_single_test(test_name, client, server, verbose):
        """
        Creates a brand-new Forwarder on a random port, runs exactly ONE test case,
        and returns whatever the global total_marks was incremented by.
        """

        local_port = random.randint(1000, 65500)
        f = Forwarder(client, server, local_port)
        Forwarder.tests_to_run(f, [test_name], verbose=verbose)
        f.execute_tests()
        return total_marks

    if not args.tests:
        all_tests = [
            "BasicFunctionality",
            "PacketLoss",
            "DuplicatePackets",
            "OutOfOrderPackets",
            "WindowSize"
        ]
        selected_tests = all_tests
    else:
        selected_tests = args.tests

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_test = {}  # mapping of futures(tasks) to test names
        for tname in selected_tests:
            # schedule a single test in its own thread
            future = executor.submit(run_single_test, tname,
                                     args.client, args.server, args.verbose)
            future_to_test[future] = tname

        # whichever task finishes first, it will log the results
        for fut in concurrent.futures.as_completed(future_to_test):
            test = future_to_test[fut]
            try:
                fut.result()
            except Exception as e:
                print(f"\033[91mTest {test}' failed due to an exception!\033[0m {e}")

    if not args.tests:
        print(f"Final Score: {total_marks}/30")

        if total_marks == 30:
            print("\n🎉 Congratulations! You aced it! 🎉")
        elif total_marks == 0:
            print("\n😢 Oh no! You didn't pass any tests! There there 😢")
        else:
            print("\n✨ Good job! Keep aiming for perfection! ✨")
