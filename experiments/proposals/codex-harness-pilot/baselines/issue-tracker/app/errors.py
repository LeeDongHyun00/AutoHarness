"""Errors raised by the service layer; server.py maps them to HTTP responses."""


class AppError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class BadRequest(AppError):
    status = 400
    code = "bad_request"


class Unauthorized(AppError):
    status = 401
    code = "unauthorized"


class Forbidden(AppError):
    status = 403
    code = "forbidden"


class NotFound(AppError):
    status = 404
    code = "not_found"


class Conflict(AppError):
    status = 409
    code = "conflict"
