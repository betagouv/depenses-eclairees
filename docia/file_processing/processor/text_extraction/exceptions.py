class FileSizeLimitException(Exception):
    def __init__(self, limit, actual):
        super().__init__(f"File is too large ({actual}), limit={limit}")
        self.limit = limit
        self.actual = actual
