import os
import requests
import re
import time
import random
import sys
import threading
import json
import base64
import hashlib
import hmac
import uuid
from datetime import datetime
from queue import Queue
from colorama import init, Fore, Style, Back
# Add this at the top of the file after imports
PROXIES = [
    "185.238.228.59:80",
    "104.21.25.196:80",
    "185.174.138.91:80",
    # ... include all proxies from your list ...
    "159.112.235.60:80"
]

# Modify the InstagramSession class __init__ method
class InstagramSession:
    def __init__(self, username, password, api_updater):
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.success_count = 0
        self.failure_count = 0
        self.csrftoken = None
        self.cookies = None
        self.lock = threading.Lock()
        self.api_updater = api_updater
        self.user_id = None
        self.is_active = False
        self.last_activity = time.time()
        self.challenge_url = None
        self.challenge_data = None
        self.account_info = {}
        self.current_proxy = None
        self.proxy_failures = 0
        self.max_proxy_failures = 3
        
    def get_random_proxy(self):
        """Get a random proxy from the list"""
        return random.choice(PROXIES)
    
    def set_proxy(self, proxy=None):
        """Set proxy for the session"""
        if proxy is None:
            proxy = self.get_random_proxy()
        
        self.current_proxy = proxy
        proxy_dict = {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }
        self.session.proxies = proxy_dict
        print(f"{Fore.BLUE}🔄 Using proxy: {proxy}{Style.RESET_ALL}")
        
    def rotate_proxy(self):
        """Rotate to a new proxy after failure"""
        self.proxy_failures += 1
        if self.proxy_failures >= self.max_proxy_failures:
            print(f"{Fore.YELLOW}⚠️ Proxy {self.current_proxy} failed multiple times. Rotating...{Style.RESET_ALL}")
            self.set_proxy()
            self.proxy_failures = 0
        else:
            print(f"{Fore.YELLOW}⚠️ Request failed with proxy {self.current_proxy}. Retrying... ({self.proxy_failures}/{self.max_proxy_failures}){Style.RESET_ALL}")

    def login(self):
        """Login to Instagram using username and password with proxy support"""
        print(f"{Fore.YELLOW}🔄 Logging in as {self.username}...{Style.RESET_ALL}")
        
        # Set initial proxy
        self.set_proxy()
        
        try:
            # Update API endpoints before login
            self.api_updater.update_api_endpoints()
            
            # Get initial page to get CSRF token
            response = self.session.get("https://www.instagram.com/")
            csrf_token_match = re.search(r'\"csrf_token\":\"(.*?)\"', response.text)
            if csrf_token_match:
                self.csrftoken = csrf_token_match.group(1)
            else:
                print(f"{Fore.RED}❌ Could not extract CSRF token{Style.RESET_ALL}")
                self.rotate_proxy()
                return False
            
            # Prepare login data with improved format
            login_data = {
                'username': self.username,
                'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{self.password}',
                'queryParams': {},
                'optIntoOneTap': 'false',
                'stopDeletion': 'false',
                'trustedDevice': 'false',
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'X-CSRFToken': self.csrftoken,
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.instagram.com/',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://www.instagram.com',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }
            
            # Send login request
            response = self.session.post(
                self.api_updater.api_endpoints['login'],
                headers=headers,
                data=login_data
            )
            
            # Check if response is valid JSON
            try:
                response_json = response.json()
            except:
                print(f"{Fore.RED}❌ Invalid response from server{Style.RESET_ALL}")
                self.rotate_proxy()
                return False
            
            # Check if login was successful
            if response_json.get('authenticated') or response_json.get('user'):
                print(f"{Fore.GREEN}✅ Login successful!{Style.RESET_ALL}")
                self.csrftoken = self.csrftoken
                self.cookies = self.session.cookies.get_dict()
                self.is_active = True
                self.proxy_failures = 0  # Reset failures on success
                
                # Get user ID
                if 'userId' in response_json:
                    self.user_id = response_json['userId']
                elif 'user' in response_json and 'pk' in response_json['user']:
                    self.user_id = response_json['user']['pk']
                
                # Get account info
                self.get_account_info()
                
                return True
            
            # Check if there's a challenge
            elif 'challenge' in response_json:
                print(f"{Fore.YELLOW}⚠️ Challenge required!{Style.RESET_ALL}")
                challenge_data = response_json['challenge']
                self.challenge_url = challenge_data.get('url')
                self.challenge_data = challenge_data
                
                # Handle the challenge
                return self.handle_challenge()
            
            # Login failed with error message
            else:
                error_message = response_json.get('message', 'Unknown error')
                print(f"{Fore.RED}❌ Login failed! {error_message}{Style.RESET_ALL}")
                self.rotate_proxy()
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Login error: {str(e)}{Style.RESET_ALL}")
            self.rotate_proxy()
            return False

# Similarly, modify other methods that make requests to use proxies
# For example, modify get_account_info:

    def get_account_info(self):
        """Get detailed account information with proxy support"""
        print(f"{Fore.YELLOW}📊 Getting account information...{Style.RESET_ALL}")
        
        try:
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                self.api_updater.api_endpoints['account_details'],
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                account_data = response.json()
                self.account_info = account_data
                
                # Display account info
                user = account_data.get('user', {})
                print(f"{Fore.GREEN}✅ Account information retrieved{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Username: {user.get('username', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Full Name: {user.get('full_name', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Bio: {user.get('biography', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Followers: {user.get('follower_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Following: {user.get('following_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Posts: {user.get('media_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Private: {'Yes' if user.get('is_private', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Verified: {'Yes' if user.get('is_verified', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Business: {'Yes' if user.get('is_business', False) else 'No'}{Style.RESET_ALL}")
                
                return True
            else:
                print(f"{Fore.RED}❌ Failed to get account information{Style.RESET_ALL}")
                self.rotate_proxy()
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting account information: {str(e)}{Style.RESET_ALL}")
            self.rotate_proxy()
            return False

# Add this method to test proxy connectivity
    def test_proxy(self, proxy=None):
        """Test if a proxy is working"""
        if proxy is None:
            proxy = self.get_random_proxy()
            
        test_url = "http://httpbin.org/ip"
        proxy_dict = {
            'http': f'http://{proxy}',
            'https': f'http://{proxy}'
        }
        
        try:
            print(f"{Fore.BLUE}🔍 Testing proxy: {proxy}{Style.RESET_ALL}")
            response = requests.get(test_url, proxies=proxy_dict, timeout=10)
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Proxy {proxy} is working!{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Proxy {proxy} returned status code: {response.status_code}{Style.RESET_ALL}")
                return False
        except Exception as e:
            print(f"{Fore.RED}❌ Proxy {proxy} failed: {str(e)}{Style.RESET_ALL}")
            return False

# Add this function to test all proxies
def test_all_proxies():
    """Test all proxies in the list and return working ones"""
    working_proxies = []
    print(f"{Fore.YELLOW}🔄 Testing all proxies...{Style.RESET_ALL}")
    
    for proxy in PROXIES:
        session = InstagramSession("", "", InstagramAPIUpdater())
        if session.test_proxy(proxy):
            working_proxies.append(proxy)
    
    print(f"{Fore.GREEN}✅ Found {len(working_proxies)} working proxies out of {len(PROXIES)}{Style.RESET_ALL}")
    return working_proxies
# Initialize colorama for colored output
init(autoreset=True)

class InstagramAPIUpdater:
    """Handles automatic updates of Instagram API endpoints and parameters"""
    
    def __init__(self):
        self.api_endpoints = {
            'login': 'https://www.instagram.com/accounts/login/ajax/',
            'user_info': 'https://www.instagram.com/api/v1/users/web_profile_info/',
            'stories': 'https://www.instagram.com/graphql/query',
            'report_info': 'https://www.instagram.com/api/v1/web/reports/get_frx_prompt/',
            'submit_report': 'https://www.instagram.com/api/v1/web/reports/submit_report/',
            'user_feed': 'https://www.instagram.com/api/v1/feed/user/',
            'media_info': 'https://www.instagram.com/api/v1/media/{media_id}/info/',
            'comment': 'https://www.instagram.com/api/v1/media/{media_id}/comment/',
            'like': 'https://www.instagram.com/api/v1/media/{media_id}/like/',
            'unlike': 'https://www.instagram.com/api/v1/media/{media_id}/unlike/',
            'follow': 'https://www.instagram.com/api/v1/friendships/create/{user_id}/',
            'unfollow': 'https://www.instagram.com/api/v1/friendships/destroy/{user_id}/',
            'direct_message': 'https://www.instagram.com/api/v1/direct_v2/web/create_thread/',
            'send_direct': 'https://www.instagram.com/api/v1/direct_v2/threads/{thread_id}/items/',
            'search': 'https://www.instagram.com/api/v1/users/search/',
            'explore': 'https://www.instagram.com/api/v1/explore/',
            'hashtag': 'https://www.instagram.com/api/v1/tags/{tag_name}/sections/',
            'location': 'https://www.instagram.com/api/v1/locations/{location_id}/sections/',
            'igtv': 'https://www.instagram.com/api/v1/igtv/channel/',
            'reels': 'https://www.instagram.com/api/v1/clips/user/',
            'saved': 'https://www.instagram.com/api/v1/feed/saved/',
            'notifications': 'https://www.instagram.com/api/v1/news/inbox/',
            'activity': 'https://www.instagram.com/api/v1/news/',
            'suggestions': 'https://www.instagram.com/api/v1/discover/chaining/',
            'top_live': 'https://www.instagram.com/api/v1/live/top-live/',
            'user_stories': 'https://www.instagram.com/api/v1/feed/user/{user_id}/story/',
            'story_tray': 'https://www.instagram.com/api/v1/feed/reels_tray/',
            'highlights': 'https://www.instagram.com/api/v1/highlights/{highlight_id}/highlights_tray/',
            'guide': 'https://www.instagram.com/api/v1/guide/{guide_id}/',
            'collection': 'https://www.instagram.com/api/v1/collections/{collection_id}/',
            'archived': 'https://www.instagram.com/api/v1/feed/archive/reel_media/',
            'close_friends': 'https://www.instagram.com/api/v1/close_friends/list/',
            'blocked_accounts': 'https://www.instagram.com/api/v1/users/blocked_list/',
            'muted_accounts': 'https://www.instagram.com/api/v1/users/muted_list/',
            'restricted_accounts': 'https://www.instagram.com/api/v1/users/restricted_list/',
            'account_details': 'https://www.instagram.com/api/v1/accounts/current_user/?edit=true',
            'update_profile': 'https://www.instagram.com/api/v1/accounts/current_user/?edit=true',
            'change_password': 'https://www.instagram.com/api/v1/accounts/change_password/',
            'delete_media': 'https://www.instagram.com/api/v1/media/{media_id}/delete/',
            'edit_media': 'https://www.instagram.com/api/v1/media/{media_id}/edit_media/',
            'upload_photo': 'https://www.instagram.com/api/v1/upload/photo/',
            'upload_video': 'https://www.instagram.com/api/v1/upload/video/',
            'upload_reel': 'https://www.instagram.com/api/v1/upload/reel/',
            'configure': 'https://www.instagram.com/api/v1/media/configure/',
            'comment_delete': 'https://www.instagram.com/api/v1/media/{comment_id}/comment/delete/',
            'comment_like': 'https://www.instagram.com/api/v1/media/{comment_id}/comment/like/',
            'comment_unlike': 'https://www.instagram.com/api/v1/media/{comment_id}/comment/unlike/',
            'media_insights': 'https://www.instagram.com/api/v1/insights/media/{media_id}/',
            'account_insights': 'https://www.instagram.com/api/v1/insights/account/',
            'audience_insights': 'https://www.instagram.com/api/v1/insights/account/audience/',
            'content_publishing': 'https://www.instagram.com/api/v1/content_publishing/',
            'brand_content_ads': 'https://www.instagram.com/api/v1/brand_content_ads/',
            'creator_studio': 'https://www.instagram.com/api/v1/creator_studio/',
            'professional_dashboard': 'https://www.instagram.com/api/v1/professional_dashboard/',
            'branded_content': 'https://www.instagram.com/api/v1/branded_content/',
            'collab_manager': 'https://www.instagram.com/api/v1/collab_manager/',
            'ads_manager': 'https://www.instagram.com/api/v1/ads_manager/',
            'business_suite': 'https://www.instagram.com/api/v1/business_suite/',
            'shopping': 'https://www.instagram.com/api/v1/shopping/',
            'affiliates': 'https://www.instagram.com/api/v1/affiliates/',
            'subscriptions': 'https://www.instagram.com/api/v1/subscriptions/',
            'badges': 'https://www.instagram.com/api/v1/badges/',
            'stars': 'https://www.instagram.com/api/v1/stars/',
            'guides': 'https://www.instagram.com/api/v1/guides/',
            'fundraisers': 'https://www.instagram.com/api/v1/fundraisers/',
            'donations': 'https://www.instagram.com/api/v1/donations/',
            'user_following': 'https://www.instagram.com/api/v1/friendships/{user_id}/following/',
            'user_followers': 'https://www.instagram.com/api/v1/friendships/{user_id}/followers/',
            'user_media': 'https://www.instagram.com/api/v1/feed/user/{user_id}/?max_id={max_id}',
            'user_igtv': 'https://www.instagram.com/api/v1/igtv/user/{user_id}/feed/',
            'user_tags': 'https://www.instagram.com/api/v1/usertags/{user_id}/feed/',
            'timeline': 'https://www.instagram.com/api/v1/feed/timeline/',
            'popular': 'https://www.instagram.com/api/v1/explore/popular/',
            'stories_archive': 'https://www.instagram.com/api/v1/archive/reel_media/',
            'posts_archive': 'https://www.instagram.com/api/v1/archive/post/',
            'live_comments': 'https://www.instagram.com/api/v1/live/{broadcast_id}/get_comment/',
            'send_live_comment': 'https://www.instagram.com/api/v1/live/{broadcast_id}/comment/',
            'like_live': 'https://www.instagram.com/api/v1/live/{broadcast_id}/like/',
            'join_live': 'https://www.instagram.com/api/v1/live/{broadcast_id}/join_and_get_viewer_count/',
            'leave_live': 'https://www.instagram.com/api/v1/live/{broadcast_id}/leave/',
            'create_highlight': 'https://www.instagram.com/api/v1/highlights/create_highlight/',
            'edit_highlight': 'https://www.instagram.com/api/v1/highlights/{highlight_id}/edit_reel/',
            'delete_highlight': 'https://www.instagram.com/api/v1/highlights/{highlight_id}/delete_reel/',
            'create_collection': 'https://www.instagram.com/api/v1/collections/create/',
            'edit_collection': 'https://www.instagram.com/api/v1/collections/{collection_id}/edit/',
            'delete_collection': 'https://www.instagram.com/api/v1/collections/{collection_id}/delete/',
            'save_to_collection': 'https://www.instagram.com/api/v1/media/{media_id}/save/',
            'unsave_from_collection': 'https://www.instagram.com/api/v1/media/{media_id}/unsave/',
            'block_user': 'https://www.instagram.com/api/v1/friendships/block/{user_id}/',
            'unblock_user': 'https://www.instagram.com/api/v1/friendships/unblock/{user_id}/',
            'restrict_user': 'https://www.instagram.com/api/v1/restrict_action/restrict/',
            'unrestrict_user': 'https://www.instagram.com/api/v1/restrict_action/unrestrict/',
            'mute_user': 'https://www.instagram.com/api/v1/friendships/mute_friend_reel/{user_id}/',
            'unmute_user': 'https://www.instagram.com/api/v1/friendships/unmute_friend_reel/{user_id}/',
            'mute_post': 'https://www.instagram.com/api/v1/friendships/mute_friend_post/{user_id}/',
            'unmute_post': 'https://www.instagram.com/api/v1/friendships/unmute_friend_post/{user_id}/',
            'mute_story': 'https://www.instagram.com/api/v1/friendships/mute_friend_story/{user_id}/',
            'unmute_story': 'https://www.instagram.com/api/v1/friendships/unmute_friend_story/{user_id}/',
            'close_friends_add': 'https://www.instagram.com/api/v1/close_friends/list/add/',
            'close_friends_remove': 'https://www.instagram.com/api/v1/close_friends/list/remove/',
            'account_switch': 'https://www.instagram.com/api/v1/accounts/switch_active_account/',
            'account_remove': 'https://www.instagram.com/api/v1/accounts/remove_logged_in_account/',
            'account_register': 'https://www.instagram.com/api/v1/accounts/create/',
            'account_verify': 'https://www.instagram.com/api/v1/accounts/send_verify_email/',
            'account_reset_password': 'https://www.instagram.com/api/v1/accounts/account_recovery_ajax_send_code/',
            'account_confirm_reset': 'https://www.instagram.com/api/v1/accounts/account_recovery_ajax_confirm_code/',
            'account_set_new_password': 'https://www.instagram.com/api/v1/accounts/account_recovery_ajax_reset_password/',
            'two_factor_enable': 'https://www.instagram.com/api/v1/accounts/two_factor_enable/',
            'two_factor_disable': 'https://www.instagram.com/api/v1/accounts/two_factor_disable/',
            'two_factor_backup_codes': 'https://www.instagram.com/api/v1/accounts/generate_backup_codes/',
            'login_activity': 'https://www.instagram.com/api/v1/accounts/login_activity/',
            'logout_sessions': 'https://www.instagram.com/api/v1/accounts/logout_all_sessions/',
            'privacy_check': 'https://www.instagram.com/api/v1/accounts/privacy_check/',
            'set_private': 'https://www.instagram.com/api/v1/accounts/set_private/',
            'set_public': 'https://www.instagram.com/api/v1/accounts/set_public/',
            'sync_contacts': 'https://www.instagram.com/api/v1/contacts/sync/',
            'link_facebook': 'https://www.instagram.com/api/v1/fb/link_account/',
            'unlink_facebook': 'https://www.instagram.com/api/v1/fb/unlink_account/',
            'business_conversion': 'https://www.instagram.com/api/v1/business/account_conversion/',
            'business_discovery': 'https://www.instagram.com/api/v1/business/discovery/',
            'friendship_status': 'https://www.instagram.com/api/v1/friendships/show/{user_id}/',
            'friendship_pending': 'https://www.instagram.com/api/v1/friendships/pending/{user_id}/',
            'friendship_approve': 'https://www.instagram.com/api/v1/friendships/approve/{user_id}/',
            'friendship_ignore': 'https://www.instagram.com/api/v1/friendships/ignore/{user_id}/',
            'friendship_deny': 'https://www.instagram.com/api/v1/friendships/deny/{user_id}/',
            'challenge': 'https://www.instagram.com/challenge/',
            'challenge_reset': 'https://www.instagram.com/challenge/reset/',
            'get_followers': 'https://www.instagram.com/api/v1/friendships/{user_id}/followers/',
            'get_following': 'https://www.instagram.com/api/v1/friendships/{user_id}/following/',
            'get_user_stories': 'https://www.instagram.com/api/v1/feed/user/{user_id}/story/',
            'get_highlights': 'https://www.instagram.com/api/v1/highlights/{user_id}/highlights_tray/',
            'get_collections': 'https://www.instagram.com/api/v1/collections/list/',
            'get_saved_posts': 'https://www.instagram.com/api/v1/feed/saved/posts/',
            'get_igtv': 'https://www.instagram.com/api/v1/igtv/suggested_channels/',
            'get_reels': 'https://www.instagram.com/api/v1/clips/home/',
            'get_suggested_users': 'https://www.instagram.com/api/v1/discover/chaining/',
            'get_top_live': 'https://www.instagram.com/api/v1/live/top-live/',
            'get_explore': 'https://www.instagram.com/api/v1/explore/',
            'get_hashtag_feed': 'https://www.instagram.com/api/v1/tags/{tag_name}/sections/',
            'get_location_feed': 'https://www.instagram.com/api/v1/locations/{location_id}/sections/',
            'get_notifications': 'https://www.instagram.com/api/v1/news/inbox/',
            'get_activity': 'https://www.instagram.com/api/v1/news/',
            'get_direct_threads': 'https://www.instagram.com/api/v1/direct_v2/inbox/',
            'get_direct_thread': 'https://www.instagram.com/api/v1/direct_v2/threads/{thread_id}/',
            'mark_thread_seen': 'https://www.instagram.com/api/v1/direct_v2/threads/{thread_id}/items/seen/',
            'mute_thread': 'https://www.instagram.com/api/v1/direct_v2/threads/{thread_id}/mute/',
            'unmute_thread': 'https://www.instagram.com/api/v1/direct_v2/threads/{thread_id}/unmute/',
            'leave_thread': 'https://www.instagram.com/api/v1/direct_v2/threads/{thread_id}/leave/',
            'delete_thread': 'https://www.instagram.com/api/v1/direct_v2/threads/{thread_id}/delete/',
            'get_media_comments': 'https://www.instagram.com/api/v1/media/{media_id}/comments/',
            'get_comment_replies': 'https://www.instagram.com/api/v1/media/{comment_id}/comment/replies/',
            'get_user_media': 'https://www.instagram.com/api/v1/feed/user/{user_id}/',
            'get_media_likers': 'https://www.instagram.com/api/v1/media/{media_id}/likers/',
            'get_story_viewers': 'https://www.instagram.com/api/v1/media/{media_id}/story_viewers/',
            'get_highlight_viewers': 'https://www.instagram.com/api/v1/highlights/{highlight_id}/story_viewers/',
            'get_live_viewers': 'https://www.instagram.com/api/v1/live/{broadcast_id}/get_viewer_list/',
            'get_account_stats': 'https://www.instagram.com/api/v1/accounts/current_user/?edit=true',
            'get_business_info': 'https://www.instagram.com/api/v1/business/account/',
            'get_creator_info': 'https://www.instagram.com/api/v1/creator/dashboard/',
            'get_insights': 'https://www.instagram.com/api/v1/insights/account/',
            'get_media_insights': 'https://www.instagram.com/api/v1/insights/media/{media_id}/',
            'get_audience_insights': 'https://www.instagram.com/api/v1/insights/account/audience/',
            'get_content_insights': 'https://www.instagram.com/api/v1/insights/content/',
            'get_activity_insights': 'https://www.instagram.com/api/v1/insights/activity/',
        }
        
        self.app_ids = [
            '936619743392459',  # Main Instagram app ID
            '1217981644879628',  # Alternative app ID 1
            '123456789012345',   # Alternative app ID 2
        ]
        
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        ]
        
        self.x_ig_www_claims = [
            'hmac.AR1qzeEVPBuPPsJxBMlPlU19lLRm0LG3bSnly_p3mz0aRW2P',
            'hmac.AR3z2eEVPBuPPsJxBMlPlU19lLRm0LG3bSnly_p3mz0aRW2P',
            'hmac.AR5z4eEVPBuPPsJxBMlPlU19lLRm0LG3bSnly_p3mz0aRW2P',
        ]
        
        self.last_updated = datetime.now()
        self.update_interval = 3600  # Update every hour
        self.csrf_token = None
        self.rollout_hash = None
        
    def update_api_endpoints(self):
        """Check and update API endpoints if needed"""
        current_time = datetime.now()
        if (current_time - self.last_updated).seconds < self.update_interval:
            return
            
        try:
            print(f"{Fore.YELLOW}🔄 Checking for Instagram API updates...{Style.RESET_ALL}")
            
            # Get the main page to extract new endpoints
            response = requests.get("https://www.instagram.com/")
            
            # Extract CSRF token
            csrf_token = re.search(r'"csrf_token":"(.*?)"', response.text)
            if csrf_token:
                self.csrf_token = csrf_token.group(1)
            
            # Extract rollout hash
            rollout_hash = re.search(r'"rollout_hash":"(.*?)"', response.text)
            if rollout_hash:
                self.rollout_hash = rollout_hash.group(1)
            
            # Extract bundle data
            bundle_data = re.search(r'<script type="text/javascript">window\._sharedData\s*=\s*(.*?);</script>', response.text)
            if bundle_data:
                try:
                    shared_data = json.loads(bundle_data.group(1))
                    # Extract any new endpoints or parameters
                    if 'qe' in shared_data and 'experiments' in shared_data['qe']:
                        # Update with any new experiment data
                        pass
                except:
                    pass
            
            # Extract additional JS data
            js_data = re.search(r'<script type="text/javascript">window\.__additionalDataLoaded\(\'feed\',\s*(.*?)\);</script>', response.text)
            if js_data:
                try:
                    additional_data = json.loads(js_data.group(1))
                    # Update with any additional data
                    pass
                except:
                    pass
            
            self.last_updated = current_time
            print(f"{Fore.GREEN}✅ API endpoints updated successfully{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error updating API endpoints: {str(e)}{Style.RESET_ALL}")
    
    def get_random_app_id(self):
        """Get a random app ID"""
        return random.choice(self.app_ids)
    
    def get_random_user_agent(self):
        """Get a random user agent"""
        return random.choice(self.user_agents)
    
    def get_random_x_ig_www_claim(self):
        """Get a random X-IG-WWW-Claim value"""
        return random.choice(self.x_ig_www_claims)
    
    def generate_device_id(self):
        """Generate a random device ID"""
        return str(uuid.uuid4())
    
    def generate_adid(self):
        """Generate a random advertising ID"""
        return str(uuid.uuid4())
    
    def generate_android_id(self):
        """Generate a random Android ID"""
        return "android-" + hashlib.md5(str(random.random()).encode()).hexdigest()[:16]
    
    def get_asbd_id(self):
        """Generate a random ASBD ID"""
        return str(random.randint(30000, 79999))
    
    def get_ig_android_id(self):
        """Generate a random IG Android ID"""
        return str(random.randint(1000000000, 9999999999))
    
    def get_ig_android_ua(self):
        """Generate a random IG Android User Agent"""
        versions = ["165.0.0.27.123", "166.0.0.28.124", "167.0.0.29.125"]
        android_versions = ["9", "10", "11", "12"]
        devices = ["SM-G950F", "SM-G960F", "SM-G965F", "SM-G970F", "SM-G975F"]
        
        version = random.choice(versions)
        android_version = random.choice(android_versions)
        device = random.choice(devices)
        
        return f"Instagram {version} Android ({android_version}/{device}; dpi 420; 1080x1920; samsung; {device}; sm_exynos9810; en_US; 165022042)"

