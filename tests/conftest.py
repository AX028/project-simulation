from hypothesis import settings

settings.register_profile(
    "deterministic-ci",
    derandomize=True,
    deadline=None,
    max_examples=50,
)
settings.load_profile("deterministic-ci")
