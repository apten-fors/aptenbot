from prometheus_client import Histogram, Gauge, Counter

ig_session_age_seconds = Gauge(
    "ig_session_age_seconds", "Age of current Instagram session")
ig_login_duration_seconds = Histogram(
    "ig_login_duration_seconds", "Duration of Instagram login")
ig_login_errors_total = Counter(
    "ig_login_errors_total", "Number of Instagram login errors")
