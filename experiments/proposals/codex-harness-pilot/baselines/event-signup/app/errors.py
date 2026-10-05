"""Domain errors. handlers.py turns them into {"detail", "code"} responses."""


class SignupError(Exception):
    http_status = 400
    code = "invalid_input"

    def __init__(self, detail, code=None):
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class InvalidInput(SignupError):
    http_status = 400
    code = "invalid_input"


class NotFoundError(SignupError):
    http_status = 404
    code = "not_found"


class ConflictError(SignupError):
    http_status = 409
    code = "conflict"
