import praw
import configparser
import time
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from prawcore.exceptions import RequestException, ResponseException, ServerError
from langdetect import detect, LangDetectException
from itertools import islice
import pickle
import os
import itertools
import threading
import queue

# Constants
NOTIFIED_POSTS_FILE = 'notified_posts.pkl'
NOTIFIED_POST_EXPIRY = 86400  # 24 hours

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Logging configuration
logging.basicConfig(
    filename=config['Logging']['log_file'],
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s'
)
logging.info("Logging initialized successfully.")

# Initialize multiple Reddit accounts
reddit_accounts = []
for section in config.sections():
    if section.startswith('RedditAccount'):
        try:
            reddit_instance = praw.Reddit(
                client_id=config[section]['client_id'],
                client_secret=config[section]['client_secret'],
                user_agent=config[section]['user_agent'],
                username=config[section]['username'],
                password=config[section]['password'],
                requestor_kwargs={'timeout': 60}
            )
            # Verify the connection
            reddit_instance.user.me()
            reddit_accounts.append(reddit_instance)
            logging.info(f"Loaded Reddit account: {reddit_instance.user.me()}")
        except Exception as e:
            logging.error(f"Failed to load Reddit account '{section}': {e}")

if not reddit_accounts:
    logging.error("No valid Reddit accounts found in config.ini. Exiting.")
    exit(1)

# General Keywords for comments
comment_keywords = [word.strip().lower() for word in config['Keywords']['keywords'].split(',') if word.strip()]
comment_exclude_keywords = [word.strip().lower() for word in config['Keywords'].get('exclude_keywords', '').split(',') if word.strip()]
exclude_languages = [lang.strip().lower() for lang in config['Keywords'].get('exclude_languages', '').split(',') if lang.strip()]

# Subreddits to monitor
all_subreddits = [sub.strip() for sub in config['Subreddits']['subreddits'].split(',') if sub.strip()]
exclude_subreddits = [sub.strip().lower() for sub in config['Subreddits'].get('exclude_subreddits', '').split(',') if sub.strip()]
filtered_subreddits = [sub for sub in all_subreddits if sub.lower() not in exclude_subreddits]

# Batching Configuration
batch_size = int(config['Batching'].get('batch_size', 500))
batch_duration_minutes = int(config['Batching'].get('batch_duration_minutes', 10))
batch_duration_seconds = batch_duration_minutes * 60

# Split subreddits into batches
def get_batches(subreddits, size):
    it = iter(subreddits)
    while True:
        batch = list(islice(it, size))
        if not batch:
            break
        yield batch

subreddit_batches = list(get_batches(filtered_subreddits, batch_size))
total_batches = len(subreddit_batches)
logging.info(f"Total subreddits: {len(filtered_subreddits)} divided into {total_batches} batches of {batch_size} each.")

# General Filter settings for comments
min_online_users = int(config['Filter'].get('min_online_users', 10))
general_time_window = int(config['Filter'].get('time_window', 10))  # In minutes; 0 means use streaming
general_min_upvotes = int(config['Filter'].get('min_upvotes', 2))
general_min_comments = int(config['Filter'].get('min_comments', 2))

# Post-specific Filter settings
post_filter_enabled = False
post_keywords = [word.strip().lower() for word in config['PostFilter'].get('keywords', '').split(',') if word.strip()]
post_created_within_hours = config['PostFilter'].get('created_within_hours', '').strip()
post_min_upvotes = config['PostFilter'].get('min_upvotes', '').strip()
post_min_comments = config['PostFilter'].get('min_comments', '').strip()

if post_keywords or post_created_within_hours or post_min_upvotes or post_min_comments:
    post_filter_enabled = True
    # Convert to appropriate types if they are set
    if post_created_within_hours:
        post_created_within_hours = int(post_created_within_hours)
    else:
        post_created_within_hours = None

    if post_min_upvotes:
        post_min_upvotes = int(post_min_upvotes)
    else:
        post_min_upvotes = None

    if post_min_comments:
        post_min_comments = int(post_min_comments)
    else:
        post_min_comments = None
else:
    # If no post-specific filters are set, use general filters
    post_filter_enabled = False

