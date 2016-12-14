# -*- mode: python; python-indent: 4 -*-

class ActionError(Exception):
    def __init__(self, info):
        self.info = info
    def get_info(self):
        return self.info
