#!/usr/bin/ipython-3.10
from atproto import AtUri, Client, models
from bsky_cred import bsky_secrets
from datetime import datetime, timedelta
import time
import re
import typing as t
import json
import requests
import grapheme
from pathlib import Path

def truncate_to_graphemes(text, max_graphemes=300):
    # Split the text into graphemes and take the first `max_graphemes`
    grapheme_list = list(grapheme.graphemes(text))[:max_graphemes]
    # Rejoin the graphemes back into a string
    truncated_text = ''.join(grapheme_list)
    return truncated_text

def expand_urls(url_list):
    expanded_urls = {}
    for short_url in url_list:
        try:
            response = requests.head(short_url, allow_redirects=True)
            expanded_urls[short_url] = response.url
        except requests.RequestException as e:
            expanded_urls[short_url] = None
            print(f"Error expanding {short_url}: {e}")
    return expanded_urls

def expand_url(short_url):
    try:
        response = requests.head(short_url, allow_redirects=True)
        expanded_url = response.url
    except:
        expanded_url = None
    return expanded_url

def media_url(url, tid):
    try:
        # Regular expression to match 
        newurl = ""
        match = re.search(r"/media/(.*)", url)
        if match:
            newsub = match.group(1)
            newurl="data/tweets_media/"+tid+"-"+newsub
        else:
            newsub = ""
            
    except:
        newurl = ""
    return newurl

def extract_url_byte_positions(text: str, *, encoding: str = 'UTF-8') -> t.List[t.Tuple[str, int, int]]:
    """This function will detect any links beginning with http or https."""
    encoded_text = text.encode(encoding)
    # Adjusted URL matching pattern
    pattern = rb'https?://[^ \n\r\t]*'
    matches = re.finditer(pattern, encoded_text)
    url_byte_positions = []
    for match in matches:
        url_bytes = match.group(0)
        url = url_bytes.decode(encoding)
        url_byte_positions.append((url, match.start(), match.end()))
    return url_byte_positions

# Function to convert Twitter date to ISO 8601 format
def convert_to_iso8601(twitter_date):
    # Example Twitter date format: "Mon Nov 12 05:16:29 +0000 2018"
    dt = datetime.strptime(twitter_date, "%a %b %d %H:%M:%S %z %Y")
    return dt.isoformat()

############################################################################
def main() -> None:
    # Parse the JSON data
    f = open('twitter/tweets.js')
    tweets = json.load(f)
    # Closing file
    f.close()

    # Initialize the client and authenticate
    client = Client()
    profile = client.login(bsky_secrets['uid'], bsky_secrets['pw'])
    print('Welcome,', profile.display_name)

    # Loop through the tweets and post to Bluesky
    num=0
    main_num=0
    for item in tweets:
        tweet = item["tweet"]
        num=num+1
        main_num=main_num+1
        tweet_text=truncate_to_graphemes(tweet["full_text"])
        tweet_id = tweet["id"]
        mymedia=""
        mymediaurl = ""
        print(f"#{main_num}:{tweet_text}")
        if num > 100:
            time.sleep(5)
            num=0
        try:
            if "extended_entities" in tweet:
                extweet = tweet["extended_entities"]
                if "media" in extweet:
                    tweet_media = extweet["media"]
                    if "media_url" in tweet_media[0]:
                        mymediaurl = tweet_media[0]["media_url"]
                    else:
                        print("No url in media")
        except:
            print(f"Error get tweets!")
        created_at = convert_to_iso8601(tweet["created_at"])
        # Determine locations of URLs in the post's text
        url_positions = extract_url_byte_positions(tweet_text)
        facets = []
        for link_data in url_positions:
            uri, byte_start, byte_end = link_data
            tweet_text=tweet_text.replace("http://t.co/", "https://bsky")
            myuri = expand_url(uri)
            if myuri:
                facets.append(
                    models.AppBskyRichtextFacet.Main(
                        features=[models.AppBskyRichtextFacet.Link(uri=myuri)],
                        index=models.AppBskyRichtextFacet.ByteSlice(byte_start=byte_start, byte_end=byte_end),
                    )
                )
        
        image_path=media_url(mymediaurl,tweet_id)
        if image_path:
            print(f"IMAGE:{image_path}")
            file_path = Path(image_path)
            if file_path.exists():
                images = []
                with open(image_path, 'rb') as f:
                    images = client.com.atproto.repo.upload_blob(f)
                blob= images.blob
                # Embed the image
                embed = {
                    "$type": "app.bsky.embed.images",
                    "images": [
                        {
                            "$type": "app.bsky.embed.images#image",
                            "image": blob,  # Blob reference returned from upload
                            "alt": f"image {image_path}"  # Alt text for accessibility
                        }
                    ]
                }
                post_record = models.AppBskyFeedPost.Record(
                    text=f"{tweet_text}",
                    created_at=created_at,
                    embed=embed
                )
            else:
                print(f"file {image_path} unknown")
        else:
            post_record = models.AppBskyFeedPost.Record(
                text=f"{tweet_text}",
                created_at=created_at,
                facets=facets
            )
        new_post = client.app.bsky.feed.post.create(client.me.did, post_record)
        time.sleep(1)  # Wait 1 second 
        #print(f'Post successfully published!')

if __name__ == '__main__':
    main()