# Email settings
email_user = config['Notifications']['email']
email_password = config['Notifications']['email_password']
smtp_server = config['Notifications']['smtp_server']
smtp_port = int(config['Notifications']['smtp_port'])
recipient_email = config['Notifications']['recipient_email']

# Caching subreddit active user counts
subreddit_cache = {}
cache_expiry = {}
cache_duration = 21600  # Cache for 6 hours

# Thread-safe locks
processed_items_lock = threading.Lock()
notified_posts_lock = threading.Lock()
cache_lock = threading.Lock()

# Initialize thread-safe data structures
processed_items = set()

# Load or initialize notified_comment_posts
if os.path.exists(NOTIFIED_POSTS_FILE):
    with open(NOTIFIED_POSTS_FILE, 'rb') as f:
        notified_comment_posts = pickle.load(f)
        logging.info(f"Loaded {len(notified_comment_posts)} notified posts from file.")
else:
    notified_comment_posts = {}
    logging.info("No existing notified posts file found. Starting fresh.")

def save_notified_posts():
    with notified_posts_lock:
        with open(NOTIFIED_POSTS_FILE, 'wb') as f:
            pickle.dump(notified_comment_posts, f)
    logging.info("Saved notified_comment_posts to file.")

def cleanup_notified_posts():
    current_time = time.time()
    to_remove = []
    with notified_posts_lock:
        for post_id, timestamp in notified_comment_posts.items():
            if current_time - timestamp > NOTIFIED_POST_EXPIRY:
                to_remove.append(post_id)
        for post_id in to_remove:
            del notified_comment_posts[post_id]
    if to_remove:
        logging.info(f"Cleaned up {len(to_remove)} old entries from notified_comment_posts.")
        save_notified_posts()

# Initialize a queue for batches
batch_queue = queue.Queue()

# Enqueue all batches
for batch in subreddit_batches:
    batch_queue.put(batch)

logging.info(f"Enqueued all {batch_queue.qsize()} batches for processing.")

def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = email_user
    msg['To'] = recipient_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)
        server.quit()
        logging.info("Email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email. Error: {str(e)}")

def get_online_users(subreddit):
    name = subreddit.display_name
    current_time = time.time()
    with cache_lock:
        if name in subreddit_cache and current_time < cache_expiry.get(name, 0):
            return subreddit_cache[name]
    try:
        online_users = subreddit.active_user_count
        if online_users is None:
            online_users = 0
        with cache_lock:
            subreddit_cache[name] = online_users
            cache_expiry[name] = current_time + cache_duration
        return online_users
    except ResponseException as e:
        if e.response.status_code == 429:
            logging.error(f"Rate limit exceeded when fetching active user count for r/{name}")
            # Exponentially increase cache duration for this subreddit
            with cache_lock:
                cache_expiry[name] = current_time + (cache_duration * 2)
            return 0
        else:
            logging.error(f"Error fetching active user count for r/{name}: {e}")
            return 0
    except Exception as e:
        logging.error(f"Error fetching active user count for r/{name}: {e}")
        return 0

def send_notification(item, online_users, item_type):
    try:
        subreddit = item.subreddit
        if item_type == 'Post':
            title = item.title
            content = item.selftext
            link = item.shortlink
            upvotes = item.score
            num_comments = item.num_comments
        elif item_type == 'Comment':
            title = f"Comment by u/{item.author}"
            content = item.body
            link = f"https://reddit.com{item.permalink}"
            upvotes = item.score
            num_comments = None
        else:
            return

        subject = f"Match in r/{subreddit.display_name} ({item_type})"
        body = f"""
Title: {title}
Subreddit: r/{subreddit.display_name}
Online Users: {online_users}
Upvotes: {upvotes}
Comments: {num_comments if num_comments is not None else 'N/A'}
Link: {link}
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(item.created_utc))}
Content:
{content}
        """
        send_email(subject, body)
    except Exception as e:
        logging.error(f"Error in send_notification: {e}")

def is_language_excluded(text):
    try:
        language = detect(text)
        return language in exclude_languages
    except LangDetectException:
        return False  # If language cannot be detected, do not exclude

