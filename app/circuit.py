import pybreaker

login_cb = pybreaker.CircuitBreaker(
    fail_max=3,          # open after 3 failures
    reset_timeout=30     # try again after 30 seconds
)
