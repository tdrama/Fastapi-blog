class NotAuthenticated(Exception):
    """
    Raised when a user is not logged in or session has expired.
    Used to trigger redirect to login page in web routes.
    """
    pass
