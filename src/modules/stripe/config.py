"""Configuration for Stripe documentation fetcher."""

# Base URL for Stripe docs
BASE_URL = "https://docs.stripe.com"

# llms.txt URL containing all documentation links
LLMS_TXT_URL = "https://docs.stripe.com/llms.txt"

# Output directory name
OUTPUT_DIR = "stripe"

# Rate limiting
REQUEST_DELAY = 0.3  # seconds between requests