class InstagramSession:
    def __init__(self, username, password, api_updater):
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.success_count = 0
        self.failure_count = 0
        self.csrftoken = None
        self.cookies = None
        self.lock = threading.Lock()
        self.api_updater = api_updater
        self.user_id = None
        self.is_active = False
        self.last_activity = time.time()
        self.challenge_url = None
        self.challenge_data = None
        self.account_info = {}
        
    def login(self):
        """Login to Instagram using username and password with improved challenge handling"""
        print(f"{Fore.YELLOW}🔄 Logging in as {self.username}...{Style.RESET_ALL}")
        
        try:
            # Update API endpoints before login
            self.api_updater.update_api_endpoints()
            
            # Get initial page to get CSRF token
            response = self.session.get("https://www.instagram.com/")
            csrf_token_match = re.search(r'"csrf_token":"(.*?)"', response.text)
            if csrf_token_match:
                self.csrftoken = csrf_token_match.group(1)
            else:
                print(f"{Fore.RED}❌ Could not extract CSRF token{Style.RESET_ALL}")
                return False
            
            # Prepare login data with improved format
            login_data = {
                'username': self.username,
                'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{self.password}',
                'queryParams': {},
                'optIntoOneTap': 'false',
                'stopDeletion': 'false',
                'trustedDevice': 'false',
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'X-CSRFToken': self.csrftoken,
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': 'https://www.instagram.com/',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://www.instagram.com',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }
            
            # Send login request
            response = self.session.post(
                self.api_updater.api_endpoints['login'],
                headers=headers,
                data=login_data
            )
            
            # Check if response is valid JSON
            try:
                response_json = response.json()
            except:
                print(f"{Fore.RED}❌ Invalid response from server{Style.RESET_ALL}")
                return False
            
            # Check if login was successful
            if response_json.get('authenticated') or response_json.get('user'):
                print(f"{Fore.GREEN}✅ Login successful!{Style.RESET_ALL}")
                self.csrftoken = self.csrftoken
                self.cookies = self.session.cookies.get_dict()
                self.is_active = True
                
                # Get user ID
                if 'userId' in response_json:
                    self.user_id = response_json['userId']
                elif 'user' in response_json and 'pk' in response_json['user']:
                    self.user_id = response_json['user']['pk']
                
                # Get account info
                self.get_account_info()
                
                return True
            
            # Check if there's a challenge
            elif 'challenge' in response_json:
                print(f"{Fore.YELLOW}⚠️ Challenge required!{Style.RESET_ALL}")
                challenge_data = response_json['challenge']
                self.challenge_url = challenge_data.get('url')
                self.challenge_data = challenge_data
                
                # Handle the challenge
                return self.handle_challenge()
            
            # Login failed with error message
            else:
                error_message = response_json.get('message', 'Unknown error')
                print(f"{Fore.RED}❌ Login failed! {error_message}{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Login error: {str(e)}{Style.RESET_ALL}")
            return False
    
    def handle_challenge(self):
        """Handle Instagram login challenges with improved methods"""
        try:
            print(f"{Fore.YELLOW}🔒 Handling challenge...{Style.RESET_ALL}")
            
            # Get the challenge page
            challenge_response = self.session.get(self.challenge_url)
            
            # Extract challenge type from the response
            if 'two_factor' in challenge_response.text.lower():
                print(f"{Fore.YELLOW}📱 Two-factor authentication required{Style.RESET_ALL}")
                return self.handle_two_factor()
            elif 'email_verification' in challenge_response.text.lower() or 'email verification' in challenge_response.text.lower():
                print(f"{Fore.YELLOW}✉️ Email verification required{Style.RESET_ALL}")
                return self.handle_email_verification()
            elif 'phone_verification' in challenge_response.text.lower():
                print(f"{Fore.YELLOW}📞 Phone verification required{Style.RESET_ALL}")
                return self.handle_phone_verification()
            else:
                print(f"{Fore.YELLOW}❓ Unknown challenge type{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Please complete the challenge manually in your browser.{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Challenge URL: {self.challenge_url}{Style.RESET_ALL}")
                
                input(f"{Fore.YELLOW}Press Enter after completing the challenge...{Style.RESET_ALL}")
                
                # Check if login was successful after manual challenge completion
                check_response = self.session.get("https://www.instagram.com/")
                if 'logout' in check_response.text or self.username in check_response.text:
                    print(f"{Fore.GREEN}✅ Challenge completed successfully!{Style.RESET_ALL}")
                    self.cookies = self.session.cookies.get_dict()
                    self.is_active = True
                    
                    # Get user ID
                    user_id_match = re.search(r'"id":"(\d+)"', check_response.text)
                    if user_id_match:
                        self.user_id = user_id_match.group(1)
                    
                    # Get account info
                    self.get_account_info()
                    
                    return True
                else:
                    print(f"{Fore.RED}❌ Challenge completion failed!{Style.RESET_ALL}")
                    return False
                    
        except Exception as e:
            print(f"{Fore.RED}❌ Error handling challenge: {str(e)}{Style.RESET_ALL}")
            return False
    
    def handle_two_factor(self):
        """Handle two-factor authentication challenge with improved method"""
        try:
            # Get the two-factor challenge page
            two_factor_url = f"{self.challenge_url}/"
            response = self.session.get(two_factor_url)
            
            # Extract the two-factor form data
            csrf_token_match = re.search(r'"csrf_token":"(.*?)"', response.text)
            if csrf_token_match:
                csrf_token = csrf_token_match.group(1)
            else:
                print(f"{Fore.RED}❌ Could not extract CSRF token for two-factor{Style.RESET_ALL}")
                return False
            
            # Ask for the two-factor code
            two_factor_code = input(f"{Fore.CYAN}Enter two-factor authentication code: {Style.RESET_ALL}")
            
            # Prepare two-factor verification data
            two_factor_data = {
                'csrfmiddlewaretoken': csrf_token,
                'verification_code': two_factor_code,
                'trust_device': 'on',
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'Referer': two_factor_url,
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://www.instagram.com',
            }
            
            # Send two-factor verification request
            response = self.session.post(
                two_factor_url,
                headers=headers,
                data=two_factor_data
            )
            
            # Check if two-factor verification was successful
            if 'two_factor' not in response.text.lower() and 'verification_code' not in response.text.lower():
                print(f"{Fore.GREEN}✅ Two-factor authentication successful!{Style.RESET_ALL}")
                self.cookies = self.session.cookies.get_dict()
                self.is_active = True
                
                # Get user ID
                user_id_match = re.search(r'"id":"(\d+)"', response.text)
                if user_id_match:
                    self.user_id = user_id_match.group(1)
                
                # Get account info
                self.get_account_info()
                
                return True
            else:
                print(f"{Fore.RED}❌ Two-factor authentication failed!{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error handling two-factor: {str(e)}{Style.RESET_ALL}")
            return False
    
    def handle_email_verification(self):
        """Handle email verification challenge with improved method"""
        try:
            # Get the email verification page
            email_url = f"{self.challenge_url}/"
            response = self.session.get(email_url)
            
            # Extract the email verification form data
            csrf_token_match = re.search(r'"csrf_token":"(.*?)"', response.text)
            if csrf_token_match:
                csrf_token = csrf_token_match.group(1)
            else:
                print(f"{Fore.RED}❌ Could not extract CSRF token for email verification{Style.RESET_ALL}")
                return False
            
            # Ask for the email verification code
            email_code = input(f"{Fore.CYAN}Enter email verification code: {Style.RESET_ALL}")
            
            # Prepare email verification data
            email_data = {
                'csrfmiddlewaretoken': csrf_token,
                'verification_code': email_code,
                'trust_device': 'on',
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'Referer': email_url,
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://www.instagram.com',
            }
            
            # Send email verification request
            response = self.session.post(
                email_url,
                headers=headers,
                data=email_data
            )
            
            # Check if email verification was successful
            if 'email_verification' not in response.text.lower() and 'verification_code' not in response.text.lower():
                print(f"{Fore.GREEN}✅ Email verification successful!{Style.RESET_ALL}")
                self.cookies = self.session.cookies.get_dict()
                self.is_active = True
                
                # Get user ID
                user_id_match = re.search(r'"id":"(\d+)"', response.text)
                if user_id_match:
                    self.user_id = user_id_match.group(1)
                
                # Get account info
                self.get_account_info()
                
                return True
            else:
                print(f"{Fore.RED}❌ Email verification failed!{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error handling email verification: {str(e)}{Style.RESET_ALL}")
            return False
    
    def handle_phone_verification(self):
        """Handle phone verification challenge with improved method"""
        try:
            # Get the phone verification page
            phone_url = f"{self.challenge_url}/"
            response = self.session.get(phone_url)
            
            # Extract the phone verification form data
            csrf_token_match = re.search(r'"csrf_token":"(.*?)"', response.text)
            if csrf_token_match:
                csrf_token = csrf_token_match.group(1)
            else:
                print(f"{Fore.RED}❌ Could not extract CSRF token for phone verification{Style.RESET_ALL}")
                return False
            
            # Ask for the phone verification code
            phone_code = input(f"{Fore.CYAN}Enter phone verification code: {Style.RESET_ALL}")
            
            # Prepare phone verification data
            phone_data = {
                'csrfmiddlewaretoken': csrf_token,
                'verification_code': phone_code,
                'trust_device': 'on',
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'Referer': phone_url,
                'X-CSRFToken': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://www.instagram.com',
            }
            
            # Send phone verification request
            response = self.session.post(
                phone_url,
                headers=headers,
                data=phone_data
            )
            
            # Check if phone verification was successful
            if 'phone_verification' not in response.text.lower() and 'verification_code' not in response.text.lower():
                print(f"{Fore.GREEN}✅ Phone verification successful!{Style.RESET_ALL}")
                self.cookies = self.session.cookies.get_dict()
                self.is_active = True
                
                # Get user ID
                user_id_match = re.search(r'"id":"(\d+)"', response.text)
                if user_id_match:
                    self.user_id = user_id_match.group(1)
                
                # Get account info
                self.get_account_info()
                
                return True
            else:
                print(f"{Fore.RED}❌ Phone verification failed!{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error handling phone verification: {str(e)}{Style.RESET_ALL}")
            return False
    
    def get_account_info(self):
        """Get detailed account information"""
        print(f"{Fore.YELLOW}📊 Getting account information...{Style.RESET_ALL}")
        
        try:
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                self.api_updater.api_endpoints['account_details'],
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                account_data = response.json()
                self.account_info = account_data
                
                # Display account info
                user = account_data.get('user', {})
                print(f"{Fore.GREEN}✅ Account information retrieved{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Username: {user.get('username', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Full Name: {user.get('full_name', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Bio: {user.get('biography', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Followers: {user.get('follower_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Following: {user.get('following_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Posts: {user.get('media_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Private: {'Yes' if user.get('is_private', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Verified: {'Yes' if user.get('is_verified', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Business: {'Yes' if user.get('is_business', False) else 'No'}{Style.RESET_ALL}")
                
                return True
            else:
                print(f"{Fore.RED}❌ Failed to get account information{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting account information: {str(e)}{Style.RESET_ALL}")
            return False
    
    def get_user_id(self, username):
        print(f"{Fore.YELLOW}🔍 Getting user ID for {username}...{Style.RESET_ALL}")
        url = f'{self.api_updater.api_endpoints["user_info"]}?username={username}'
        headers = {'x-ig-app-id': self.api_updater.get_random_app_id()}
        try:
            response = self.session.get(url, headers=headers)
            user_data = response.json().get('data', {}).get('user', {})
            user_id = user_data.get('id')
            if user_id:
                print(f"{Fore.GREEN}✅ User ID found: {user_id}{Style.RESET_ALL}")
                return user_id
            else:
                print(f"{Fore.RED}❌ User not found or account is private{Style.RESET_ALL}")
                return None
        except Exception as e:
            print(f'{Fore.RED}❌ Error getting user ID: {str(e)}{Style.RESET_ALL}')
            return None
    
    def get_user_info(self, username):
        print(f"{Fore.YELLOW}👤 Getting user information for {username}...{Style.RESET_ALL}")
        url = f'{self.api_updater.api_endpoints["user_info"]}?username={username}'
        headers = {'x-ig-app-id': self.api_updater.get_random_app_id()}
        try:
            response = self.session.get(url, headers=headers)
            user_data = response.json().get('data', {}).get('user', {})
            
            if user_data:
                print(f"{Fore.GREEN}✅ User information retrieved{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Username: {user_data.get('username', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Full Name: {user_data.get('full_name', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Bio: {user_data.get('biography', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Followers: {user_data.get('edge_followed_by', {}).get('count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Following: {user_data.get('edge_follow', {}).get('count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Posts: {user_data.get('edge_owner_to_timeline_media', {}).get('count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Private: {'Yes' if user_data.get('is_private', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Verified: {'Yes' if user_data.get('is_verified', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Business: {'Yes' if user_data.get('is_business_account', False) else 'No'}{Style.RESET_ALL}")
                
                return user_data
            else:
                print(f"{Fore.RED}❌ User not found or account is private{Style.RESET_ALL}")
                return None
        except Exception as e:
            print(f'{Fore.RED}❌ Error getting user information: {str(e)}{Style.RESET_ALL}')
            return None
    
    def get_user_followers(self, username, max_count=100):
        print(f"{Fore.YELLOW}👥 Getting followers for {username}...{Style.RESET_ALL}")
        
        user_id = self.get_user_id(username)
        if not user_id:
            return None
            
        followers = []
        next_max_id = None
        
        while len(followers) < max_count:
            try:
                url = f'{self.api_updater.api_endpoints["get_followers"].format(user_id=user_id)}'
                params = {
                    'rank_token': self.api_updater.generate_device_id(),
                    'max_id': next_max_id if next_max_id else ''
                }
                
                headers = {
                    'User-Agent': self.api_updater.get_random_user_agent(),
                    'x-csrftoken': self.csrftoken,
                    'x-ig-app-id': self.api_updater.get_random_app_id(),
                    'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                }
                
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    cookies=self.cookies
                )
                
                if response.status_code == 200:
                    data = response.json()
                    users = data.get('users', [])
                    
                    for user in users:
                        followers.append({
                            'username': user.get('username'),
                            'full_name': user.get('full_name'),
                            'user_id': user.get('pk'),
                            'is_private': user.get('is_private'),
                            'is_verified': user.get('is_verified'),
                            'profile_pic_url': user.get('profile_pic_url')
                        })
                        
                        if len(followers) >= max_count:
                            break
                    
                    next_max_id = data.get('next_max_id')
                    
                    if not next_max_id:
                        break
                        
                    # Add delay to avoid rate limiting
                    time.sleep(1)
                else:
                    print(f"{Fore.RED}❌ Failed to get followers{Style.RESET_ALL}")
                    break
                    
            except Exception as e:
                print(f"{Fore.RED}❌ Error getting followers: {str(e)}{Style.RESET_ALL}")
                break
        
        print(f"{Fore.GREEN}✅ Retrieved {len(followers)} followers{Style.RESET_ALL}")
        return followers
    
    def get_user_following(self, username, max_count=100):
        print(f"{Fore.YELLOW}👥 Getting following for {username}...{Style.RESET_ALL}")
        
        user_id = self.get_user_id(username)
        if not user_id:
            return None
            
        following = []
        next_max_id = None
        
        while len(following) < max_count:
            try:
                url = f'{self.api_updater.api_endpoints["get_following"].format(user_id=user_id)}'
                params = {
                    'rank_token': self.api_updater.generate_device_id(),
                    'max_id': next_max_id if next_max_id else ''
                }
                
                headers = {
                    'User-Agent': self.api_updater.get_random_user_agent(),
                    'x-csrftoken': self.csrftoken,
                    'x-ig-app-id': self.api_updater.get_random_app_id(),
                    'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                }
                
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    cookies=self.cookies
                )
                
                if response.status_code == 200:
                    data = response.json()
                    users = data.get('users', [])
                    
                    for user in users:
                        following.append({
                            'username': user.get('username'),
                            'full_name': user.get('full_name'),
                            'user_id': user.get('pk'),
                            'is_private': user.get('is_private'),
                            'is_verified': user.get('is_verified'),
                            'profile_pic_url': user.get('profile_pic_url')
                        })
                        
                        if len(following) >= max_count:
                            break
                    
                    next_max_id = data.get('next_max_id')
                    
                    if not next_max_id:
                        break
                        
                    # Add delay to avoid rate limiting
                    time.sleep(1)
                else:
                    print(f"{Fore.RED}❌ Failed to get following{Style.RESET_ALL}")
                    break
                    
            except Exception as e:
                print(f"{Fore.RED}❌ Error getting following: {str(e)}{Style.RESET_ALL}")
                break
        
        print(f"{Fore.GREEN}✅ Retrieved {len(following)} following{Style.RESET_ALL}")
        return following
    
    def get_user_media(self, username, max_count=20):
        print(f"{Fore.YELLOW}📸 Getting media for {username}...{Style.RESET_ALL}")
        
        user_id = self.get_user_id(username)
        if not user_id:
            return None
            
        media_list = []
        next_max_id = None
        
        while len(media_list) < max_count:
            try:
                url = f'{self.api_updater.api_endpoints["user_media"].format(user_id=user_id, max_id=next_max_id if next_max_id else "")}'
                
                headers = {
                    'User-Agent': self.api_updater.get_random_user_agent(),
                    'x-csrftoken': self.csrftoken,
                    'x-ig-app-id': self.api_updater.get_random_app_id(),
                    'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                }
                
                response = self.session.get(
                    url,
                    headers=headers,
                    cookies=self.cookies
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    for item in items:
                        media_list.append({
                            'id': item.get('id'),
                            'code': item.get('code'),
                            'caption': item.get('caption', {}).get('text', ''),
                            'media_type': item.get('media_type'),
                            'like_count': item.get('like_count', 0),
                            'comment_count': item.get('comment_count', 0),
                            'is_video': item.get('is_video', False),
                            'video_url': item.get('video_url'),
                            'image_versions': item.get('image_versions2', {}).get('candidates', [])
                        })
                        
                        if len(media_list) >= max_count:
                            break
                    
                    next_max_id = data.get('next_max_id')
                    
                    if not next_max_id:
                        break
                        
                    # Add delay to avoid rate limiting
                    time.sleep(1)
                else:
                    print(f"{Fore.RED}❌ Failed to get media{Style.RESET_ALL}")
                    break
                    
            except Exception as e:
                print(f"{Fore.RED}❌ Error getting media: {str(e)}{Style.RESET_ALL}")
                break
        
        print(f"{Fore.GREEN}✅ Retrieved {len(media_list)} media items{Style.RESET_ALL}")
        return media_list
    
    def like_media(self, media_id):
        print(f"{Fore.YELLOW}👍 Liking media {media_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['like'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Media liked successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to like media{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error liking media: {str(e)}{Style.RESET_ALL}")
            return False
    
    def unlike_media(self, media_id):
        print(f"{Fore.YELLOW}👎 Unliking media {media_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['unlike'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Media unliked successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to unlike media{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error unliking media: {str(e)}{Style.RESET_ALL}")
            return False
    
    def follow_user(self, user_id):
        print(f"{Fore.YELLOW}👤 Following user {user_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['follow'].format(user_id=user_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ User followed successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to follow user{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error following user: {str(e)}{Style.RESET_ALL}")
            return False
    
    def unfollow_user(self, user_id):
        print(f"{Fore.YELLOW}👤 Unfollowing user {user_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['unfollow'].format(user_id=user_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ User unfollowed successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to unfollow user{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error unfollowing user: {str(e)}{Style.RESET_ALL}")
            return False
    
    def comment_media(self, media_id, comment_text):
        print(f"{Fore.YELLOW}💬 Commenting on media {media_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['comment'].format(media_id=media_id)
            
            data = {
                'comment_text': comment_text
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Comment added successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to add comment{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error adding comment: {str(e)}{Style.RESET_ALL}")
            return False
    
    def send_direct_message(self, user_id, message_text):
        print(f"{Fore.YELLOW}✉️ Sending direct message to user {user_id}...{Style.RESET_ALL}")
        
        try:
            # First create a thread
            thread_url = self.api_updater.api_endpoints['direct_message']
            
            thread_data = {
                'recipient_users': f'[{user_id}]',
                'text': message_text
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                thread_url,
                headers=headers,
                data=thread_data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Direct message sent successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to send direct message{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error sending direct message: {str(e)}{Style.RESET_ALL}")
            return False
    
    def block_user(self, user_id):
        print(f"{Fore.YELLOW}🚫 Blocking user {user_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['block_user'].format(user_id=user_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ User blocked successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to block user{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error blocking user: {str(e)}{Style.RESET_ALL}")
            return False
    
    def unblock_user(self, user_id):
        print(f"{Fore.YELLOW}✅ Unblocking user {user_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['unblock_user'].format(user_id=user_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ User unblocked successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to unblock user{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error unblocking user: {str(e)}{Style.RESET_ALL}")
            return False
    
    def report_user(self, user_id, reason="spam"):
        print(f"{Fore.YELLOW}🚨 Reporting user {user_id}...{Style.RESET_ALL}")
        
        try:
            # First get report info
            report_info_url = self.api_updater.api_endpoints['report_info']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                report_info_url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                report_info = response.json()
                
                # Now submit the report
                submit_report_url = self.api_updater.api_endpoints['submit_report']
                
                report_data = {
                    'source_name': 'profile',
                    'user_id': user_id,
                    'reason': reason,
                    'frx_request': True,
                    'is_spam': True if reason == "spam" else False
                }
                
                response = self.session.post(
                    submit_report_url,
                    headers=headers,
                    data=report_data,
                    cookies=self.cookies
                )
                
                if response.status_code == 200:
                    print(f"{Fore.GREEN}✅ User reported successfully{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}❌ Failed to report user{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to get report info{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error reporting user: {str(e)}{Style.RESET_ALL}")
            return False
    
    def report_media(self, media_id, reason="spam"):
        print(f"{Fore.YELLOW}🚨 Reporting media {media_id}...{Style.RESET_ALL}")
        
        try:
            # First get report info
            report_info_url = self.api_updater.api_endpoints['report_info']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                report_info_url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                report_info = response.json()
                
                # Now submit the report
                submit_report_url = self.api_updater.api_endpoints['submit_report']
                
                report_data = {
                    'source_name': 'media',
                    'media_id': media_id,
                    'reason': reason,
                    'frx_request': True,
                    'is_spam': True if reason == "spam" else False
                }
                
                response = self.session.post(
                    submit_report_url,
                    headers=headers,
                    data=report_data,
                    cookies=self.cookies
                )
                
                if response.status_code == 200:
                    print(f"{Fore.GREEN}✅ Media reported successfully{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}❌ Failed to report media{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to get report info{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error reporting media: {str(e)}{Style.RESET_ALL}")
            return False
    
    def search_users(self, query, count=10):
        print(f"{Fore.YELLOW}🔍 Searching for users with query '{query}'...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['search']
            
            params = {
                'q': query,
                'count': count
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                
                print(f"{Fore.GREEN}✅ Found {len(users)} users{Style.RESET_ALL}")
                
                for user in users:
                    print(f"{Fore.CYAN}Username: {user.get('username', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Full Name: {user.get('full_name', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}User ID: {user.get('pk', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Profile Pic: {user.get('profile_pic_url', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Private: {'Yes' if user.get('is_private', False) else 'No'}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Verified: {'Yes' if user.get('is_verified', False) else 'No'}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return users
            else:
                print(f"{Fore.RED}❌ Failed to search users{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error searching users: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_hashtag_feed(self, hashtag, count=20):
        print(f"{Fore.YELLOW}📌 Getting hashtag feed for #{hashtag}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_hashtag_feed'].format(tag_name=hashtag)
            
            params = {
                'count': count
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                sections = data.get('sections', [])
                
                media_list = []
                
                for section in sections:
                    layout_content = section.get('layout_content', {})
                    medias = layout_content.get('medias', [])
                    
                    for media_item in medias:
                        media = media_item.get('media', {})
                        
                        media_list.append({
                            'id': media.get('id'),
                            'code': media.get('code'),
                            'caption': media.get('caption', ''),
                            'like_count': media.get('like_count', 0),
                            'comment_count': media.get('comment_count', 0),
                            'is_video': media.get('is_video', False),
                            'video_url': media.get('video_url'),
                            'image_versions': media.get('image_versions2', {}).get('candidates', [])
                        })
                
                print(f"{Fore.GREEN}✅ Retrieved {len(media_list)} media items for #{hashtag}{Style.RESET_ALL}")
                return media_list
            else:
                print(f"{Fore.RED}❌ Failed to get hashtag feed{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting hashtag feed: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_location_feed(self, location_id, count=20):
        print(f"{Fore.YELLOW}📍 Getting location feed for location {location_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_location_feed'].format(location_id=location_id)
            
            params = {
                'count': count
            }
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                sections = data.get('sections', [])
                
                media_list = []
                
                for section in sections:
                    layout_content = section.get('layout_content', {})
                    medias = layout_content.get('medias', [])
                    
                    for media_item in medias:
                        media = media_item.get('media', {})
                        
                        media_list.append({
                            'id': media.get('id'),
                            'code': media.get('code'),
                            'caption': media.get('caption', ''),
                            'like_count': media.get('like_count', 0),
                            'comment_count': media.get('comment_count', 0),
                            'is_video': media.get('is_video', False),
                            'video_url': media.get('video_url'),
                            'image_versions': media.get('image_versions2', {}).get('candidates', [])
                        })
                
                print(f"{Fore.GREEN}✅ Retrieved {len(media_list)} media items for location {location_id}{Style.RESET_ALL}")
                return media_list
            else:
                print(f"{Fore.RED}❌ Failed to get location feed{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting location feed: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_notifications(self):
        print(f"{Fore.YELLOW}🔔 Getting notifications...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_notifications']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                notifications = data.get('new_stories', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(notifications)} notifications{Style.RESET_ALL}")
                
                for notification in notifications:
                    print(f"{Fore.CYAN}Type: {notification.get('type', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Text: {notification.get('text', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Time: {notification.get('time', 'N/A')}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return notifications
            else:
                print(f"{Fore.RED}❌ Failed to get notifications{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting notifications: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_activity(self):
        print(f"{Fore.YELLOW}📋 Getting activity...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_activity']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                stories = data.get('stories', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(stories)} activity items{Style.RESET_ALL}")
                
                for story in stories:
                    print(f"{Fore.CYAN}Type: {story.get('type', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Text: {story.get('text', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Time: {story.get('time', 'N/A')}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return stories
            else:
                print(f"{Fore.RED}❌ Failed to get activity{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting activity: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_direct_threads(self):
        print(f"{Fore.YELLOW}📨 Getting direct message threads...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_direct_threads']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                threads = data.get('inbox', {}).get('threads', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(threads)} direct message threads{Style.RESET_ALL}")
                
                for thread in threads:
                    print(f"{Fore.CYAN}Thread ID: {thread.get('thread_id', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Thread Title: {thread.get('thread_title', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Users: {[user.get('username', 'N/A') for user in thread.get('users', [])]}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Last Activity: {thread.get('last_activity_at', 'N/A')}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return threads
            else:
                print(f"{Fore.RED}❌ Failed to get direct message threads{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting direct message threads: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_direct_thread(self, thread_id):
        print(f"{Fore.YELLOW}📨 Getting direct message thread {thread_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_direct_thread'].format(thread_id=thread_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                thread = data.get('thread', {})
                items = thread.get('items', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(items)} messages in thread {thread_id}{Style.RESET_ALL}")
                
                for item in items:
                    print(f"{Fore.CYAN}Item ID: {item.get('item_id', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Text: {item.get('text', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}User ID: {item.get('user_id', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Timestamp: {item.get('timestamp', 'N/A')}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return thread
            else:
                print(f"{Fore.RED}❌ Failed to get direct message thread{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting direct message thread: {str(e)}{Style.RESET_ALL}")
            return None
    
    def mark_thread_seen(self, thread_id):
        print(f"{Fore.YELLOW}👁️ Marking thread {thread_id} as seen...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['mark_thread_seen'].format(thread_id=thread_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Thread marked as seen{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to mark thread as seen{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error marking thread as seen: {str(e)}{Style.RESET_ALL}")
            return False
    
    def mute_thread(self, thread_id):
        print(f"{Fore.YELLOW}🔇 Muting thread {thread_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['mute_thread'].format(thread_id=thread_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Thread muted{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to mute thread{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error muting thread: {str(e)}{Style.RESET_ALL}")
            return False
    
    def unmute_thread(self, thread_id):
        print(f"{Fore.YELLOW}🔊 Unmuting thread {thread_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['unmute_thread'].format(thread_id=thread_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Thread unmuted{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to unmute thread{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error unmuting thread: {str(e)}{Style.RESET_ALL}")
            return False
    
    def leave_thread(self, thread_id):
        print(f"{Fore.YELLOW}🚪 Leaving thread {thread_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['leave_thread'].format(thread_id=thread_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Left thread{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to leave thread{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error leaving thread: {str(e)}{Style.RESET_ALL}")
            return False
    
    def delete_thread(self, thread_id):
        print(f"{Fore.YELLOW}🗑️ Deleting thread {thread_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['delete_thread'].format(thread_id=thread_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Thread deleted{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to delete thread{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error deleting thread: {str(e)}{Style.RESET_ALL}")
            return False
    
    def get_media_comments(self, media_id):
        print(f"{Fore.YELLOW}💬 Getting comments for media {media_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_media_comments'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                comments = data.get('comments', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(comments)} comments{Style.RESET_ALL}")
                
                for comment in comments:
                    print(f"{Fore.CYAN}Comment ID: {comment.get('pk', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Text: {comment.get('text', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}User ID: {comment.get('user', {}).get('pk', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Username: {comment.get('user', {}).get('username', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Timestamp: {comment.get('created_at', 'N/A')}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return comments
            else:
                print(f"{Fore.RED}❌ Failed to get comments{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting comments: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_comment_replies(self, comment_id):
        print(f"{Fore.YELLOW}💬 Getting replies for comment {comment_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_comment_replies'].format(comment_id=comment_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                replies = data.get('child_comments', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(replies)} replies{Style.RESET_ALL}")
                
                for reply in replies:
                    print(f"{Fore.CYAN}Reply ID: {reply.get('pk', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Text: {reply.get('text', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}User ID: {reply.get('user', {}).get('pk', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Username: {reply.get('user', {}).get('username', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Timestamp: {reply.get('created_at', 'N/A')}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return replies
            else:
                print(f"{Fore.RED}❌ Failed to get replies{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting replies: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_media_likers(self, media_id):
        print(f"{Fore.YELLOW}👍 Getting likers for media {media_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_media_likers'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(users)} likers{Style.RESET_ALL}")
                
                for user in users:
                    print(f"{Fore.CYAN}Username: {user.get('username', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Full Name: {user.get('full_name', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}User ID: {user.get('pk', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Profile Pic: {user.get('profile_pic_url', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Private: {'Yes' if user.get('is_private', False) else 'No'}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Verified: {'Yes' if user.get('is_verified', False) else 'No'}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return users
            else:
                print(f"{Fore.RED}❌ Failed to get likers{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting likers: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_story_viewers(self, media_id):
        print(f"{Fore.YELLOW}👁️ Getting story viewers for media {media_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_story_viewers'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(users)} story viewers{Style.RESET_ALL}")
                
                for user in users:
                    print(f"{Fore.CYAN}Username: {user.get('username', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Full Name: {user.get('full_name', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}User ID: {user.get('pk', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Profile Pic: {user.get('profile_pic_url', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Private: {'Yes' if user.get('is_private', False) else 'No'}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Verified: {'Yes' if user.get('is_verified', False) else 'No'}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return users
            else:
                print(f"{Fore.RED}❌ Failed to get story viewers{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting story viewers: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_highlight_viewers(self, highlight_id):
        print(f"{Fore.YELLOW}👁️ Getting highlight viewers for highlight {highlight_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_highlight_viewers'].format(highlight_id=highlight_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(users)} highlight viewers{Style.RESET_ALL}")
                
                for user in users:
                    print(f"{Fore.CYAN}Username: {user.get('username', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Full Name: {user.get('full_name', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}User ID: {user.get('pk', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Profile Pic: {user.get('profile_pic_url', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Private: {'Yes' if user.get('is_private', False) else 'No'}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Verified: {'Yes' if user.get('is_verified', False) else 'No'}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return users
            else:
                print(f"{Fore.RED}❌ Failed to get highlight viewers{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting highlight viewers: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_live_viewers(self, broadcast_id):
        print(f"{Fore.YELLOW}👁️ Getting live viewers for broadcast {broadcast_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_live_viewers'].format(broadcast_id=broadcast_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                
                print(f"{Fore.GREEN}✅ Retrieved {len(users)} live viewers{Style.RESET_ALL}")
                
                for user in users:
                    print(f"{Fore.CYAN}Username: {user.get('username', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Full Name: {user.get('full_name', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}User ID: {user.get('pk', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Profile Pic: {user.get('profile_pic_url', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Private: {'Yes' if user.get('is_private', False) else 'No'}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}Is Verified: {'Yes' if user.get('is_verified', False) else 'No'}{Style.RESET_ALL}")
                    print("-" * 50)
                
                return users
            else:
                print(f"{Fore.RED}❌ Failed to get live viewers{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting live viewers: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_account_stats(self):
        print(f"{Fore.YELLOW}📊 Getting account stats...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_account_stats']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                user = data.get('user', {})
                
                print(f"{Fore.GREEN}✅ Account stats retrieved{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Username: {user.get('username', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Full Name: {user.get('full_name', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Bio: {user.get('biography', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Followers: {user.get('follower_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Following: {user.get('following_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Posts: {user.get('media_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Private: {'Yes' if user.get('is_private', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Verified: {'Yes' if user.get('is_verified', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Business: {'Yes' if user.get('is_business', False) else 'No'}{Style.RESET_ALL}")
                
                return user
            else:
                print(f"{Fore.RED}❌ Failed to get account stats{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting account stats: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_business_info(self):
        print(f"{Fore.YELLOW}💼 Getting business info...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_business_info']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"{Fore.GREEN}✅ Business info retrieved{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Business Account: {'Yes' if data.get('is_business_account', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Business Category: {data.get('business_category_name', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Business Phone: {data.get('business_phone_number', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Business Email: {data.get('business_email', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Business Address: {data.get('business_address_json', {}).get('street_address', 'N/A')}{Style.RESET_ALL}")
                
                return data
            else:
                print(f"{Fore.RED}❌ Failed to get business info{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting business info: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_creator_info(self):
        print(f"{Fore.YELLOW}🎨 Getting creator info...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_creator_info']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"{Fore.GREEN}✅ Creator info retrieved{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Creator Account: {'Yes' if data.get('is_creator_account', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Creator Category: {data.get('creator_category_name', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Eligible for Branded Content: {'Yes' if data.get('is_eligible_for_branded_content', False) else 'No'}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Has Branded Content Partners: {'Yes' if data.get('has_branded_content_partners', False) else 'No'}{Style.RESET_ALL}")
                
                return data
            else:
                print(f"{Fore.RED}❌ Failed to get creator info{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting creator info: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_insights(self):
        print(f"{Fore.YELLOW}📈 Getting insights...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_insights']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"{Fore.GREEN}✅ Insights retrieved{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Account Type: {data.get('account_type', 'N/A')}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Followers: {data.get('followers_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Following: {data.get('following_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Posts: {data.get('posts_count', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Impressions: {data.get('impressions', {}).get('value', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Reach: {data.get('reach', {}).get('value', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Profile Views: {data.get('profile_views', {}).get('value', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Website Clicks: {data.get('website_clicks', {}).get('value', 0)}{Style.RESET_ALL}")
                
                return data
            else:
                print(f"{Fore.RED}❌ Failed to get insights{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting insights: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_media_insights(self, media_id):
        print(f"{Fore.YELLOW}📈 Getting media insights for {media_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_media_insights'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"{Fore.GREEN}✅ Media insights retrieved{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Impressions: {data.get('impressions', {}).get('value', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Reach: {data.get('reach', {}).get('value', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Saves: {data.get('saves', {}).get('value', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Likes: {data.get('likes', {}).get('value', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Comments: {data.get('comments', {}).get('value', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Shares: {data.get('shares', {}).get('value', 0)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Engagement Rate: {data.get('engagement_rate', {}).get('value', 0)}%{Style.RESET_ALL}")
                
                return data
            else:
                print(f"{Fore.RED}❌ Failed to get media insights{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting media insights: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_audience_insights(self):
        print(f"{Fore.YELLOW}👥 Getting audience insights...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_audience_insights']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"{Fore.GREEN}✅ Audience insights retrieved{Style.RESET_ALL}")
                
                # Top cities
                top_cities = data.get('top_cities', [])
                print(f"{Fore.CYAN}Top Cities:{Style.RESET_ALL}")
                for city in top_cities:
                    print(f"{Fore.CYAN}  {city.get('name', 'N/A')}: {city.get('value', 0)}{Style.RESET_ALL}")
                
                # Top countries
                top_countries = data.get('top_countries', [])
                print(f"{Fore.CYAN}Top Countries:{Style.RESET_ALL}")
                for country in top_countries:
                    print(f"{Fore.CYAN}  {country.get('name', 'N/A')}: {country.get('value', 0)}{Style.RESET_ALL}")
                
                # Age range
                age_range = data.get('age_range', {})
                print(f"{Fore.CYAN}Age Range:{Style.RESET_ALL}")
                for age, value in age_range.items():
                    print(f"{Fore.CYAN}  {age}: {value}{Style.RESET_ALL}")
                
                # Gender
                gender = data.get('gender', {})
                print(f"{Fore.CYAN}Gender:{Style.RESET_ALL}")
                for gen, value in gender.items():
                    print(f"{Fore.CYAN}  {gen}: {value}{Style.RESET_ALL}")
                
                return data
            else:
                print(f"{Fore.RED}❌ Failed to get audience insights{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting audience insights: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_content_insights(self):
        print(f"{Fore.YELLOW}📱 Getting content insights...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_content_insights']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"{Fore.GREEN}✅ Content insights retrieved{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Best Performing Content:{Style.RESET_ALL}")
                
                best_content = data.get('best_performing_content', [])
                for content in best_content:
                    print(f"{Fore.CYAN}  Media ID: {content.get('media_id', 'N/A')}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}  Impressions: {content.get('impressions', 0)}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}  Reach: {content.get('reach', 0)}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}  Engagement Rate: {content.get('engagement_rate', 0)}%{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}  Type: {content.get('media_type', 'N/A')}{Style.RESET_ALL}")
                    print("-" * 30)
                
                return data
            else:
                print(f"{Fore.RED}❌ Failed to get content insights{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting content insights: {str(e)}{Style.RESET_ALL}")
            return None
    
    def get_activity_insights(self):
        print(f"{Fore.YELLOW}📊 Getting activity insights...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['get_activity_insights']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.get(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"{Fore.GREEN}✅ Activity insights retrieved{Style.RESET_ALL}")
                
                # Follower activity
                follower_activity = data.get('follower_activity', {})
                print(f"{Fore.CYAN}Follower Activity:{Style.RESET_ALL}")
                for day, value in follower_activity.items():
                    print(f"{Fore.CYAN}  {day}: {value}{Style.RESET_ALL}")
                
                # Non-follower activity
                non_follower_activity = data.get('non_follower_activity', {})
                print(f"{Fore.CYAN}Non-Follower Activity:{Style.RESET_ALL}")
                for day, value in non_follower_activity.items():
                    print(f"{Fore.CYAN}  {day}: {value}{Style.RESET_ALL}")
                
                # Profile activity
                profile_activity = data.get('profile_activity', {})
                print(f"{Fore.CYAN}Profile Activity:{Style.RESET_ALL}")
                for day, value in profile_activity.items():
                    print(f"{Fore.CYAN}  {day}: {value}{Style.RESET_ALL}")
                
                return data
            else:
                print(f"{Fore.RED}❌ Failed to get activity insights{Style.RESET_ALL}")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error getting activity insights: {str(e)}{Style.RESET_ALL}")
            return False
    
    def upload_photo(self, image_path, caption=""):
        print(f"{Fore.YELLOW}📷 Uploading photo...{Style.RESET_ALL}")
        
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                print(f"{Fore.RED}❌ File not found: {image_path}{Style.RESET_ALL}")
                return False
            
            # Generate upload_id
            upload_id = str(int(time.time() * 1000))
            
            # Get upload parameters
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            # Upload the photo
            upload_url = self.api_updater.api_endpoints['upload_photo']
            
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
            
            files = {
                'photo': (os.path.basename(image_path), image_data, 'image/jpeg')
            }
            
            data = {
                'upload_id': upload_id,
                'media_type': 1,
                'image_compression': '{"lib_name":"jt","lib_version":"1.3.0","quality":"87"}'
            }
            
            response = self.session.post(
                upload_url,
                headers=headers,
                files=files,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                upload_data = response.json()
                
                if upload_data.get('status') == 'ok':
                    # Configure the photo
                    configure_url = self.api_updater.api_endpoints['configure']
                    
                    configure_data = {
                        'upload_id': upload_id,
                        'caption': caption,
                        'source_type': '4',
                        'device': {
                            'manufacturer': self.api_updater.get_ig_android_ua().split('(')[1].split(';')[1].strip(),
                            'model': self.api_updater.get_ig_android_ua().split('(')[1].split(';')[2].strip(),
                            'android_version': self.api_updater.get_ig_android_ua().split('(')[1].split('/')[0].strip(),
                            'android_release': self.api_updater.get_ig_android_ua().split('(')[1].split('/')[0].strip()
                        }
                    }
                    
                    response = self.session.post(
                        configure_url,
                        headers=headers,
                        data=configure_data,
                        cookies=self.cookies
                    )
                    
                    if response.status_code == 200:
                        configure_data = response.json()
                        
                        if configure_data.get('status') == 'ok':
                            media_id = configure_data.get('media', {}).get('pk')
                            print(f"{Fore.GREEN}✅ Photo uploaded successfully! Media ID: {media_id}{Style.RESET_ALL}")
                            return True
                        else:
                            print(f"{Fore.RED}❌ Failed to configure photo{Style.RESET_ALL}")
                            return False
                    else:
                        print(f"{Fore.RED}❌ Failed to configure photo{Style.RESET_ALL}")
                        return False
                else:
                    print(f"{Fore.RED}❌ Failed to upload photo{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to upload photo{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error uploading photo: {str(e)}{Style.RESET_ALL}")
            return False
    
    def upload_video(self, video_path, caption=""):
        print(f"{Fore.YELLOW}📹 Uploading video...{Style.RESET_ALL}")
        
        try:
            # Check if file exists
            if not os.path.exists(video_path):
                print(f"{Fore.RED}❌ File not found: {video_path}{Style.RESET_ALL}")
                return False
            
            # Generate upload_id
            upload_id = str(int(time.time() * 1000))
            
            # Get upload parameters
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            # Upload the video
            upload_url = self.api_updater.api_endpoints['upload_video']
            
            with open(video_path, 'rb') as video_file:
                video_data = video_file.read()
            
            files = {
                'video': (os.path.basename(video_path), video_data, 'video/mp4')
            }
            
            data = {
                'upload_id': upload_id,
                'media_type': 2,
                'video_compression': '{"lib_name":"jt","lib_version":"1.3.0","quality":"87"}'
            }
            
            response = self.session.post(
                upload_url,
                headers=headers,
                files=files,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                upload_data = response.json()
                
                if upload_data.get('status') == 'ok':
                    # Configure the video
                    configure_url = self.api_updater.api_endpoints['configure']
                    
                    configure_data = {
                        'upload_id': upload_id,
                        'caption': caption,
                        'source_type': '4',
                        'device': {
                            'manufacturer': self.api_updater.get_ig_android_ua().split('(')[1].split(';')[1].strip(),
                            'model': self.api_updater.get_ig_android_ua().split('(')[1].split(';')[2].strip(),
                            'android_version': self.api_updater.get_ig_android_ua().split('(')[1].split('/')[0].strip(),
                            'android_release': self.api_updater.get_ig_android_ua().split('(')[1].split('/')[0].strip()
                        }
                    }
                    
                    response = self.session.post(
                        configure_url,
                        headers=headers,
                        data=configure_data,
                        cookies=self.cookies
                    )
                    
                    if response.status_code == 200:
                        configure_data = response.json()
                        
                        if configure_data.get('status') == 'ok':
                            media_id = configure_data.get('media', {}).get('pk')
                            print(f"{Fore.GREEN}✅ Video uploaded successfully! Media ID: {media_id}{Style.RESET_ALL}")
                            return True
                        else:
                            print(f"{Fore.RED}❌ Failed to configure video{Style.RESET_ALL}")
                            return False
                    else:
                        print(f"{Fore.RED}❌ Failed to configure video{Style.RESET_ALL}")
                        return False
                else:
                    print(f"{Fore.RED}❌ Failed to upload video{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to upload video{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error uploading video: {str(e)}{Style.RESET_ALL}")
            return False
    
    def upload_reel(self, video_path, caption=""):
        print(f"{Fore.YELLOW}🎬 Uploading reel...{Style.RESET_ALL}")
        
        try:
            # Check if file exists
            if not os.path.exists(video_path):
                print(f"{Fore.RED}❌ File not found: {video_path}{Style.RESET_ALL}")
                return False
            
            # Generate upload_id
            upload_id = str(int(time.time() * 1000))
            
            # Get upload parameters
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            # Upload the reel
            upload_url = self.api_updater.api_endpoints['upload_reel']
            
            with open(video_path, 'rb') as video_file:
                video_data = video_file.read()
            
            files = {
                'video': (os.path.basename(video_path), video_data, 'video/mp4')
            }
            
            data = {
                'upload_id': upload_id,
                'media_type': 2,
                'video_compression': '{"lib_name":"jt","lib_version":"1.3.0","quality":"87"}'
            }
            
            response = self.session.post(
                upload_url,
                headers=headers,
                files=files,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                upload_data = response.json()
                
                if upload_data.get('status') == 'ok':
                    # Configure the reel
                    configure_url = self.api_updater.api_endpoints['configure']
                    
                    configure_data = {
                        'upload_id': upload_id,
                        'caption': caption,
                        'source_type': '4',
                        'device': {
                            'manufacturer': self.api_updater.get_ig_android_ua().split('(')[1].split(';')[1].strip(),
                            'model': self.api_updater.get_ig_android_ua().split('(')[1].split(';')[2].strip(),
                            'android_version': self.api_updater.get_ig_android_ua().split('(')[1].split('/')[0].strip(),
                            'android_release': self.api_updater.get_ig_android_ua().split('(')[1].split('/')[0].strip()
                        }
                    }
                    
                    response = self.session.post(
                        configure_url,
                        headers=headers,
                        data=configure_data,
                        cookies=self.cookies
                    )
                    
                    if response.status_code == 200:
                        configure_data = response.json()
                        
                        if configure_data.get('status') == 'ok':
                            media_id = configure_data.get('media', {}).get('pk')
                            print(f"{Fore.GREEN}✅ Reel uploaded successfully! Media ID: {media_id}{Style.RESET_ALL}")
                            return True
                        else:
                            print(f"{Fore.RED}❌ Failed to configure reel{Style.RESET_ALL}")
                            return False
                    else:
                        print(f"{Fore.RED}❌ Failed to configure reel{Style.RESET_ALL}")
                        return False
                else:
                    print(f"{Fore.RED}❌ Failed to upload reel{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to upload reel{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error uploading reel: {str(e)}{Style.RESET_ALL}")
            return False
    
    def delete_media(self, media_id):
        print(f"{Fore.YELLOW}🗑️ Deleting media {media_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['delete_media'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            data = {
                'media_id': media_id,
                'igtv_feed_preview': False
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Media deleted successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to delete media{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error deleting media: {str(e)}{Style.RESET_ALL}")
            return False
    
    def edit_media(self, media_id, caption=""):
        print(f"{Fore.YELLOW}✏️ Editing media {media_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['edit_media'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            data = {
                'caption_text': caption
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Media edited successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to edit media{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error editing media: {str(e)}{Style.RESET_ALL}")
            return False
    
    def create_highlight(self, media_ids, title="", cover_media_id=""):
        print(f"{Fore.YELLOW}✨ Creating highlight...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['create_highlight']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            data = {
                'media_ids': json.dumps(media_ids),
                'title': title,
                'cover_media_id': cover_media_id
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                highlight_data = response.json()
                
                if highlight_data.get('status') == 'ok':
                    highlight_id = highlight_data.get('highlight', {}).get('id')
                    print(f"{Fore.GREEN}✅ Highlight created successfully! Highlight ID: {highlight_id}{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}❌ Failed to create highlight{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to create highlight{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error creating highlight: {str(e)}{Style.RESET_ALL}")
            return False
    
    def edit_highlight(self, highlight_id, title="", cover_media_id="", add_media_ids=[], remove_media_ids=[]):
        print(f"{Fore.YELLOW}✏️ Editing highlight {highlight_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['edit_highlight'].format(highlight_id=highlight_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            data = {
                'title': title,
                'cover_media_id': cover_media_id,
                'added_media_ids': json.dumps(add_media_ids),
                'removed_media_ids': json.dumps(remove_media_ids)
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                highlight_data = response.json()
                
                if highlight_data.get('status') == 'ok':
                    print(f"{Fore.GREEN}✅ Highlight edited successfully{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}❌ Failed to edit highlight{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to edit highlight{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error editing highlight: {str(e)}{Style.RESET_ALL}")
            return False
    
    def delete_highlight(self, highlight_id):
        print(f"{Fore.YELLOW}🗑️ Deleting highlight {highlight_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['delete_highlight'].format(highlight_id=highlight_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Highlight deleted successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to delete highlight{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error deleting highlight: {str(e)}{Style.RESET_ALL}")
            return False
    
    def create_collection(self, name, media_ids=[]):
        print(f"{Fore.YELLOW}📚 Creating collection...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['create_collection']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            data = {
                'collection_name': name,
                'added_media_ids': json.dumps(media_ids)
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                collection_data = response.json()
                
                if collection_data.get('status') == 'ok':
                    collection_id = collection_data.get('collection', {}).get('id')
                    print(f"{Fore.GREEN}✅ Collection created successfully! Collection ID: {collection_id}{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}❌ Failed to create collection{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to create collection{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error creating collection: {str(e)}{Style.RESET_ALL}")
            return False
    
    def edit_collection(self, collection_id, name="", add_media_ids=[], remove_media_ids=[]):
        print(f"{Fore.YELLOW}✏️ Editing collection {collection_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['edit_collection'].format(collection_id=collection_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            data = {
                'collection_name': name,
                'added_media_ids': json.dumps(add_media_ids),
                'removed_media_ids': json.dumps(remove_media_ids)
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                collection_data = response.json()
                
                if collection_data.get('status') == 'ok':
                    print(f"{Fore.GREEN}✅ Collection edited successfully{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}❌ Failed to edit collection{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to edit collection{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error editing collection: {str(e)}{Style.RESET_ALL}")
            return False
    
    def delete_collection(self, collection_id):
        print(f"{Fore.YELLOW}🗑️ Deleting collection {collection_id}...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['delete_collection'].format(collection_id=collection_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Collection deleted successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to delete collection{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error deleting collection: {str(e)}{Style.RESET_ALL}")
            return False
    
    def save_to_collection(self, media_id, collection_id=""):
        print(f"{Fore.YELLOW}📚 Saving media {media_id} to collection...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['save_to_collection'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            data = {
                'collection_id': collection_id
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Media saved to collection successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to save media to collection{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error saving media to collection: {str(e)}{Style.RESET_ALL}")
            return False
    
    def unsave_from_collection(self, media_id):
        print(f"{Fore.YELLOW}📚 Unsaving media {media_id} from collection...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['unsave_from_collection'].format(media_id=media_id)
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Media unsaved from collection successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to unsave media from collection{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error unsaving media from collection: {str(e)}{Style.RESET_ALL}")
            return False
    
    def set_private(self):
        print(f"{Fore.YELLOW}🔒 Setting account to private...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['set_private']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Account set to private successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to set account to private{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error setting account to private: {str(e)}{Style.RESET_ALL}")
            return False
    
    def set_public(self):
        print(f"{Fore.YELLOW}🌍 Setting account to public...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['set_public']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                url,
                headers=headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✅ Account set to public successfully{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Failed to set account to public{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error setting account to public: {str(e)}{Style.RESET_ALL}")
            return False
    
    def change_password(self, old_password, new_password):
        print(f"{Fore.YELLOW}🔑 Changing password...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['change_password']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            data = {
                'old_password': old_password,
                'new_password1': new_password,
                'new_password2': new_password
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                password_data = response.json()
                
                if password_data.get('status') == 'ok':
                    print(f"{Fore.GREEN}✅ Password changed successfully{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}❌ Failed to change password{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to change password{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error changing password: {str(e)}{Style.RESET_ALL}")
            return False
    
    def update_profile(self, full_name="", biography="", phone_number="", email="", gender="1", website=""):
        print(f"{Fore.YELLOW}👤 Updating profile...{Style.RESET_ALL}")
        
        try:
            url = self.api_updater.api_endpoints['update_profile']
            
            headers = {
                'User-Agent': self.api_updater.get_random_user_agent(),
                'x-csrftoken': self.csrftoken,
                'x-ig-app-id': self.api_updater.get_random_app_id(),
                'x-ig-www-claim': self.api_updater.get_random_x_ig_www_claim(),
                'x-requested-with': 'XMLHttpRequest'
            }
            
            data = {
                'external_url': website,
                'gender': gender,
                'phone_number': phone_number,
                'username': self.username,
                'first_name': full_name,
                'biography': biography,
                'email': email
            }
            
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                profile_data = response.json()
                
                if profile_data.get('status') == 'ok':
                    print(f"{Fore.GREEN}✅ Profile updated successfully{Style.RESET_ALL}")
                    return True
                else:
                    print(f"{Fore.RED}❌ Failed to update profile{Style.RESET_ALL}")
                    return False
            else:
                print(f"{Fore.RED}❌ Failed to update profile{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error updating profile: {str(e)}{Style.RESET_ALL}")
            return False
    
    def logout(self):
        print(f"{Fore.YELLOW}🚪 Logging out...{Style.RESET_ALL}")
        
        try:
            # Clear session data
            self.session = requests.Session()
            self.csrftoken = None
            self.cookies = None
            self.is_active = False
            self.user_id = None
            self.challenge_url = None
            self.challenge_data = None
            self.account_info = {}
            
            print(f"{Fore.GREEN}✅ Logged out successfully{Style.RESET_ALL}")
            return True
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error logging out: {str(e)}{Style.RESET_ALL}")
            return False

class InstagramAutomationTool:
    def __init__(self):
        self.api_updater = InstagramAPIUpdater()
        self.active_sessions = {}
        self.current_session = None
        self.running = True
        
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_banner(self):
        """Display the tool banner"""
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL} {Fore.MAGENTA}ARMAAN MULTI TOOL FOR INSTAGRAM{Style.RESET_ALL} {Fore.CYAN}                                      ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL} {Fore.YELLOW}INSTAGRAM @EFKZW{Style.RESET_ALL} {Fore.CYAN}                                                          ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL} {Fore.YELLOW}TELEGRAM @ARMTR4N{Style.RESET_ALL} {Fore.CYAN}                                                          ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}")
        print()
    
    def display_header(self):
        """Display the tool header"""
        self.display_banner()
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}  Instagram Automation Tool v2.0{Style.RESET_ALL}")
        print(f"{Fore.CYAN}  Created with Python{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")
        print()
    
    def display_main_menu(self):
        """Display the main menu"""
        print(f"{Fore.YELLOW}Main Menu:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Account Management{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. User Actions{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Media Actions{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Direct Messaging{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Mass Actions{Style.RESET_ALL}")
        print(f"{Fore.GREEN}6. Account Settings{Style.RESET_ALL}")
        print(f"{Fore.GREEN}7. Insights & Analytics{Style.RESET_ALL}")
        print(f"{Fore.GREEN}8. Content Management{Style.RESET_ALL}")
        print(f"{Fore.GREEN}9. Update API Endpoints{Style.RESET_ALL}")
        print(f"{Fore.RED}0. Exit{Style.RESET_ALL}")
        print()
    
    def display_account_menu(self):
        """Display the account management menu"""
        print(f"{Fore.YELLOW}Account Management:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Login to Instagram{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Logout from Instagram{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Switch Account{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. View Account Info{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Mass Login{Style.RESET_ALL}")
        print(f"{Fore.RED}0. Back to Main Menu{Style.RESET_ALL}")
        print()
    
    def display_user_actions_menu(self):
        """Display the user actions menu"""
        print(f"{Fore.YELLOW}User Actions:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Get User Info{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Get User Followers{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Get User Following{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Get User Media{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Follow User{Style.RESET_ALL}")
        print(f"{Fore.GREEN}6. Unfollow User{Style.RESET_ALL}")
        print(f"{Fore.GREEN}7. Block User{Style.RESET_ALL}")
        print(f"{Fore.GREEN}8. Unblock User{Style.RESET_ALL}")
        print(f"{Fore.GREEN}9. Report User{Style.RESET_ALL}")
        print(f"{Fore.GREEN}10. Search Users{Style.RESET_ALL}")
        print(f"{Fore.RED}0. Back to Main Menu{Style.RESET_ALL}")
        print()
    
    def display_media_actions_menu(self):
        """Display the media actions menu"""
        print(f"{Fore.YELLOW}Media Actions:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Like Media{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Unlike Media{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Comment on Media{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Get Media Comments{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Get Comment Replies{Style.RESET_ALL}")
        print(f"{Fore.GREEN}6. Get Media Likers{Style.RESET_ALL}")
        print(f"{Fore.GREEN}7. Get Story Viewers{Style.RESET_ALL}")
        print(f"{Fore.GREEN}8. Get Highlight Viewers{Style.RESET_ALL}")
        print(f"{Fore.GREEN}9. Get Live Viewers{Style.RESET_ALL}")
        print(f"{Fore.GREEN}10. Report Media{Style.RESET_ALL}")
        print(f"{Fore.RED}0. Back to Main Menu{Style.RESET_ALL}")
        print()
    
    def display_direct_messaging_menu(self):
        """Display the direct messaging menu"""
        print(f"{Fore.YELLOW}Direct Messaging:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Get Direct Threads{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Get Direct Thread{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Send Direct Message{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Mark Thread as Seen{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Mute Thread{Style.RESET_ALL}")
        print(f"{Fore.GREEN}6. Unmute Thread{Style.RESET_ALL}")
        print(f"{Fore.GREEN}7. Leave Thread{Style.RESET_ALL}")
        print(f"{Fore.GREEN}8. Delete Thread{Style.RESET_ALL}")
        print(f"{Fore.RED}0. Back to Main Menu{Style.RESET_ALL}")
        print()
    
    def display_mass_actions_menu(self):
        """Display the mass actions menu"""
        print(f"{Fore.YELLOW}Mass Actions:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Mass Follow Users{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Mass Unfollow Users{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Mass Like Media{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Mass Comment on Media{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Mass Report Users{Style.RESET_ALL}")
        print(f"{Fore.GREEN}6. Mass Report Media{Style.RESET_ALL}")
        print(f"{Fore.GREEN}7. Mass Send Direct Messages{Style.RESET_ALL}")
        print(f"{Fore.RED}0. Back to Main Menu{Style.RESET_ALL}")
        print()
    
    def display_account_settings_menu(self):
        """Display the account settings menu"""
        print(f"{Fore.YELLOW}Account Settings:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Set Account to Private{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Set Account to Public{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Change Password{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Update Profile{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Get Notifications{Style.RESET_ALL}")
        print(f"{Fore.GREEN}6. Get Activity{Style.RESET_ALL}")
        print(f"{Fore.GREEN}7. Enable Two-Factor Authentication{Style.RESET_ALL}")
        print(f"{Fore.GREEN}8. Disable Two-Factor Authentication{Style.RESET_ALL}")
        print(f"{Fore.GREEN}9. Get Login Activity{Style.RESET_ALL}")
        print(f"{Fore.GREEN}10. Logout All Sessions{Style.RESET_ALL}")
        print(f"{Fore.RED}0. Back to Main Menu{Style.RESET_ALL}")
        print()
    
    def display_insights_menu(self):
        """Display the insights menu"""
        print(f"{Fore.YELLOW}Insights & Analytics:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Get Account Stats{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Get Business Info{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Get Creator Info{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Get Insights{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Get Media Insights{Style.RESET_ALL}")
        print(f"{Fore.GREEN}6. Get Audience Insights{Style.RESET_ALL}")
        print(f"{Fore.GREEN}7. Get Content Insights{Style.RESET_ALL}")
        print(f"{Fore.GREEN}8. Get Activity Insights{Style.RESET_ALL}")
        print(f"{Fore.GREEN}9. Get Hashtag Feed{Style.RESET_ALL}")
        print(f"{Fore.GREEN}10. Get Location Feed{Style.RESET_ALL}")
        print(f"{Fore.RED}0. Back to Main Menu{Style.RESET_ALL}")
        print()
    
    def display_content_management_menu(self):
        """Display the content management menu"""
        print(f"{Fore.YELLOW}Content Management:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Upload Photo{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Upload Video{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Upload Reel{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Delete Media{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Edit Media{Style.RESET_ALL}")
        print(f"{Fore.GREEN}6. Create Highlight{Style.RESET_ALL}")
        print(f"{Fore.GREEN}7. Edit Highlight{Style.RESET_ALL}")
        print(f"{Fore.GREEN}8. Delete Highlight{Style.RESET_ALL}")
        print(f"{Fore.GREEN}9. Create Collection{Style.RESET_ALL}")
        print(f"{Fore.GREEN}10. Edit Collection{Style.RESET_ALL}")
        print(f"{Fore.GREEN}11. Delete Collection{Style.RESET_ALL}")
        print(f"{Fore.GREEN}12. Save to Collection{Style.RESET_ALL}")
        print(f"{Fore.GREEN}13. Unsave from Collection{Style.RESET_ALL}")
        print(f"{Fore.RED}0. Back to Main Menu{Style.RESET_ALL}")
        print()
    
    def get_user_choice(self, max_option):
        """Get user choice from menu"""
        while True:
            try:
                choice = input(f"{Fore.CYAN}Enter your choice (0-{max_option}): {Style.RESET_ALL}")
                choice = int(choice)
                
                if 0 <= choice <= max_option:
                    return choice
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter a number between 0 and {max_option}.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
    
    def handle_account_management(self):
        """Handle account management menu"""
        while True:
            self.clear_screen()
            self.display_header()
            self.display_account_menu()
            
            choice = self.get_user_choice(5)
            
            if choice == 0:  # Back to main menu
                break
            elif choice == 1:  # Login to Instagram
                self.handle_login()
            elif choice == 2:  # Logout from Instagram
                self.handle_logout()
            elif choice == 3:  # Switch Account
                self.handle_switch_account()
            elif choice == 4:  # View Account Info
                self.handle_view_account_info()
            elif choice == 5:  # Mass Login
                self.handle_mass_login()
    
    def handle_login(self):
        """Handle login to Instagram"""
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Login to Instagram{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        password = input(f"{Fore.CYAN}Enter password: {Style.RESET_ALL}")
        
        # Create a new session
        session = InstagramSession(username, password, self.api_updater)
        
        # Try to login
        if session.login():
            self.active_sessions[username] = session
            self.current_session = session
            
            print(f"{Fore.GREEN}✅ Login successful!{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ Login failed!{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_logout(self):
        """Handle logout from Instagram"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Logout from Instagram{Style.RESET_ALL}")
        print()
        
        # Logout
        if self.current_session.logout():
            # Remove from active sessions
            if self.current_session.username in self.active_sessions:
                del self.active_sessions[self.current_session.username]
            
            self.current_session = None
            
            print(f"{Fore.GREEN}✅ Logout successful!{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ Logout failed!{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_switch_account(self):
        """Handle switch account"""
        if len(self.active_sessions) <= 1:
            print(f"{Fore.RED}❌ No other accounts to switch to!{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Switch Account{Style.RESET_ALL}")
        print()
        
        # Display available accounts
        print(f"{Fore.CYAN}Available accounts:{Style.RESET_ALL}")
        accounts = list(self.active_sessions.keys())
        
        for i, account in enumerate(accounts, 1):
            if account == self.current_session.username:
                print(f"{Fore.GREEN}{i}. {account} (Current){Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}{i}. {account}{Style.RESET_ALL}")
        
        print()
        
        # Get user choice
        while True:
            try:
                choice = input(f"{Fore.CYAN}Enter account number (1-{len(accounts)}): {Style.RESET_ALL}")
                choice = int(choice)
                
                if 1 <= choice <= len(accounts):
                    break
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and {len(accounts)}.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Switch account
        self.current_session = self.active_sessions[accounts[choice - 1]]
        
        print(f"{Fore.GREEN}✅ Switched to account: {self.current_session.username}{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_view_account_info(self):
        """Handle view account info"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Account Information{Style.RESET_ALL}")
        print()
        
        # Get account info
        self.current_session.get_account_info()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mass_login(self):
        """Handle mass login"""
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mass Login{Style.RESET_ALL}")
        print()
        
        # Get number of accounts
        while True:
            try:
                num_accounts = input(f"{Fore.CYAN}Enter number of accounts to login: {Style.RESET_ALL}")
                num_accounts = int(num_accounts)
                
                if num_accounts > 0:
                    break
                else:
                    print(f"{Fore.RED}Number of accounts must be greater than 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Get account credentials
        accounts = []
        for i in range(num_accounts):
            print(f"\n{Fore.CYAN}Account {i+1}:{Style.RESET_ALL}")
            username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
            password = input(f"{Fore.CYAN}Enter password: {Style.RESET_ALL}")
            accounts.append((username, password))
        
        # Login to all accounts
        print(f"\n{Fore.YELLOW}Logging in to {num_accounts} accounts...{Style.RESET_ALL}")
        
        success_count = 0
        for username, password in accounts:
            print(f"\n{Fore.YELLOW}Logging in as {username}...{Style.RESET_ALL}")
            
            # Create a new session
            session = InstagramSession(username, password, self.api_updater)
            
            # Try to login
            if session.login():
                self.active_sessions[username] = session
                if not self.current_session:
                    self.current_session = session
                
                success_count += 1
                print(f"{Fore.GREEN}✅ Login successful!{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}❌ Login failed!{Style.RESET_ALL}")
        
        print(f"\n{Fore.GREEN}Successfully logged in to {success_count} out of {num_accounts} accounts.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_user_actions(self):
        """Handle user actions menu"""
        while True:
            self.clear_screen()
            self.display_header()
            self.display_user_actions_menu()
            
            choice = self.get_user_choice(10)
            
            if choice == 0:  # Back to main menu
                break
            elif choice == 1:  # Get User Info
                self.handle_get_user_info()
            elif choice == 2:  # Get User Followers
                self.handle_get_user_followers()
            elif choice == 3:  # Get User Following
                self.handle_get_user_following()
            elif choice == 4:  # Get User Media
                self.handle_get_user_media()
            elif choice == 5:  # Follow User
                self.handle_follow_user()
            elif choice == 6:  # Unfollow User
                self.handle_unfollow_user()
            elif choice == 7:  # Block User
                self.handle_block_user()
            elif choice == 8:  # Unblock User
                self.handle_unblock_user()
            elif choice == 9:  # Report User
                self.handle_report_user()
            elif choice == 10:  # Search Users
                self.handle_search_users()
    
    def handle_get_user_info(self):
        """Handle get user info"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get User Information{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        
        # Get user info
        self.current_session.get_user_info(username)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_user_followers(self):
        """Handle get user followers"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get User Followers{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        
        # Get max count
        while True:
            try:
                max_count = input(f"{Fore.CYAN}Enter maximum number of followers to retrieve (default: 100): {Style.RESET_ALL}")
                if not max_count:
                    max_count = 100
                else:
                    max_count = int(max_count)
                
                if max_count > 0:
                    break
                else:
                    print(f"{Fore.RED}Maximum count must be greater than 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Get user followers
        self.current_session.get_user_followers(username, max_count)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_user_following(self):
        """Handle get user following"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get User Following{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        
        # Get max count
        while True:
            try:
                max_count = input(f"{Fore.CYAN}Enter maximum number of following to retrieve (default: 100): {Style.RESET_ALL}")
                if not max_count:
                    max_count = 100
                else:
                    max_count = int(max_count)
                
                if max_count > 0:
                    break
                else:
                    print(f"{Fore.RED}Maximum count must be greater than 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Get user following
        self.current_session.get_user_following(username, max_count)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_user_media(self):
        """Handle get user media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get User Media{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        
        # Get max count
        while True:
            try:
                max_count = input(f"{Fore.CYAN}Enter maximum number of media to retrieve (default: 20): {Style.RESET_ALL}")
                if not max_count:
                    max_count = 20
                else:
                    max_count = int(max_count)
                
                if max_count > 0:
                    break
                else:
                    print(f"{Fore.RED}Maximum count must be greater than 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Get user media
        self.current_session.get_user_media(username, max_count)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_follow_user(self):
        """Handle follow user"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Follow User{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        
        # Get user ID
        user_id = self.current_session.get_user_id(username)
        
        if user_id:
            # Follow user
            self.current_session.follow_user(user_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_unfollow_user(self):
        """Handle unfollow user"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Unfollow User{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        
        # Get user ID
        user_id = self.current_session.get_user_id(username)
        
        if user_id:
            # Unfollow user
            self.current_session.unfollow_user(user_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_block_user(self):
        """Handle block user"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Block User{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        
        # Get user ID
        user_id = self.current_session.get_user_id(username)
        
        if user_id:
            # Block user
            self.current_session.block_user(user_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_unblock_user(self):
        """Handle unblock user"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Unblock User{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        
        # Get user ID
        user_id = self.current_session.get_user_id(username)
        
        if user_id:
            # Unblock user
            self.current_session.unblock_user(user_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_report_user(self):
        """Handle report user"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Report User{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        
        # Get report reason
        print(f"{Fore.CYAN}Report reasons:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Spam{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Inappropriate Content{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Harassment or Bullying{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Hate Speech or Symbols{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. False Information{Style.RESET_ALL}")
        
        # Get user choice
        while True:
            try:
                choice = input(f"{Fore.CYAN}Enter report reason (1-5): {Style.RESET_ALL}")
                choice = int(choice)
                
                if 1 <= choice <= 5:
                    break
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and 5.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Map choice to reason
        reasons = {
            1: "spam",
            2: "inappropriate",
            3: "harassment",
            4: "hate_speech",
            5: "false_information"
        }
        
        reason = reasons[choice]
        
        # Get user ID
        user_id = self.current_session.get_user_id(username)
        
        if user_id:
            # Report user
            self.current_session.report_user(user_id, reason)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_search_users(self):
        """Handle search users"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Search Users{Style.RESET_ALL}")
        print()
        
        query = input(f"{Fore.CYAN}Enter search query: {Style.RESET_ALL}")
        
        # Get count
        while True:
            try:
                count = input(f"{Fore.CYAN}Enter number of results to retrieve (default: 10): {Style.RESET_ALL}")
                if not count:
                    count = 10
                else:
                    count = int(count)
                
                if count > 0:
                    break
                else:
                    print(f"{Fore.RED}Count must be greater than 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Search users
        self.current_session.search_users(query, count)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_media_actions(self):
        """Handle media actions menu"""
        while True:
            self.clear_screen()
            self.display_header()
            self.display_media_actions_menu()
            
            choice = self.get_user_choice(10)
            
            if choice == 0:  # Back to main menu
                break
            elif choice == 1:  # Like Media
                self.handle_like_media()
            elif choice == 2:  # Unlike Media
                self.handle_unlike_media()
            elif choice == 3:  # Comment on Media
                self.handle_comment_media()
            elif choice == 4:  # Get Media Comments
                self.handle_get_media_comments()
            elif choice == 5:  # Get Comment Replies
                self.handle_get_comment_replies()
            elif choice == 6:  # Get Media Likers
                self.handle_get_media_likers()
            elif choice == 7:  # Get Story Viewers
                self.handle_get_story_viewers()
            elif choice == 8:  # Get Highlight Viewers
                self.handle_get_highlight_viewers()
            elif choice == 9:  # Get Live Viewers
                self.handle_get_live_viewers()
            elif choice == 10:  # Report Media
                self.handle_report_media()
    
    def handle_like_media(self):
        """Handle like media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Like Media{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        
        # Like media
        self.current_session.like_media(media_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_unlike_media(self):
        """Handle unlike media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Unlike Media{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        
        # Unlike media
        self.current_session.unlike_media(media_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_comment_media(self):
        """Handle comment on media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Comment on Media{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        comment = input(f"{Fore.CYAN}Enter comment: {Style.RESET_ALL}")
        
        # Comment on media
        self.current_session.comment_media(media_id, comment)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_media_comments(self):
        """Handle get media comments"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Media Comments{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        
        # Get media comments
        self.current_session.get_media_comments(media_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_comment_replies(self):
        """Handle get comment replies"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Comment Replies{Style.RESET_ALL}")
        print()
        
        comment_id = input(f"{Fore.CYAN}Enter comment ID: {Style.RESET_ALL}")
        
        # Get comment replies
        self.current_session.get_comment_replies(comment_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_media_likers(self):
        """Handle get media likers"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Media Likers{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        
        # Get media likers
        self.current_session.get_media_likers(media_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_story_viewers(self):
        """Handle get story viewers"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Story Viewers{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        
        # Get story viewers
        self.current_session.get_story_viewers(media_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_highlight_viewers(self):
        """Handle get highlight viewers"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Highlight Viewers{Style.RESET_ALL}")
        print()
        
        highlight_id = input(f"{Fore.CYAN}Enter highlight ID: {Style.RESET_ALL}")
        
        # Get highlight viewers
        self.current_session.get_highlight_viewers(highlight_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_live_viewers(self):
        """Handle get live viewers"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Live Viewers{Style.RESET_ALL}")
        print()
        
        broadcast_id = input(f"{Fore.CYAN}Enter broadcast ID: {Style.RESET_ALL}")
        
        # Get live viewers
        self.current_session.get_live_viewers(broadcast_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_report_media(self):
        """Handle report media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Report Media{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        
        # Get report reason
        print(f"{Fore.CYAN}Report reasons:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Spam{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Nudity or Sexual Activity{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Hate Speech or Symbols{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. False Information{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Bullying or Harassment{Style.RESET_ALL}")
        
        # Get user choice
        while True:
            try:
                choice = input(f"{Fore.CYAN}Enter report reason (1-5): {Style.RESET_ALL}")
                choice = int(choice)
                
                if 1 <= choice <= 5:
                    break
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and 5.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Map choice to reason
        reasons = {
            1: "spam",
            2: "nudity",
            3: "hate_speech",
            4: "false_information",
            5: "harassment"
        }
        
        reason = reasons[choice]
        
        # Report media
        self.current_session.report_media(media_id, reason)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_direct_messaging(self):
        """Handle direct messaging menu"""
        while True:
            self.clear_screen()
            self.display_header()
            self.display_direct_messaging_menu()
            
            choice = self.get_user_choice(8)
            
            if choice == 0:  # Back to main menu
                break
            elif choice == 1:  # Get Direct Threads
                self.handle_get_direct_threads()
            elif choice == 2:  # Get Direct Thread
                self.handle_get_direct_thread()
            elif choice == 3:  # Send Direct Message
                self.handle_send_direct_message()
            elif choice == 4:  # Mark Thread as Seen
                self.handle_mark_thread_seen()
            elif choice == 5:  # Mute Thread
                self.handle_mute_thread()
            elif choice == 6:  # Unmute Thread
                self.handle_unmute_thread()
            elif choice == 7:  # Leave Thread
                self.handle_leave_thread()
            elif choice == 8:  # Delete Thread
                self.handle_delete_thread()
    
    def handle_get_direct_threads(self):
        """Handle get direct threads"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Direct Threads{Style.RESET_ALL}")
        print()
        
        # Get direct threads
        self.current_session.get_direct_threads()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_direct_thread(self):
        """Handle get direct thread"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Direct Thread{Style.RESET_ALL}")
        print()
        
        thread_id = input(f"{Fore.CYAN}Enter thread ID: {Style.RESET_ALL}")
        
        # Get direct thread
        self.current_session.get_direct_thread(thread_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_send_direct_message(self):
        """Handle send direct message"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Send Direct Message{Style.RESET_ALL}")
        print()
        
        username = input(f"{Fore.CYAN}Enter username: {Style.RESET_ALL}")
        message = input(f"{Fore.CYAN}Enter message: {Style.RESET_ALL}")
        
        # Get user ID
        user_id = self.current_session.get_user_id(username)
        
        if user_id:
            # Send direct message
            self.current_session.send_direct_message(user_id, message)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mark_thread_seen(self):
        """Handle mark thread seen"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mark Thread as Seen{Style.RESET_ALL}")
        print()
        
        thread_id = input(f"{Fore.CYAN}Enter thread ID: {Style.RESET_ALL}")
        
        # Mark thread as seen
        self.current_session.mark_thread_seen(thread_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mute_thread(self):
        """Handle mute thread"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mute Thread{Style.RESET_ALL}")
        print()
        
        thread_id = input(f"{Fore.CYAN}Enter thread ID: {Style.RESET_ALL}")
        
        # Mute thread
        self.current_session.mute_thread(thread_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_unmute_thread(self):
        """Handle unmute thread"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Unmute Thread{Style.RESET_ALL}")
        print()
        
        thread_id = input(f"{Fore.CYAN}Enter thread ID: {Style.RESET_ALL}")
        
        # Unmute thread
        self.current_session.unmute_thread(thread_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_leave_thread(self):
        """Handle leave thread"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Leave Thread{Style.RESET_ALL}")
        print()
        
        thread_id = input(f"{Fore.CYAN}Enter thread ID: {Style.RESET_ALL}")
        
        # Leave thread
        self.current_session.leave_thread(thread_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_delete_thread(self):
        """Handle delete thread"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Delete Thread{Style.RESET_ALL}")
        print()
        
        thread_id = input(f"{Fore.CYAN}Enter thread ID: {Style.RESET_ALL}")
        
        # Delete thread
        self.current_session.delete_thread(thread_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mass_actions(self):
        """Handle mass actions menu"""
        while True:
            self.clear_screen()
            self.display_header()
            self.display_mass_actions_menu()
            
            choice = self.get_user_choice(7)
            
            if choice == 0:  # Back to main menu
                break
            elif choice == 1:  # Mass Follow Users
                self.handle_mass_follow_users()
            elif choice == 2:  # Mass Unfollow Users
                self.handle_mass_unfollow_users()
            elif choice == 3:  # Mass Like Media
                self.handle_mass_like_media()
            elif choice == 4:  # Mass Comment on Media
                self.handle_mass_comment_media()
            elif choice == 5:  # Mass Report Users
                self.handle_mass_report_users()
            elif choice == 6:  # Mass Report Media
                self.handle_mass_report_media()
            elif choice == 7:  # Mass Send Direct Messages
                self.handle_mass_send_direct_messages()
    
    def handle_mass_follow_users(self):
        """Handle mass follow users"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mass Follow Users{Style.RESET_ALL}")
        print()
        
        # Get usernames
        usernames_input = input(f"{Fore.CYAN}Enter usernames (comma separated): {Style.RESET_ALL}")
        usernames = [username.strip() for username in usernames_input.split(',')]
        
        # Get delay
        while True:
            try:
                delay = input(f"{Fore.CYAN}Enter delay between actions in seconds (default: 5): {Style.RESET_ALL}")
                if not delay:
                    delay = 5
                else:
                    delay = int(delay)
                
                if delay >= 0:
                    break
                else:
                    print(f"{Fore.RED}Delay must be greater than or equal to 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Mass follow users
        success_count = 0
        for username in usernames:
            print(f"\n{Fore.YELLOW}Following {username}...{Style.RESET_ALL}")
            
            # Get user ID
            user_id = self.current_session.get_user_id(username)
            
            if user_id:
                # Follow user
                if self.current_session.follow_user(user_id):
                    success_count += 1
            
            # Delay
            if delay > 0:
                time.sleep(delay)
        
        print(f"\n{Fore.GREEN}Successfully followed {success_count} out of {len(usernames)} users.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mass_unfollow_users(self):
        """Handle mass unfollow users"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mass Unfollow Users{Style.RESET_ALL}")
        print()
        
        # Get usernames
        usernames_input = input(f"{Fore.CYAN}Enter usernames (comma separated): {Style.RESET_ALL}")
        usernames = [username.strip() for username in usernames_input.split(',')]
        
        # Get delay
        while True:
            try:
                delay = input(f"{Fore.CYAN}Enter delay between actions in seconds (default: 5): {Style.RESET_ALL}")
                if not delay:
                    delay = 5
                else:
                    delay = int(delay)
                
                if delay >= 0:
                    break
                else:
                    print(f"{Fore.RED}Delay must be greater than or equal to 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Mass unfollow users
        success_count = 0
        for username in usernames:
            print(f"\n{Fore.YELLOW}Unfollowing {username}...{Style.RESET_ALL}")
            
            # Get user ID
            user_id = self.current_session.get_user_id(username)
            
            if user_id:
                # Unfollow user
                if self.current_session.unfollow_user(user_id):
                    success_count += 1
            
            # Delay
            if delay > 0:
                time.sleep(delay)
        
        print(f"\n{Fore.GREEN}Successfully unfollowed {success_count} out of {len(usernames)} users.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mass_like_media(self):
        """Handle mass like media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mass Like Media{Style.RESET_ALL}")
        print()
        
        # Get media IDs
        media_ids_input = input(f"{Fore.CYAN}Enter media IDs (comma separated): {Style.RESET_ALL}")
        media_ids = [media_id.strip() for media_id in media_ids_input.split(',')]
        
        # Get delay
        while True:
            try:
                delay = input(f"{Fore.CYAN}Enter delay between actions in seconds (default: 5): {Style.RESET_ALL}")
                if not delay:
                    delay = 5
                else:
                    delay = int(delay)
                
                if delay >= 0:
                    break
                else:
                    print(f"{Fore.RED}Delay must be greater than or equal to 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Mass like media
        success_count = 0
        for media_id in media_ids:
            print(f"\n{Fore.YELLOW}Liking media {media_id}...{Style.RESET_ALL}")
            
            # Like media
            if self.current_session.like_media(media_id):
                success_count += 1
            
            # Delay
            if delay > 0:
                time.sleep(delay)
        
        print(f"\n{Fore.GREEN}Successfully liked {success_count} out of {len(media_ids)} media items.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mass_comment_media(self):
        """Handle mass comment on media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mass Comment on Media{Style.RESET_ALL}")
        print()
        
        # Get media IDs
        media_ids_input = input(f"{Fore.CYAN}Enter media IDs (comma separated): {Style.RESET_ALL}")
        media_ids = [media_id.strip() for media_id in media_ids_input.split(',')]
        
        # Get comment
        comment = input(f"{Fore.CYAN}Enter comment: {Style.RESET_ALL}")
        
        # Get delay
        while True:
            try:
                delay = input(f"{Fore.CYAN}Enter delay between actions in seconds (default: 5): {Style.RESET_ALL}")
                if not delay:
                    delay = 5
                else:
                    delay = int(delay)
                
                if delay >= 0:
                    break
                else:
                    print(f"{Fore.RED}Delay must be greater than or equal to 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Mass comment on media
        success_count = 0
        for media_id in media_ids:
            print(f"\n{Fore.YELLOW}Commenting on media {media_id}...{Style.RESET_ALL}")
            
            # Comment on media
            if self.current_session.comment_media(media_id, comment):
                success_count += 1
            
            # Delay
            if delay > 0:
                time.sleep(delay)
        
        print(f"\n{Fore.GREEN}Successfully commented on {success_count} out of {len(media_ids)} media items.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mass_report_users(self):
        """Handle mass report users"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mass Report Users{Style.RESET_ALL}")
        print()
        
        # Get usernames
        usernames_input = input(f"{Fore.CYAN}Enter usernames (comma separated): {Style.RESET_ALL}")
        usernames = [username.strip() for username in usernames_input.split(',')]
        
        # Get report reason
        print(f"{Fore.CYAN}Report reasons:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Spam{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Inappropriate Content{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Harassment or Bullying{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. Hate Speech or Symbols{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. False Information{Style.RESET_ALL}")
        
        # Get user choice
        while True:
            try:
                choice = input(f"{Fore.CYAN}Enter report reason (1-5): {Style.RESET_ALL}")
                choice = int(choice)
                
                if 1 <= choice <= 5:
                    break
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and 5.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Map choice to reason
        reasons = {
            1: "spam",
            2: "inappropriate",
            3: "harassment",
            4: "hate_speech",
            5: "false_information"
        }
        
        reason = reasons[choice]
        
        # Get delay
        while True:
            try:
                delay = input(f"{Fore.CYAN}Enter delay between actions in seconds (default: 10): {Style.RESET_ALL}")
                if not delay:
                    delay = 10
                else:
                    delay = int(delay)
                
                if delay >= 0:
                    break
                else:
                    print(f"{Fore.RED}Delay must be greater than or equal to 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Mass report users
        success_count = 0
        for username in usernames:
            print(f"\n{Fore.YELLOW}Reporting {username}...{Style.RESET_ALL}")
            
            # Get user ID
            user_id = self.current_session.get_user_id(username)
            
            if user_id:
                # Report user
                if self.current_session.report_user(user_id, reason):
                    success_count += 1
            
            # Delay
            if delay > 0:
                time.sleep(delay)
        
        print(f"\n{Fore.GREEN}Successfully reported {success_count} out of {len(usernames)} users.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mass_report_media(self):
        """Handle mass report media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mass Report Media{Style.RESET_ALL}")
        print()
        
        # Get media IDs
        media_ids_input = input(f"{Fore.CYAN}Enter media IDs (comma separated): {Style.RESET_ALL}")
        media_ids = [media_id.strip() for media_id in media_ids_input.split(',')]
        
        # Get report reason
        print(f"{Fore.CYAN}Report reasons:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Spam{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Nudity or Sexual Activity{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Hate Speech or Symbols{Style.RESET_ALL}")
        print(f"{Fore.GREEN}4. False Information{Style.RESET_ALL}")
        print(f"{Fore.GREEN}5. Bullying or Harassment{Style.RESET_ALL}")
        
        # Get user choice
        while True:
            try:
                choice = input(f"{Fore.CYAN}Enter report reason (1-5): {Style.RESET_ALL}")
                choice = int(choice)
                
                if 1 <= choice <= 5:
                    break
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and 5.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Map choice to reason
        reasons = {
            1: "spam",
            2: "nudity",
            3: "hate_speech",
            4: "false_information",
            5: "harassment"
        }
        
        reason = reasons[choice]
        
        # Get delay
        while True:
            try:
                delay = input(f"{Fore.CYAN}Enter delay between actions in seconds (default: 10): {Style.RESET_ALL}")
                if not delay:
                    delay = 10
                else:
                    delay = int(delay)
                
                if delay >= 0:
                    break
                else:
                    print(f"{Fore.RED}Delay must be greater than or equal to 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Mass report media
        success_count = 0
        for media_id in media_ids:
            print(f"\n{Fore.YELLOW}Reporting media {media_id}...{Style.RESET_ALL}")
            
            # Report media
            if self.current_session.report_media(media_id, reason):
                success_count += 1
            
            # Delay
            if delay > 0:
                time.sleep(delay)
        
        print(f"\n{Fore.GREEN}Successfully reported {success_count} out of {len(media_ids)} media items.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_mass_send_direct_messages(self):
        """Handle mass send direct messages"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Mass Send Direct Messages{Style.RESET_ALL}")
        print()
        
        # Get usernames
        usernames_input = input(f"{Fore.CYAN}Enter usernames (comma separated): {Style.RESET_ALL}")
        usernames = [username.strip() for username in usernames_input.split(',')]
        
        # Get message
        message = input(f"{Fore.CYAN}Enter message: {Style.RESET_ALL}")
        
        # Get delay
        while True:
            try:
                delay = input(f"{Fore.CYAN}Enter delay between actions in seconds (default: 10): {Style.RESET_ALL}")
                if not delay:
                    delay = 10
                else:
                    delay = int(delay)
                
                if delay >= 0:
                    break
                else:
                    print(f"{Fore.RED}Delay must be greater than or equal to 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Mass send direct messages
        success_count = 0
        for username in usernames:
            print(f"\n{Fore.YELLOW}Sending message to {username}...{Style.RESET_ALL}")
            
            # Get user ID
            user_id = self.current_session.get_user_id(username)
            
            if user_id:
                # Send direct message
                if self.current_session.send_direct_message(user_id, message):
                    success_count += 1
            
            # Delay
            if delay > 0:
                time.sleep(delay)
        
        print(f"\n{Fore.GREEN}Successfully sent messages to {success_count} out of {len(usernames)} users.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_account_settings(self):
        """Handle account settings menu"""
        while True:
            self.clear_screen()
            self.display_header()
            self.display_account_settings_menu()
            
            choice = self.get_user_choice(10)
            
            if choice == 0:  # Back to main menu
                break
            elif choice == 1:  # Set Account to Private
                self.handle_set_private()
            elif choice == 2:  # Set Account to Public
                self.handle_set_public()
            elif choice == 3:  # Change Password
                self.handle_change_password()
            elif choice == 4:  # Update Profile
                self.handle_update_profile()
            elif choice == 5:  # Get Notifications
                self.handle_get_notifications()
            elif choice == 6:  # Get Activity
                self.handle_get_activity()
            elif choice == 7:  # Enable Two-Factor Authentication
                self.handle_enable_two_factor()
            elif choice == 8:  # Disable Two-Factor Authentication
                self.handle_disable_two_factor()
            elif choice == 9:  # Get Login Activity
                self.handle_get_login_activity()
            elif choice == 10:  # Logout All Sessions
                self.handle_logout_all_sessions()
    
    def handle_set_private(self):
        """Handle set account to private"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Set Account to Private{Style.RESET_ALL}")
        print()
        
        # Set account to private
        self.current_session.set_private()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_set_public(self):
        """Handle set account to public"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Set Account to Public{Style.RESET_ALL}")
        print()
        
        # Set account to public
        self.current_session.set_public()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_change_password(self):
        """Handle change password"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Change Password{Style.RESET_ALL}")
        print()
        
        old_password = input(f"{Fore.CYAN}Enter old password: {Style.RESET_ALL}")
        new_password = input(f"{Fore.CYAN}Enter new password: {Style.RESET_ALL}")
        confirm_password = input(f"{Fore.CYAN}Confirm new password: {Style.RESET_ALL}")
        
        if new_password != confirm_password:
            print(f"{Fore.RED}❌ New passwords do not match!{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        # Change password
        self.current_session.change_password(old_password, new_password)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_update_profile(self):
        """Handle update profile"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Update Profile{Style.RESET_ALL}")
        print()
        
        full_name = input(f"{Fore.CYAN}Enter full name (leave blank to keep current): {Style.RESET_ALL}")
        biography = input(f"{Fore.CYAN}Enter biography (leave blank to keep current): {Style.RESET_ALL}")
        phone_number = input(f"{Fore.CYAN}Enter phone number (leave blank to keep current): {Style.RESET_ALL}")
        email = input(f"{Fore.CYAN}Enter email (leave blank to keep current): {Style.RESET_ALL}")
        website = input(f"{Fore.CYAN}Enter website (leave blank to keep current): {Style.RESET_ALL}")
        
        # Get gender
        print(f"{Fore.CYAN}Gender:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1. Male{Style.RESET_ALL}")
        print(f"{Fore.GREEN}2. Female{Style.RESET_ALL}")
        print(f"{Fore.GREEN}3. Prefer not to say{Style.RESET_ALL}")
        
        # Get user choice
        while True:
            try:
                choice = input(f"{Fore.CYAN}Enter gender (1-3, leave blank to keep current): {Style.RESET_ALL}")
                if not choice:
                    gender = ""
                    break
                else:
                    choice = int(choice)
                
                if 1 <= choice <= 3:
                    gender = str(choice)
                    break
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and 3.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Update profile
        self.current_session.update_profile(full_name, biography, phone_number, email, gender, website)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_notifications(self):
        """Handle get notifications"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Notifications{Style.RESET_ALL}")
        print()
        
        # Get notifications
        self.current_session.get_notifications()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_activity(self):
        """Handle get activity"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Activity{Style.RESET_ALL}")
        print()
        
        # Get activity
        self.current_session.get_activity()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_enable_two_factor(self):
        """Handle enable two-factor authentication"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Enable Two-Factor Authentication{Style.RESET_ALL}")
        print()
        
        print(f"{Fore.CYAN}This feature is not yet implemented.{Style.RESET_ALL}")
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_disable_two_factor(self):
        """Handle disable two-factor authentication"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Disable Two-Factor Authentication{Style.RESET_ALL}")
        print()
        
        print(f"{Fore.CYAN}This feature is not yet implemented.{Style.RESET_ALL}")
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_login_activity(self):
        """Handle get login activity"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Login Activity{Style.RESET_ALL}")
        print()
        
        print(f"{Fore.CYAN}This feature is not yet implemented.{Style.RESET_ALL}")
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_logout_all_sessions(self):
        """Handle logout all sessions"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Logout All Sessions{Style.RESET_ALL}")
        print()
        
        print(f"{Fore.CYAN}This feature is not yet implemented.{Style.RESET_ALL}")
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_insights(self):
        """Handle insights menu"""
        while True:
            self.clear_screen()
            self.display_header()
            self.display_insights_menu()
            
            choice = self.get_user_choice(10)
            
            if choice == 0:  # Back to main menu
                break
            elif choice == 1:  # Get Account Stats
                self.handle_get_account_stats()
            elif choice == 2:  # Get Business Info
                self.handle_get_business_info()
            elif choice == 3:  # Get Creator Info
                self.handle_get_creator_info()
            elif choice == 4:  # Get Insights
                self.handle_get_insights()
            elif choice == 5:  # Get Media Insights
                self.handle_get_media_insights()
            elif choice == 6:  # Get Audience Insights
                self.handle_get_audience_insights()
            elif choice == 7:  # Get Content Insights
                self.handle_get_content_insights()
            elif choice == 8:  # Get Activity Insights
                self.handle_get_activity_insights()
            elif choice == 9:  # Get Hashtag Feed
                self.handle_get_hashtag_feed()
            elif choice == 10:  # Get Location Feed
                self.handle_get_location_feed()
    
    def handle_get_account_stats(self):
        """Handle get account stats"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Account Stats{Style.RESET_ALL}")
        print()
        
        # Get account stats
        self.current_session.get_account_stats()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_business_info(self):
        """Handle get business info"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Business Info{Style.RESET_ALL}")
        print()
        
        # Get business info
        self.current_session.get_business_info()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_creator_info(self):
        """Handle get creator info"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Creator Info{Style.RESET_ALL}")
        print()
        
        # Get creator info
        self.current_session.get_creator_info()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_insights(self):
        """Handle get insights"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Insights{Style.RESET_ALL}")
        print()
        
        # Get insights
        self.current_session.get_insights()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_media_insights(self):
        """Handle get media insights"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Media Insights{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        
        # Get media insights
        self.current_session.get_media_insights(media_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_audience_insights(self):
        """Handle get audience insights"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Audience Insights{Style.RESET_ALL}")
        print()
        
        # Get audience insights
        self.current_session.get_audience_insights()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_content_insights(self):
        """Handle get content insights"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Content Insights{Style.RESET_ALL}")
        print()
        
        # Get content insights
        self.current_session.get_content_insights()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_activity_insights(self):
        """Handle get activity insights"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Activity Insights{Style.RESET_ALL}")
        print()
        
        # Get activity insights
        self.current_session.get_activity_insights()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_hashtag_feed(self):
        """Handle get hashtag feed"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Hashtag Feed{Style.RESET_ALL}")
        print()
        
        hashtag = input(f"{Fore.CYAN}Enter hashtag (without #): {Style.RESET_ALL}")
        
        # Get count
        while True:
            try:
                count = input(f"{Fore.CYAN}Enter number of media to retrieve (default: 20): {Style.RESET_ALL}")
                if not count:
                    count = 20
                else:
                    count = int(count)
                
                if count > 0:
                    break
                else:
                    print(f"{Fore.RED}Count must be greater than 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Get hashtag feed
        self.current_session.get_hashtag_feed(hashtag, count)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_get_location_feed(self):
        """Handle get location feed"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Get Location Feed{Style.RESET_ALL}")
        print()
        
        location_id = input(f"{Fore.CYAN}Enter location ID: {Style.RESET_ALL}")
        
        # Get count
        while True:
            try:
                count = input(f"{Fore.CYAN}Enter number of media to retrieve (default: 20): {Style.RESET_ALL}")
                if not count:
                    count = 20
                else:
                    count = int(count)
                
                if count > 0:
                    break
                else:
                    print(f"{Fore.RED}Count must be greater than 0.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
        
        # Get location feed
        self.current_session.get_location_feed(location_id, count)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_content_management(self):
        """Handle content management menu"""
        while True:
            self.clear_screen()
            self.display_header()
            self.display_content_management_menu()
            
            choice = self.get_user_choice(13)
            
            if choice == 0:  # Back to main menu
                break
            elif choice == 1:  # Upload Photo
                self.handle_upload_photo()
            elif choice == 2:  # Upload Video
                self.handle_upload_video()
            elif choice == 3:  # Upload Reel
                self.handle_upload_reel()
            elif choice == 4:  # Delete Media
                self.handle_delete_media()
            elif choice == 5:  # Edit Media
                self.handle_edit_media()
            elif choice == 6:  # Create Highlight
                self.handle_create_highlight()
            elif choice == 7:  # Edit Highlight
                self.handle_edit_highlight()
            elif choice == 8:  # Delete Highlight
                self.handle_delete_highlight()
            elif choice == 9:  # Create Collection
                self.handle_create_collection()
            elif choice == 10:  # Edit Collection
                self.handle_edit_collection()
            elif choice == 11:  # Delete Collection
                self.handle_delete_collection()
            elif choice == 12:  # Save to Collection
                self.handle_save_to_collection()
            elif choice == 13:  # Unsave from Collection
                self.handle_unsave_from_collection()
    
    def handle_upload_photo(self):
        """Handle upload photo"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Upload Photo{Style.RESET_ALL}")
        print()
        
        image_path = input(f"{Fore.CYAN}Enter image path: {Style.RESET_ALL}")
        caption = input(f"{Fore.CYAN}Enter caption (leave blank for no caption): {Style.RESET_ALL}")
        
        # Upload photo
        self.current_session.upload_photo(image_path, caption)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_upload_video(self):
        """Handle upload video"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Upload Video{Style.RESET_ALL}")
        print()
        
        video_path = input(f"{Fore.CYAN}Enter video path: {Style.RESET_ALL}")
        caption = input(f"{Fore.CYAN}Enter caption (leave blank for no caption): {Style.RESET_ALL}")
        
        # Upload video
        self.current_session.upload_video(video_path, caption)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_upload_reel(self):
        """Handle upload reel"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Upload Reel{Style.RESET_ALL}")
        print()
        
        video_path = input(f"{Fore.CYAN}Enter video path: {Style.RESET_ALL}")
        caption = input(f"{Fore.CYAN}Enter caption (leave blank for no caption): {Style.RESET_ALL}")
        
        # Upload reel
        self.current_session.upload_reel(video_path, caption)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_delete_media(self):
        """Handle delete media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Delete Media{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        
        # Delete media
        self.current_session.delete_media(media_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_edit_media(self):
        """Handle edit media"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Edit Media{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        caption = input(f"{Fore.CYAN}Enter new caption: {Style.RESET_ALL}")
        
        # Edit media
        self.current_session.edit_media(media_id, caption)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_create_highlight(self):
        """Handle create highlight"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Create Highlight{Style.RESET_ALL}")
        print()
        
        # Get media IDs
        media_ids_input = input(f"{Fore.CYAN}Enter media IDs (comma separated): {Style.RESET_ALL}")
        media_ids = [media_id.strip() for media_id in media_ids_input.split(',')]
        
        title = input(f"{Fore.CYAN}Enter highlight title: {Style.RESET_ALL}")
        cover_media_id = input(f"{Fore.CYAN}Enter cover media ID (leave blank for default): {Style.RESET_ALL}")
        
        # Create highlight
        self.current_session.create_highlight(media_ids, title, cover_media_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_edit_highlight(self):
        """Handle edit highlight"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Edit Highlight{Style.RESET_ALL}")
        print()
        
        highlight_id = input(f"{Fore.CYAN}Enter highlight ID: {Style.RESET_ALL}")
        title = input(f"{Fore.CYAN}Enter new title (leave blank to keep current): {Style.RESET_ALL}")
        cover_media_id = input(f"{Fore.CYAN}Enter new cover media ID (leave blank to keep current): {Style.RESET_ALL}")
        
        # Get media IDs to add
        add_media_ids_input = input(f"{Fore.CYAN}Enter media IDs to add (comma separated, leave blank for none): {Style.RESET_ALL}")
        add_media_ids = [media_id.strip() for media_id in add_media_ids_input.split(',')] if add_media_ids_input else []
        
        # Get media IDs to remove
        remove_media_ids_input = input(f"{Fore.CYAN}Enter media IDs to remove (comma separated, leave blank for none): {Style.RESET_ALL}")
        remove_media_ids = [media_id.strip() for media_id in remove_media_ids_input.split(',')] if remove_media_ids_input else []
        
        # Edit highlight
        self.current_session.edit_highlight(highlight_id, title, cover_media_id, add_media_ids, remove_media_ids)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_delete_highlight(self):
        """Handle delete highlight"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Delete Highlight{Style.RESET_ALL}")
        print()
        
        highlight_id = input(f"{Fore.CYAN}Enter highlight ID: {Style.RESET_ALL}")
        
        # Delete highlight
        self.current_session.delete_highlight(highlight_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_create_collection(self):
        """Handle create collection"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Create Collection{Style.RESET_ALL}")
        print()
        
        name = input(f"{Fore.CYAN}Enter collection name: {Style.RESET_ALL}")
        
        # Get media IDs
        media_ids_input = input(f"{Fore.CYAN}Enter media IDs (comma separated, leave blank for none): {Style.RESET_ALL}")
        media_ids = [media_id.strip() for media_id in media_ids_input.split(',')] if media_ids_input else []
        
        # Create collection
        self.current_session.create_collection(name, media_ids)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_edit_collection(self):
        """Handle edit collection"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Edit Collection{Style.RESET_ALL}")
        print()
        
        collection_id = input(f"{Fore.CYAN}Enter collection ID: {Style.RESET_ALL}")
        name = input(f"{Fore.CYAN}Enter new name (leave blank to keep current): {Style.RESET_ALL}")
        
        # Get media IDs to add
        add_media_ids_input = input(f"{Fore.CYAN}Enter media IDs to add (comma separated, leave blank for none): {Style.RESET_ALL}")
        add_media_ids = [media_id.strip() for media_id in add_media_ids_input.split(',')] if add_media_ids_input else []
        
        # Get media IDs to remove
        remove_media_ids_input = input(f"{Fore.CYAN}Enter media IDs to remove (comma separated, leave blank for none): {Style.RESET_ALL}")
        remove_media_ids = [media_id.strip() for media_id in remove_media_ids_input.split(',')] if remove_media_ids_input else []
        
        # Edit collection
        self.current_session.edit_collection(collection_id, name, add_media_ids, remove_media_ids)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_delete_collection(self):
        """Handle delete collection"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Delete Collection{Style.RESET_ALL}")
        print()
        
        collection_id = input(f"{Fore.CYAN}Enter collection ID: {Style.RESET_ALL}")
        
        # Delete collection
        self.current_session.delete_collection(collection_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_save_to_collection(self):
        """Handle save to collection"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Save to Collection{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        collection_id = input(f"{Fore.CYAN}Enter collection ID (leave blank for default collection): {Style.RESET_ALL}")
        
        # Save to collection
        self.current_session.save_to_collection(media_id, collection_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_unsave_from_collection(self):
        """Handle unsave from collection"""
        if not self.current_session:
            print(f"{Fore.RED}❌ No active session! Please login first.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            return
        
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Unsave from Collection{Style.RESET_ALL}")
        print()
        
        media_id = input(f"{Fore.CYAN}Enter media ID: {Style.RESET_ALL}")
        
        # Unsave from collection
        self.current_session.unsave_from_collection(media_id)
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def handle_update_api_endpoints(self):
        """Handle update API endpoints"""
        self.clear_screen()
        self.display_header()
        
        print(f"{Fore.YELLOW}Update API Endpoints{Style.RESET_ALL}")
        print()
        
        # Update API endpoints
        self.api_updater.update_api_endpoints()
        
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
    
    def run(self):
        """Run the Instagram automation tool"""
        while self.running:
            self.clear_screen()
            self.display_header()
            self.display_main_menu()
            
            choice = self.get_user_choice(9)
            
            if choice == 0:  # Exit
                self.running = False
                print(f"{Fore.GREEN}Thank you for using Instagram Automation Tool!{Style.RESET_ALL}")
            elif choice == 1:  # Account Management
                self.handle_account_management()
            elif choice == 2:  # User Actions
                self.handle_user_actions()
            elif choice == 3:  # Media Actions
                self.handle_media_actions()
            elif choice == 4:  # Direct Messaging
                self.handle_direct_messaging()
            elif choice == 5:  # Mass Actions
                self.handle_mass_actions()
            elif choice == 6:  # Account Settings
                self.handle_account_settings()
            elif choice == 7:  # Insights & Analytics
                self.handle_insights()
            elif choice == 8:  # Content Management
                self.handle_content_management()
            elif choice == 9:  # Update API Endpoints
                self.handle_update_api_endpoints()

def main():
    """Main function"""
    # Initialize the tool
    tool = InstagramAutomationTool()
    
    # Run the tool
    tool.run()

if __name__ == "__main__":
    main()