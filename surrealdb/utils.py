from urllib.parse import urlparse, urlunparse


def change_url_scheme(url, new_scheme):
    parsed_url = urlparse(url)
    modified_url = parsed_url._asdict()
    modified_url['scheme'] = new_scheme
    return urlunparse(modified_url.values())