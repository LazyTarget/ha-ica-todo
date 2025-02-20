import logging


class EmptyLogger(logging.Logger):
    """Acts as an dumb logger that doesn't actually log anything"""

    def __init__(self):
        self.disabled = True
