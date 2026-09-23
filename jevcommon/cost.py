PRICE_PER_TOKEN = 0.042 / 1_000_000  # jev-1.13 list price, input tokens only


def usd(input_tokens: int) -> float:
    return input_tokens * PRICE_PER_TOKEN
