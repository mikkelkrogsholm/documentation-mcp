"""Configuration for Next.js documentation fetcher."""

# Base URL for Next.js docs
BASE_URL = "https://nextjs.org/docs"

# llms.txt URL containing all documentation links
LLMS_TXT_URL = "https://nextjs.org/docs/llms.txt"

# Output directory name
OUTPUT_DIR = "nextjs"

# Rate limiting
REQUEST_DELAY = 0.3  # seconds between requests