def process_item(item):
    try:
        # Check if the item has already been processed
        with processed_items_lock:
            if item.id in processed_items:
                return  # Skip if it's already processed

        subreddit = item.subreddit

        # Exclude subreddits
        if subreddit.display_name.lower() in exclude_subreddits:
            return  # Skip this item

        # Determine if the item is a Post or Comment
        if isinstance(item, praw.models.Submission):
            item_type = 'Post'
            text_to_search = (item.title + ' ' + item.selftext).lower()
            upvotes = item.score
            num_comments = item.num_comments
            created_time = item.created_utc
        elif isinstance(item, praw.models.Comment):
            item_type = 'Comment'
            text_to_search = item.body.lower()
            upvotes = item.score
            num_comments = None
            created_time = item.created_utc

            # Check if the parent post has already triggered a notification for comments
            parent_submission = item.submission
            parent_id = parent_submission.id

            with notified_posts_lock:
                if parent_id in notified_comment_posts:
                    return  # Already notified for this post's comments
        else:
            return  # Unsupported type

        # Exclude based on language
        if exclude_languages and is_language_excluded(text_to_search):
            return

        # Exclude keywords
        if comment_exclude_keywords:
            if any(ex_kw in text_to_search for ex_kw in comment_exclude_keywords):
                return  # Skip this item

        # Determine which keywords to use
        if item_type == 'Post' and post_filter_enabled and post_keywords:
            keywords_to_use = post_keywords
        else:
            keywords_to_use = comment_keywords

        # If no keywords to search, skip
        if not keywords_to_use:
            return

        # Check for keyword match
        matched_keyword = None
        for keyword in keywords_to_use:
            if keyword in text_to_search:
                matched_keyword = keyword
                break

        if not matched_keyword:
            return

        # Get online users
        online_users = get_online_users(subreddit)
        if online_users < min_online_users:
            return

        # Apply filters based on item type
        if item_type == 'Post':
            if post_filter_enabled:
                # Check created within X hours
                if post_created_within_hours is not None:
                    current_time = time.time()
                    if (current_time - created_time) > (post_created_within_hours * 3600):
                        return

                # Check minimum upvotes
                if post_min_upvotes is not None and upvotes < post_min_upvotes:
                    return

                # Check minimum comments
                if post_min_comments is not None and num_comments < post_min_comments:
                    return
            else:
                # Apply general filters
                if general_time_window > 0:
                    current_time = time.time()
                    if (current_time - created_time) > (general_time_window * 60):
                        return

                if upvotes < general_min_upvotes or num_comments < general_min_comments:
                    return

        elif item_type == 'Comment':
            # Apply general filters
            if general_time_window > 0:
                current_time = time.time()
                if (current_time - created_time) > (general_time_window * 60):
                    return

            if upvotes < general_min_upvotes:
                return

        # For Comments: Mark the parent post as notified to prevent future notifications
        if item_type == 'Comment':
            with notified_posts_lock:
                notified_comment_posts[parent_id] = time.time()
            save_notified_posts()

        # Log the keyword match
        logging.info(f"Match found in r/{subreddit.display_name} for keyword '{matched_keyword}': {item.shortlink if item_type == 'Post' else f'https://reddit.com{item.permalink}'}")

        # Send notification
        send_notification(item, online_users, item_type)

        # Mark the item as processed
        with processed_items_lock:
            processed_items.add(item.id)

    except Exception as e:
        logging.error(f"Error in process_item: {e}")

