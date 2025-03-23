import snscrape.modules.twitter as sntwitter

def scrape_twitter_content(handle, keyword):
    """Scrape tweets locally using snscrape."""
    query = f'from:{handle} "{keyword}"'
    tweets = []

    print(f"🔍 Searching for tweets with: {query}")

    for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
        if i >= 5:
            break
        tweets.append(tweet.content)
        print(f"✅ Tweet {i+1}: {tweet.content[:100]}...")

    if not tweets:
        print(f"⚠️ No tweets found for @{handle} with keyword: {keyword}")
    else:
        print(f"✅ Found {len(tweets)} tweets locally")

    return tweets
