import hashlib
import os
import random
from string import ascii_letters
import time
from tests import BasicTest

class BasicFunctionalityTest(BasicTest.BasicTest):
    def set_state(self):
        self.num_of_clients = 4
        self.client_stdin = {"client1": 1, "client2":2, "client3":3, "client4": 4}
        self.input = [  ("client1","list\n"),
                        ("client4","msg 3 client1 client3 client4 Can we cheat?\n"),
                        ("client2","msg 4 client1 client2 client3 client4 Hello Dear Friends! Do not cheat.\n") ,
                        ("client1","file 2 client1 client5 test_file2\n") ,
                        ("client3","file 4 client1 client2 client3 client4 test_file1\n") 
                     ]
        self.last_time = time.time()
        self.num_of_acks = 8*2 + 2*2 + 4*2 + 5*2 + 2*2 + 5*2
        self.time_interval = 2
        with open("test_file1","w") as f:
            f.write(''.join(random.choice(ascii_letters) for i in range(20000)))
        
        with open("test_file2","w") as f:
            f.write(''.join(random.choice(ascii_letters) for i in range(3000)))
    

    def result(self):
        return self.result_basic()
        