def monitor_recent_items(subreddits, duration, reddit_instance, max_retries=3):
    subreddit_str = '+'.join(subreddits)
    subreddit = reddit_instance.subreddit(subreddit_str)
    start_time = time.time()
    retries = 0

    while True:
        try:
            current_time = time.time()
            if current_time - start_time > duration:
                logging.info(f"Batch duration of {duration} seconds reached. Switching to next batch.")
                break  # Exit after duration

            if post_filter_enabled:
                post_time_threshold = current_time - (post_created_within_hours * 3600) if post_created_within_hours else current_time - (general_time_window * 60)
            else:
                post_time_threshold = current_time - (general_time_window * 60)

            # Fetch recent submissions
            submissions = subreddit.new(limit=None)
            for submission in submissions:
                if submission.created_utc <= post_time_threshold:
                    continue  # Skip older submissions
                process_item(submission)

            # Fetch recent comments
            if general_time_window > 0:
                comment_time_threshold = current_time - (general_time_window * 60)
            else:
                comment_time_threshold = current_time

            comments = subreddit.comments(limit=None)
            for comment in comments:
                if comment.created_utc <= comment_time_threshold:
                    continue  # Skip older comments
                process_item(comment)

            # Cleanup old notified posts
            cleanup_notified_posts()

            # Reset retries after successful operation
            retries = 0

            # Sleep before next fetch to avoid hitting rate limits
            time.sleep(30)

        except (RequestException, ResponseException, ServerError) as e:
            logging.warning(f"Retrying due to {type(e).__name__}({e}) with account {reddit_instance.user.me()}")
            retries += 1
            if retries > max_retries:
                logging.error(f"Max retries exceeded for batch {subreddits} with account {reddit_instance.user.me()}. Skipping to next batch.")
                break
            # Exponential backoff
            sleep_time = 2 ** retries
            logging.info(f"Sleeping for {sleep_time} seconds before retrying.")
            time.sleep(sleep_time)
        except Exception as e:
            logging.error(f"Error in monitor_recent_items: {e}")
            time.sleep(60)

def monitor_stream(subreddits, duration, reddit_instance, max_retries=3):
    subreddit_str = '+'.join(subreddits)
    subreddit = reddit_instance.subreddit(subreddit_str)
    start_time = time.time()
    retries = 0

    while True:
        try:
            current_time = time.time()
            if current_time - start_time > duration:
                logging.info(f"Batch duration of {duration} seconds reached. Switching to next batch.")
                break  # Exit after duration

            # Stream submissions
            for submission in subreddit.stream.submissions(pause_after=1):
                if submission is None:
                    break
                process_item(submission)

            # Stream comments
            for comment in subreddit.stream.comments(pause_after=1):
                if comment is None:
                    break
                process_item(comment)

            # Cleanup old notified posts
            cleanup_notified_posts()

            # Reset retries after successful operation
            retries = 0

            # Sleep briefly to avoid rapid looping
            time.sleep(5)

        except (RequestException, ResponseException, ServerError) as e:
            logging.warning(f"Retrying due to {type(e).__name__}({e}) with account {reddit_instance.user.me()}")
            retries += 1
            if retries > max_retries:
                logging.error(f"Max retries exceeded for batch {subreddits} with account {reddit_instance.user.me()}. Skipping to next batch.")
                break
            # Exponential backoff
            sleep_time = 2 ** retries
            logging.info(f"Sleeping for {sleep_time} seconds before retrying.")
            time.sleep(sleep_time)
        except Exception as e:
            logging.error(f"Error in monitor_stream: {e}")
            time.sleep(60)

def worker_thread(reddit_instance, batch_queue):
    while True:
        try:
            batch = batch_queue.get_nowait()
        except queue.Empty:
            logging.info(f"All batches have been processed by account {reddit_instance.user.me()}.")
            break  # No more batches to process

        try:
            logging.info(f"Account {reddit_instance.user.me()} processing batch with {len(batch)} subreddits.")
            # Determine which monitoring function to use
            if general_time_window > 0 or post_filter_enabled:
                monitor_recent_items(batch, batch_duration_seconds, reddit_instance=reddit_instance)
            else:
                monitor_stream(batch, batch_duration_seconds, reddit_instance=reddit_instance)
            logging.info(f"Account {reddit_instance.user.me()} completed batch. Moving to next batch.")
            # Optional: Add a short delay between batches to prevent immediate rate limiting
            time.sleep(5)
        except Exception as e:
            logging.error(f"Error processing batch with account {reddit_instance.user.me()}: {e}")

        batch_queue.task_done()

def start_threads():
    threads = []
    for reddit_instance in reddit_accounts:
        t = threading.Thread(target=worker_thread, args=(reddit_instance, batch_queue))
        t.start()
        threads.append(t)
        logging.info(f"Started thread for account {reddit_instance.user.me()}.")

    # Wait for all batches to be processed
    for t in threads:
        t.join()

    logging.info("All threads have completed processing.")

if __name__ == "__main__":
    try:
        logging.info("Starting Reddit Monitor with Multithreaded Batch Processing.")
        start_threads()
    except Exception as e:
        logging.error(f"Unhandled exception in main: {e}")
