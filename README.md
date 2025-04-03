# Twitter Follower Scraper

A robust Twitter follower scraper with advanced features:

- **Cookie Rotation**: Automatically switches between multiple cookies when rate limits are encountered
- **Rate Limit Handling**: Uses x-rate-limit-reset headers to calculate precise cooldown times
- **Structured Logging**: Includes timestamps, log levels, and cookie information in each log message
- **Recovery Functionality**: Continues scraping from where it left off using saved cursor positions

## Key Files

- `new.js`: Main scraper with cookie rotation and enhanced logging
- `main.js`: Alternative implementation with similar functionality
- `package.json`: Node.js dependencies
- `cookies.txt`: Store your Twitter cookies here (one per line)
- `requirements.txt`: Python dependencies for auxiliary scripts

## Usage

1. Add your Twitter cookies to `cookies.txt`
2. Run the scraper: `node new.js`
3. Scraped data will be saved to output files