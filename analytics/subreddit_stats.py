"""
Subreddit Statistics - Subscribers, rules, mods, and metadata
"""
import requests
from datetime import datetime
import json

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_subreddit_about(subreddit):
    """
    Fetch subreddit metadata (subscribers, description, rules, etc.)
    
    Args:
        subreddit: Subreddit name (without r/)
    
    Returns:
        Dictionary with subreddit info
    """
    url = f"https://old.reddit.com/r/{subreddit}/about.json"
    
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch r/{subreddit} info: {response.status_code}")
            return None
        
        data = response.json()['data']
        
        return {
            "name": data.get('display_name'),
            "title": data.get('title'),
            "description": data.get('public_description'),
            "subscribers": data.get('subscribers', 0),
            "active_users": data.get('accounts_active', 0),
            "created_utc": datetime.fromtimestamp(data.get('created_utc', 0)).isoformat(),
            "over_18": data.get('over18', False),
            "subreddit_type": data.get('subreddit_type'),  # public, private, restricted
            "lang": data.get('lang'),
            "icon_url": data.get('icon_img', '').split('?')[0] if data.get('icon_img') else None,
            "banner_url": data.get('banner_img', '').split('?')[0] if data.get('banner_img') else None,
            "header_url": data.get('header_img'),
            "community_icon": data.get('community_icon', '').split('?')[0] if data.get('community_icon') else None,
            "wiki_enabled": data.get('wiki_enabled', False),
            "spoilers_enabled": data.get('spoilers_enabled', False),
            "allow_videos": data.get('allow_videos', False),
            "allow_images": data.get('allow_images', False),
            "allow_polls": data.get('allow_polls', False),
        }
    except Exception as e:
        print(f"❌ Error fetching subreddit info: {e}")
        return None

def get_subreddit_rules(subreddit):
    """
    Fetch subreddit rules.
    
    Args:
        subreddit: Subreddit name
    
    Returns:
        List of rule dictionaries
    """
    url = f"https://old.reddit.com/r/{subreddit}/about/rules.json"
    
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        rules = []
        
        for rule in data.get('rules', []):
            rules.append({
                "short_name": rule.get('short_name'),
                "description": rule.get('description'),
                "priority": rule.get('priority'),
                "kind": rule.get('kind'),  # link, comment, all
                "created_utc": datetime.fromtimestamp(rule.get('created_utc', 0)).isoformat()
            })
        
        return rules
    except Exception as e:
        print(f"❌ Error fetching rules: {e}")
        return []

def get_subreddit_mods(subreddit):
    """
    Fetch subreddit moderators.
    
    Args:
        subreddit: Subreddit name
    
    Returns:
        List of moderator usernames
    """
    url = f"https://old.reddit.com/r/{subreddit}/about/moderators.json"
    
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        mods = []
        
        for mod in data.get('data', {}).get('children', []):
            mods.append({
                "name": mod.get('name'),
                "permissions": mod.get('mod_permissions', []),
                "added_utc": datetime.fromtimestamp(mod.get('date', 0)).isoformat() if mod.get('date') else None
            })
        
        return mods
    except Exception as e:
        print(f"❌ Error fetching mods: {e}")
        return []

def get_subreddit_flairs(subreddit):
    """
    Fetch available post flairs.
    
    Args:
        subreddit: Subreddit name
    
    Returns:
        List of flair options
    """
    url = f"https://old.reddit.com/r/{subreddit}/api/link_flair_v2.json"
    
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        
        if response.status_code != 200:
            return []
        
        flairs = []
        for flair in response.json():
            flairs.append({
                "text": flair.get('text'),
                "id": flair.get('id'),
                "background_color": flair.get('background_color'),
                "text_color": flair.get('text_color'),
                "type": flair.get('type')
            })
        
        return flairs
    except Exception as e:
        return []

def get_full_subreddit_stats(subreddit):
    """
    Get comprehensive subreddit statistics.
    
    Args:
        subreddit: Subreddit name
    
    Returns:
        Dictionary with all stats
    """
    print(f"📊 Fetching stats for r/{subreddit}...")
    
    about = get_subreddit_about(subreddit)
    
    if not about:
        return None
    
    rules = get_subreddit_rules(subreddit)
    mods = get_subreddit_mods(subreddit)
    flairs = get_subreddit_flairs(subreddit)
    
    stats = {
        **about,
        "rules": rules,
        "rules_count": len(rules),
        "moderators": mods,
        "moderator_count": len(mods),
        "flairs": flairs,
        "flair_count": len(flairs),
        "fetched_at": datetime.now().isoformat()
    }
    
    # Print summary
    print(f"\n📊 r/{subreddit} Statistics:")
    print(f"   👥 Subscribers: {stats['subscribers']:,}")
    print(f"   🟢 Active Users: {stats['active_users']:,}")
    print(f"   📜 Rules: {stats['rules_count']}")
    print(f"   👮 Moderators: {stats['moderator_count']}")
    print(f"   🏷️ Flairs: {stats['flair_count']}")
    print(f"   📅 Created: {stats['created_utc'][:10]}")
    print(f"   🔞 NSFW: {stats['over_18']}")
    
    return stats

def save_subreddit_stats(subreddit, output_dir="data"):
    """
    Fetch and save subreddit stats to JSON.
    
    Args:
        subreddit: Subreddit name
        output_dir: Output directory
    
    Returns:
        Path to saved file
    """
    import os
    
    stats = get_full_subreddit_stats(subreddit)
    
    if not stats:
        return None
    
    save_dir = f"{output_dir}/r_{subreddit}"
    os.makedirs(save_dir, exist_ok=True)
    
    filepath = f"{save_dir}/subreddit_stats.json"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved to {filepath}")
    return filepath

# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Subreddit Statistics")
    parser.add_argument("subreddit", help="Subreddit name")
    parser.add_argument("--save", action="store_true", help="Save to JSON")
    
    args = parser.parse_args()
    
    if args.save:
        save_subreddit_stats(args.subreddit)
    else:
        stats = get_full_subreddit_stats(args.subreddit)
        if stats:
            print(f"\n📝 Description: {stats['description'][:200]}..." if stats['description'] else "")
