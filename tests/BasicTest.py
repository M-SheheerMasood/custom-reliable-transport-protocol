import hashlib
import os
import time
import util


class BasicTest(object):
    def __init__(self, forwarder, verbose=False, test_name="Basic"):
        self.forwarder = forwarder
        self.forwarder.register_test(self, test_name)
        self.num_of_clients = 0
        self.client_stdin = {}
        self.input = []
        self.input_to_check = []
        self.last_time = time.time()
        self.time_interval = 0.5
        self.packets_processed = {"ack": 0, "data": 0, "start": 0, "end": 0}
        self.packet_length_exceeded_limit = 0
        self.num_of_acks = 30
        self.verbose = verbose
        self.test_name = test_name

    def set_state(self):
        pass

    def handle_packet(self):
        for p, user in self.forwarder.in_queue:
            if len(p.full_packet) > 1500:
                self.packet_length_exceeded_limit += 1
                continue
            # print(f"Received packet from {user}: {p.full_packet}")
            msg_type, a, b, c = util.parse_packet(p.full_packet.decode()[8:])
            self.packets_processed[msg_type] += 1
            self.forwarder.out_queue.append((p, user))
        self.forwarder.in_queue = []

    def handle_tick(self, tick_interval):
        if self.last_time == None:
            return
        elif len(self.input) > 0:
            if time.time() - self.last_time > self.time_interval:
                client, inpt = self.input[0]
                self.input_to_check.append((client, inpt))
                self.input = self.input[1:]
                self.forwarder.senders[client].stdin.write(inpt.encode())
                self.forwarder.senders[client].stdin.flush()
                self.last_time = time.time()

        elif time.time() - self.last_time > self.time_interval*4:
            for client in self.forwarder.senders.keys():
                self.forwarder.senders[client].stdin.write("quit\n".encode())
                self.forwarder.senders[client].stdin.flush()
            self.last_time = None
        return

    def result(self):
        print(f"Test {self.test_name} Passed!")
        return True

    def result_basic(self):
        # Check if Output File Exists
        if not os.path.exists(f"server_out_{self.test_name}"):
            raise ValueError("No such file server_out")

        for client in self.client_stdin.keys():
            if not os.path.exists("client_"+client):
                raise ValueError("No such file %s" % "client_" + client)

        # Check Packet Length
        if self.packet_length_exceeded_limit > 0:
            print(
                f"\033[91mTest {self.test_name} Failed\033[0m: Packet length exceeded 1500 bytes.")
            return False

        # Check ACK packets
        if self.packets_processed['ack'] < self.num_of_acks:
            print(
                f"\033[91mTest {self.test_name} Failed\033[0m: Some packets were not acknowledged.")
            return False

        # Generating Expected Output
        server_out = []
        clients_out = {}
        num_data_pkts = 0
        files = {"test_file1": [], "test_file2": []}

        for client in self.client_stdin.keys():
            server_out.append("join: %s" % client)
            clients_out[client] = ["quitting"]
            server_out.append('disconnected: %s' % client)
            num_data_pkts += 2

        for inp in self.input_to_check:
            client, message = inp
            msg = message.split()
            if msg[0] == "list":
                server_out.append("request_users_list: %s" % client)
                clients_out[client].append("list: %s" % " ".join(
                    sorted(self.client_stdin.keys())))
                num_data_pkts += 2
            elif msg[0] == "msg":
                server_out.append("msg: %s" % client)
                num_data_pkts += 1
                for i in range(int(msg[1])):
                    if msg[i + 2] not in clients_out:
                        server_out.append(
                            "msg: %s to non-existent user %s" % (client, msg[i+2]))
                    else:
                        clients_out[msg[i + 2]].append("msg: %s: %s" %
                                                       (client, " ".join(msg[2 + int(msg[1]):])))
                        num_data_pkts += 1
            elif msg[0] == "file":
                server_out.append("file: %s" % client)
                num_data_pkts += 1
                for i in range(int(msg[1])):
                    if msg[i + 2] not in clients_out:
                        server_out.append(
                            "file: %s to non-existent user %s" % (client, msg[i+2]))
                    else:
                        clients_out[msg[i + 2]].append("file: %s: %s" %
                                                       (client, msg[2 + int(msg[1])]))
                        files[msg[2+int(msg[1])]].append("%s_%s" %
                                                         (msg[i+2], msg[2+int(msg[1])]))
                        num_data_pkts += 1

        for client, expected_output in clients_out.items():
            with open(f"client_{client}") as f:
                user_output = f.read().split("\n")
                user_output = [line for line in user_output if line.strip(" \n") != ""]
                
                               
                missing_lines = list(set(user_output).symmetric_difference(set(expected_output)))

                if self.verbose:
                    self.show_verbose_output(
                        expected_output, user_output, f"Client {client}")
                if len(user_output) != len(expected_output):
                    print(
                        f"\033[91mTest {self.test_name} Failed\033[0m: Client {client} output is not the same length. Expected {len(expected_output)} got {len(user_output)}")
                    return False
                if missing_lines:
                    print(
                        f"\033[91mTest {self.test_name} Failed\033[0m: Client {client} output is incorrect.")
                    print("\nDifference:")
                    for line in missing_lines:
                        print(f"  - {line}")
                    return False

        with open(f"server_out_{self.test_name}") as f:
            user_output = f.read().split("\n")
            user_output = [line for line in user_output if line.strip(" \n") != ""]
            
            missing_lines = list(set(user_output).symmetric_difference(set(server_out)))

            if self.verbose:
                self.show_verbose_output(server_out, user_output, "Server")
            if len(user_output) != len(server_out):
                print(
                    f"\033[91mTest {self.test_name} Failed\033[0m: Server output is not the same length. Expected {len(server_out)} got {len(user_output)}")
                return False
            if missing_lines:
                print(
                    f"\033[91mTest {self.test_name} Failed\033[0m: Server output is incorrect.")
                print("\nDifference:")
                for line in missing_lines:
                    print(f"  - {line}")
                return False

        # Checking Files
        for filename in files:
            for each_file in files[filename]:
                if not self.files_are_the_same(each_file, filename):
                    print(
                        f"Test {self.test_name} Failed: File is corrupted/not found")
                    return False

        for filename in files:
            for each_file in files[filename]:
                if not self.files_are_the_same(each_file, filename):
                    print(
                        f"\033[91mTest {self.test_name} Failed\033[0m: File is corrupted or not found.")
                    return False

        # Check end packets
        if self.packets_processed["end"] < num_data_pkts:
            print(
                f"\033[91mTest {self.test_name} Failed\033[0m: Connections were not terminated by end packet.")
            return False

        # Check start packets
        if self.packets_processed["start"] < num_data_pkts:
            print(
                f"\033[91mTest {self.test_name} Failed\033[0m: Connections were not started by start packet.")
            return False

        print(f"\033[92mTest {self.test_name} Passed!\033[0m")
        return True

    def show_verbose_output(self, expected, actual, context, max_line_length=100):
        """Display detailed side-by-side comparison of outputs."""
        print(f"\n\033[94mVerbose Output: {context} Comparison\033[0m")

        def format_line(line):
            return line if len(line) <= max_line_length else "[LINE TOO BIG]"

        formatted_expected = [format_line(line) for line in expected]
        formatted_actual = [format_line(line) for line in actual]

        max_expected_len = max(
            len(line) for line in formatted_expected) if formatted_expected else 0
        max_actual_len = max(len(line)
                             for line in formatted_actual) if formatted_actual else 0

        row_format = f"{{:<{max_expected_len + 2}}} | {{:<{max_actual_len + 2}}}"
        header = row_format.format("Expected Output", "Actual Output")
        separator = "-" * len(header)

        print(header)
        print(separator)

        max_lines = max(len(formatted_expected), len(formatted_actual))
        for i in range(max_lines):
            expected_line = formatted_expected[i] if i < len(
                formatted_expected) else ""
            actual_line = formatted_actual[i] if i < len(
                formatted_actual) else ""
            print(row_format.format(expected_line, actual_line))

    def files_are_the_same(self, file1, file2):
        return BasicTest.md5sum(file1) == BasicTest.md5sum(file2)

    @staticmethod
    def md5sum(filename, block_size=2**20):
        f = open(filename, "rb")
        md5 = hashlib.md5()
        while True:
            data = f.read(block_size)
            if not data:
                break
            md5.update(data)
        f.close()
        return md5.digest()
