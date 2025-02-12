# Reddit Monitor 🤖

[![Python](https://img.shields.io/badge/Python-3.6%2B-blue)](https://www.python.org/)
[![PRAW](https://img.shields.io/badge/PRAW-Latest-orange)](https://praw.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg)](CONTRIBUTING.md)

This project is a powerful, multi-threaded Reddit monitoring tool that scans subreddits for posts and comments containing specific keywords, applies sophisticated filters, and sends email notifications when matches are found. Perfect for market research, trend monitoring, or keeping track of specific topics across Reddit.

<div align="center">
    <img src="docs/images/reddit-monitor-banner.png" alt="Reddit Monitor Banner" width="600px">
</div>

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/Reddit-Keyword-Monitoring.git

# Navigate to the project directory
cd Reddit-Keyword-Monitoring

# Install dependencies
pip install -r requirements.txt

# Configure your settings
cp config.example.ini config.ini
# Edit config.ini with your settings

# Run the monitor
python reddit_monitor.py
```

---

## Table of Contents
1. [Overview](#overview)
2. [Features](#features)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Running the Script](#running-the-script)
7. [File Structure](#file-structure)
8. [Customization](#customization)
9. [Logging](#logging)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Reddit Monitor is designed to efficiently monitor multiple subreddits for posts and comments that match predefined criteria. It uses multiple Reddit accounts to distribute the load and avoid rate limits, processes subreddits in batches, and sends email notifications for relevant matches.

---

## Features

- **Multi-Account Support**: Use multiple Reddit accounts to handle large workloads.
- **Batch Processing**: Divide subreddits into batches for efficient processing.
- **Keyword Matching**: Monitor for specific keywords in posts and comments.
- **Exclusion Filters**: Exclude certain keywords, languages, or subreddits from monitoring.
- **Advanced Filtering**: Apply filters based on upvotes, comment counts, and online user activity.
- **Email Notifications**: Send email alerts when matching posts or comments are found.
- **Thread-Safe Operations**: Ensure thread safety with locks for shared resources.
- **Cache Mechanism**: Cache subreddit active user counts to reduce API calls.

---

## Prerequisites

Before running the script, ensure you have the following:

### System Requirements
- Python 3.6 or higher
- 512MB RAM minimum
- Stable internet connection

### Required Python Packages
```bash
pip install -r requirements.txt
```

Required packages include:
- `praw>=7.0.0`: Reddit API wrapper
- `configparser`: Configuration file parsing
- `langdetect`: Language detection
- `pandas`: Data handling (for analytics)
- `schedule`: Task scheduling
- `colorlog`: Enhanced logging with colors

### API Credentials
1. Create a Reddit account
2. Go to https://www.reddit.com/prefs/apps
3. Click "Create App" or "Create Another App"
4. Fill in the required information:
   - Name: `Reddit-Keyword-Monitor`
   - Type: `script`
   - Redirect URI: `http://localhost:8080`
5. Note down your:
   - Client ID
   - Client Secret

---

## Installation

1. Clone the repository or download the script files.
2. Install the required Python packages:
   ```bash
   pip install praw configparser smtplib langdetect itertools threading queue
   ```
3. Create a `config.ini` file using the provided template below.

---

## Configuration

The configuration file (`config.ini`) contains all the settings for the Reddit Monitor. Below is an example structure:

```ini
[RedditAccount1]
client_id = YOUR_CLIENT_ID_1
client_secret = YOUR_CLIENT_SECRET_1
user_agent = keyword_monitor:v2.0 (by u/Username1)
username = Username1
password = Password1

[RedditAccount2]
client_id = YOUR_CLIENT_ID_2
client_secret = YOUR_CLIENT_SECRET_2
user_agent = keyword_monitor:v2.0 (by u/Username2)
username = Username2
password = Password2

; Add more accounts as needed

[Keywords]
keywords = Amazon Prime, HBO, Hulu, Netflix, TV Show, TV Series, VPN
exclude_keywords = NetflixByProxy, Rhonda_Lime
exclude_languages = de, es, fr, pt

[Subreddits]
subreddits = technology, movies, streaming, entertainment
exclude_subreddits = politics, news

[Filter]
min_online_users = 10
time_window = 10
min_upvotes = 2
min_comments = 2

[PostFilter]
keywords = Amazon Prime, "HBO", Hulu, Movie, Netflix, TV Show, TV Series, VPN
created_within_hours = 8
min_upvotes = 2
min_comments = 2

[Notifications]
email = your_email@gmail.com
email_password = your_email_password
smtp_server = smtp.gmail.com
smtp_port = 465
recipient_email = recipient_email@gmail.com

[Batching]
batch_size = 500
batch_duration_minutes = 10

[Logging]
log_file = reddit_monitor.log
```

---

## Running the Script

1. Save the `config.ini` file in the same directory as the script.
2. Run the script using the following command:
   ```bash
   python reddit_monitor.py
   ```
3. The script will start monitoring subreddits based on the configuration.

---

## File Structure

- `reddit_monitor.py`: The main script for the Reddit Monitor.
- `config.ini`: Configuration file for setting up accounts, keywords, filters, and notifications.
- `notified_posts.pkl`: A cache file for storing notified posts to prevent duplicate notifications.
- `reddit_monitor.log`: Log file for recording script activities.

---

## Customization

### Adding More Accounts
To add more Reddit accounts, create additional sections in the `config.ini` file with names like `[RedditAccount3]`, `[RedditAccount4]`, etc., and provide the necessary credentials.

### Adjusting Batching
You can adjust the batch size and duration by modifying the `batch_size` and `batch_duration_minutes` values in the `[Batching]` section.

### Modifying Filters
Adjust the filter settings in the `[Filter]` and `[PostFilter]` sections to fine-tune the criteria for matching posts and comments.

---

## Logging

The script logs all activities to the file specified in the `[Logging]` section (`reddit_monitor.log`). This includes information about processed items, errors, and notifications sent.

---

## Troubleshooting

### Common Issues
1. **Rate Limit Exceeded**: If you encounter rate limit issues, consider increasing the `batch_duration_minutes` or adding more Reddit accounts.
2. **Email Not Sending**: Ensure your email credentials are correct and that your SMTP server allows less secure apps if using Gmail.
3. **Script Crashes**: Check the log file (`reddit_monitor.log`) for detailed error messages.

If you encounter any issues not covered here, please open an issue in the repository or consult the documentation for the libraries used.

---

## Advanced Usage

### Custom Filtering Rules
You can create complex filtering rules by combining multiple conditions:

```python
[CustomFilters]
# Example of advanced filtering
min_account_age_days = 30
required_karma = 100
post_length_min = 50
title_contains = ["[SERIOUS]", "Discussion"]
```

### Webhook Integration
The monitor supports webhook notifications to popular platforms:

```ini
[Webhooks]
discord_webhook = YOUR_DISCORD_WEBHOOK_URL
slack_webhook = YOUR_SLACK_WEBHOOK_URL
telegram_bot_token = YOUR_TELEGRAM_BOT_TOKEN
telegram_chat_id = YOUR_CHAT_ID
```

### Analytics
Enable data collection for insights:

```ini
[Analytics]
enable_analytics = true
export_format = csv
export_interval_hours = 24
metrics = upvotes,comments,sentiment
```

## 📊 Performance Optimization

### Memory Usage
- Batch size: 500 subreddits recommended for 1GB RAM
- Cache duration: 10 minutes default, adjust based on needs
- Thread pool: 4 threads recommended for most use cases

### Rate Limiting
The script implements exponential backoff:
- Initial delay: 1 second
- Max delay: 5 minutes
- Jitter: ±500ms

## 🔒 Security Best Practices

1. **API Credentials**
   - Never commit `config.ini` with real credentials
   - Use environment variables for sensitive data
   - Rotate Reddit API credentials regularly

2. **Email Security**
   - Use app-specific passwords for Gmail
   - Enable 2FA on email accounts
   - Consider using OAuth 2.0

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:
- Code Style
- Pull Request Process
- Development Setup
- Testing Requirements

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Reddit API Team for PRAW
- Contributors and maintainers
- Open source community

---

<div align="center">
    <p>Made with ❤️ by the Reddit Monitor Team</p>
    <p>
        <a href="https://github.com/yourusername/Reddit-Keyword-Monitoring/issues">Report Bug</a> ·
        <a href="https://github.com/yourusername/Reddit-Keyword-Monitoring/issues">Request Feature</a>
    </p>
</div>