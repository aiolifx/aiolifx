from dataclasses import dataclass

@dataclass
class BaseFixture():
    def __init__(self, req_with_resp, req_with_ack, fire_and_forget):
        self.req_with_resp = req_with_resp
        self.req_with_ack = req_with_ack
        self.fire_and_forget = fire_and_forget
        return