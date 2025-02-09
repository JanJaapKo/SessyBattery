"""Sessy exceptions"""

class RequestError(Exception):
    """Custom error to handle return errors from API calls"""
    def __init__(self, code, error_message):
        self.message = "Failed call to Sessy API (status code = {}, error message: '{}')".format(code, error_message)
        super().__init__(self.message)

class ScheduleError(Exception):
    """Custom error to handle return errors from API calls"""
    def __init__(self, data_element, date_string):
        self.message = "Missing schedule information '{}' for {}".format(data_element, date_string)
        super().__init__(self.message)

class TooManyRetries(Exception):
    """Too many retries to call API"""
    def __init__(self):
        self.message = "Failed to call Sessy API (too many retries)"
        super().__init__(self.message)
