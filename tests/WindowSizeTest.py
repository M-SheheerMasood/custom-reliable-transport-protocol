import hashlib
import os
import random
from string import ascii_letters
import time
from tests import BasicTest
import util


class WindowSizeTest(BasicTest.BasicTest):
	def set_state(self):
		self.num_of_clients = 4
		self.client_stdin = {"client21": 1, "client22": 2}
		self.input = [
			("client21", "file 1 client22 test_file2\n"),
		]
		self.time_interval = 3
		self.num_of_acks = 8*2 + 2*2 + 2*2
		with open("test_file2", "w") as f:
			f.write(''.join(random.choice(ascii_letters)
					for i in range(10000)))
		self.last_time = time.time()
		self.packets_ = {'client21': [], 'client22': []}
		self.last_ack_dropped = []
		self.checksum_test = {'client21': False, 'client22': False}
		self.window = 3
  
	def result(self, rigorous = True
            ):
     
		print("\n\033[96m===============================================\033[0m\n"
			"\033[93m WINDOW SIZE TEST - RIGOROUS VS. LESS RIGOROUS \033[0m\n"
			"\033[96m===============================================\033[0m\n"
			"\033[92m🔹 Rigorous Version:\033[0m The sender should always fill the window. (+5)\n"
			"\033[94m🔹 Less Rigorous Version:\033[0m The sender should fill the window at least once in the cycle. (+5)\n"
			"\033[96m===============================================\033[0m\n")
     
		rigorous_passed = True
		for user in self.client_stdin.keys():
			self.print_verbose(f"\n\033[94mDebugging for User: {user}\033[0m")

			join_msgs_count = 0
			is_max_passed = list(map(lambda x: self.packets_[user].count(
				x) > util.NUM_OF_RETRANSMISSIONS+1, self.packets_[user]))

			if "True" in is_max_passed:
				print(
					f"\033[91mTest {self.test_name} Failed\033[0m: A packet was retransmitted more than util.NUM_OF_RETRANSMISSIONS {util.NUM_OF_RETRANSMISSIONS}.")
				print(f"Retransmitted Packets: {is_max_passed}")
				return False, False

			
			seq_pkt = [] # Tracks in-flight packets (those not yet acknowledged)
			max_ack = 0 # This is the maximum sequence number that has been acknowledged
			packets_to_send = 0   # Number of packets to send in the current cycle
			join_msgs_count = 0    # Count join messages

			# For checking that the sender always fills the window
			max_inflight_cycle = 0  # Maximum number of in-flight packets observed in the current cycle. This is used to check if the sender filled the window in the current cycle at least once
   
			last_packet_was_start_or_end = False # My reason for doing this is to make sure that since start and end packeets are sent sequentially, i can use this to check if the last packet was a start or end packet and not penalize the sender for not filling the window in that case
   
    		# Here i will extract packets between start and end markers
			filtered = WindowSizeTest.extract_packets_between_start_and_end(self.packets_[user])
			self.print_verbose("\n\033[94mExtracted Packets:\033[0m")
			self.print_verbose(str(filtered))
			self.print_verbose("\n\033[94mIterating Through Packets...\033[0m")

   
			for idx, pkt in enumerate(self.packets_[user]):
				p_type, seq_no, data, checksum = util.parse_packet(pkt[8:])
				seq_no = int(seq_no)
				self.print_verbose(f"Packets to send: {packets_to_send}")
				self.print_verbose(f"\033[94mPacket {idx + 1}:\033[0m Type: {p_type}, Seq No: {seq_no}")

				if p_type == "start":
					self.print_verbose("  - Start Packet Detected. Resetting max_ack and cycle counter.")
					max_ack = 0
					last_packet_was_start_or_end = True
					max_inflight_cycle = 0  # reset cycle counter
     
					if len(seq_pkt) > 0:
						self.print_verbose("\033[91mTest {self.test_name} Failed\033[0m: Start Packet Detected with In-Flight Packets.")
						self.print_verbose(f"  - Current In-Flight Packets: {seq_pkt}")
						return False, False
  
					if idx in filtered:
						packets_to_send = len(filtered[idx])
						self.print_verbose(f"  - Number of Packets to Send: {packets_to_send}")
						self.print_verbose(f"  - Packets to Send: {filtered[idx]}")
					else:
						self.print_verbose("  - Warning: No extracted packets for this start packet.")
						packets_to_send = 0
					continue  # Move to the next packet

				elif p_type == "ack":
					self.print_verbose(f"  - ACK Packet Detected. Current Max Ack: {max_ack}")
					self.print_verbose(f"  - In-Flight Packets Before ACK: {seq_pkt}")
     
					# this part is a more rigorous check. This is to check if the sender always fills the window, not less not more. between two acks, there should be at least window packets sent. 
     
					if rigorous and packets_to_send >= self.window and not last_packet_was_start_or_end:
						if len(set(seq_pkt)) < self.window : # set to remove dups
							print(f"\033[91mTest {self.test_name} Failed\033[0m: In-flight packets ({len(list(set(seq_pkt)))}) did not reach the window size ({self.window}).")
							self.print_verbose(f"  - Current In-Flight Packets: {seq_pkt}")
							# return False
							rigorous_passed = False
	
						if len(seq_pkt) > self.window : # i want to check if they are filling window by just repeating apckets so to catch that, no set
							print(f"\033[91mTest {self.test_name} Failed\033[0m: In-flight packets ({len(list(seq_pkt))}) exceeded the window size ({self.window}).")
							self.print_verbose(f"  - Current In-Flight Packets: {seq_pkt}")
							rigorous_passed = False
   
     
					# this part is a less rigorous check than the one above. This is to check if the sender at some point in the cycle filled the window. This is to ensure that the sender is not just sending packets one by one
					if packets_to_send and not last_packet_was_start_or_end:
						if max_inflight_cycle < self.window and packets_to_send >= self.window:
							print(f"\033[91mTest {self.test_name} Failed\033[0m: Maximum in-flight packets in the current cycle ({max_inflight_cycle}) did not reach the window size ({self.window}).")
							self.print_verbose(f"  - Current In-Flight Packets: {seq_pkt}")
							return False, False
						if len(seq_pkt) > self.window:
							print(f"\033[91mTest {self.test_name} Failed\033[0m: In-flight packets ({len(seq_pkt)}) exceeded the window size ({self.window}).")
							self.print_verbose(f"  - Current In-Flight Packets: {seq_pkt}")
							return False, False
					max_ack = max(seq_no, max_ack) 
     
					seq_pkt = [x for x in seq_pkt if x >= max_ack] # Remove packets that have been acknowledged (i.e. seq numbers less than the maxium ack received)
					self.print_verbose(f"  - In-Flight Packets After ACK Processing: {seq_pkt}")

					last_packet_was_start_or_end = False

				else:
					if p_type == "data":
						last_packet_was_start_or_end = False
						if packets_to_send > 0:
							packets_to_send -= 1
							self.print_verbose(f"Packets to send after data update: {packets_to_send}")
       
						seq_pkt.append(seq_no) # Add the sequence number to the in-flight packets
						self.print_verbose(f"  - Added Seq No: {seq_no} to In-Flight Packets.")
						self.print_verbose(f"  - Current In-Flight Packets: {seq_pkt}")
      
						max_inflight_cycle = max(max_inflight_cycle, len(set(seq_pkt)))
						if user in data:
							join_msgs_count += 1

					if p_type == "end":
						last_packet_was_start_or_end = True
      
						if len(seq_pkt) > 0:
							self.print_verbose("\033[91mTest {self.test_name} Failed\033[0m: End Packet Detected with In-Flight Packets.")
							self.print_verbose(f"  - Current In-Flight Packets: {seq_pkt}")
							return False, False
       
						self.print_verbose("  - End Packet Detected. Clearing in-flight packets and resetting max_ack.")
						seq_pkt = []
						max_ack = 0
						max_inflight_cycle = 0

			# Final summary and join message check
			self.print_verbose(f"\n\033[94mFinal Summary for User: {user}\033[0m")
			self.print_verbose(f"  - Total Packets Processed: {len(self.packets_[user])}")
			if join_msgs_count < 3:
				print(f"\033[91mTest Failed\033[0m: Checksum Test {self.test_name} Failed. Expected Join Msg Count >= 3, Found: {join_msgs_count}")
				return False, False

		

		print(f"\033[92mTest {self.test_name} Passed (Less Rigorous version)!\033[0m")
		if rigorous_passed:
			print(f"\033[92mTest {self.test_name} Passed (Rigorous version)!\033[0m")
		else:
			print(f"\033[93mTest {self.test_name} Failed (Rigorous version)!\033[0m")
		return True, rigorous_passed


	def print_verbose(self, *args):
		if self.verbose:
			print(" ".join(map(str, args)))

	def handle_packet(self):
		for p, user in self.forwarder.in_queue:
			if len(p.full_packet) > 1500:
				self.packet_length_exceeded_limit += 1
				continue
			msg_type, a, b, c = util.parse_packet(p.full_packet.decode()[8:])
			if msg_type == "ack":
				if user in self.last_ack_dropped:
					self.last_ack_dropped.remove(user)
					self.packets_processed[msg_type] += 1
					self.forwarder.out_queue.append((p, user))
					self.packets_[user].append(p.full_packet.decode())
				else:
					self.last_ack_dropped.append(user)
			else:
				if msg_type == "data" and self.checksum_test[user] == False:
					p.full_packet = p.full_packet.decode() + "1"
					p.full_packet = p.full_packet.encode()
					self.packets_[user].append(p.full_packet.decode())
					self.packets_processed[msg_type] += 1
					self.checksum_test[user] = True
					self.forwarder.out_queue.append((p, user))
				else:
					self.packets_[user].append(p.full_packet.decode())
					self.packets_processed[msg_type] += 1
					self.forwarder.out_queue.append((p, user))

		# empty out the in_queue
		self.forwarder.in_queue = []

	@staticmethod
	def extract_packets_between_start_and_end(packets):
		"""
		Extracts packets between each start and end packet pair.

		Args:
			packets (list): A list of packet strings (e.g., ["start", "data1", "data2", "end", ...]).

		Returns:
			dict: A dictionary where the keys are the indices of `start` packets in the original list,
				and the values are lists of packets between the corresponding `start` and `end`.
		"""
		result = {}
		current_group = []
		start_index = None

		for i, packet in enumerate(packets):
			p_type, seq_no, data, checksum = util.parse_packet(packet[8:])
			if p_type == "start":
				start_index = i
				current_group = []
			elif p_type == "end":
				if start_index is not None:
					result[start_index] = current_group
					start_index = None
			elif p_type == "ack":
				# Ignore ACK packets as we only care about data packets. we want to know how many of those are left
				pass
			else:
				if start_index is not None:
					current_group.append(seq_no)

		return result
