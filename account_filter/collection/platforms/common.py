"""Small defaults for adapters that emit verified video records."""


async def parse_response(response, user_id):
    return None


def exclusion_reason(video):
    return None if video.get('content_type') == 'video' else '非视频作品，不作为视频候选'


def prefer_bio(current, dom):
    return False


def normalize_data(channel):
    return channel


def excluded_post_counts(channel):
    return {'excluded_post_count': len(channel.get('excluded_posts', [])),
            'excluded_image_count': 0, 'excluded_article_count': 0}


def recover_saved_failure(output, url):
    return False


def folder_id(user_id):
    return user_id
