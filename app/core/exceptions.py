class TviraException(Exception):
    """Base exception for Tvira Business Discovery Engine."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class SessionNotFoundError(TviraException):
    """Raised when a requested session UUID is not found in the repository."""
    def __init__(self, session_id: str):
        super().__init__(f"Session with ID '{session_id}' was not found.")
        self.session_id = session_id

class InvalidStateTransitionError(TviraException):
    """Raised when validating an invalid state transition in the session state machine."""
    def __init__(self, current_status: str, target_status: str):
        super().__init__(f"Cannot transition session from '{current_status}' to '{target_status}'.")
        self.current_status = current_status
        self.target_status = target_status

class QuestionEligibilityError(TviraException):
    """Raised when answering a question that is invalid or not pending in the current queue."""
    def __init__(self, question_key: str):
        super().__init__(f"Question '{question_key}' is not eligible to be answered in this state.")
        self.question_key = question_key

class BlueprintNotFoundError(TviraException):
    """Raised when a requested blueprint version or name does not exist."""
    def __init__(self, blueprint_name: str, version: str):
        super().__init__(f"Discovery Blueprint '{blueprint_name}' (version: {version}) was not found.")
        self.blueprint_name = blueprint_name
        self.version = version
