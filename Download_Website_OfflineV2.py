import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.request import url2pathname
import sys
import json
import csv
import argparse
import logging
from pathlib import Path

sys.setrecursionlimit(10000)

# --- Offline Configuration ---
OFFLINE_ROOT = "downloaded_site"

# --- Runtime Globals ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
session = requests.Session()
downloaded_assets = set()

def parse_args():
    parser = argparse.ArgumentParser(description="Download a website for offline viewing.")
    parser.add_argument("url", nargs="?", default="https://hamzak.cloud", help="Root URL to crawl")
    parser.add_argument("-d", "--depth", type=int, default=1, help="Maximum crawl depth")
    parser.add_argument("-o", "--output", default=OFFLINE_ROOT, help="Output directory for offline site")
    return parser.parse_args()

# --- Utility Functions ---

def is_valid(url):
    """
    Check if the URL is valid (has a scheme and network location).
    """
    parsed = urlparse(url)
    return bool(parsed.scheme) and bool(parsed.netloc)

def url_to_local_path(url):
    """
    Convert a URL into a local file path under OFFLINE_ROOT.
    If the URL path does not have a file extension or ends with a slash, use "index.html".
    """
    parsed = urlparse(url)
    path = parsed.path
    if path.endswith("/"):
        path += "index.html"
    elif not os.path.splitext(path)[1]:
        path += "/index.html"
    local_path = os.path.join(OFFLINE_ROOT, parsed.netloc, path.lstrip("/"))
    return local_path

def ensure_dir(filepath):
    """
    Ensure the directory for the given filepath exists.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

def download_file(url, local_path):
    """
    Download a file and save it to `local_path` using a shared requests.Session.

    Skips the download if the asset was already fetched during this run or if
    the target file already exists on disk. Returns True if the file is
    confirmed to be available locally.
    """
    try:
        if url in downloaded_assets or os.path.exists(local_path):
            return True
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            ensure_dir(local_path)
            with open(local_path, "wb") as f:
                f.write(response.content)
            downloaded_assets.add(url)
            return True
    except Exception as e:
        print(f"Error downloading asset {url}: {e}")
    return False

# --- Asset Processing ---

def process_assets(soup, page_url):
    """
    For asset tags (CSS, JS, images), download the asset file and update the tag
    to refer to the local copy (using a relative path).
    """
    # Process <link> tags (commonly CSS)
    for tag in soup.find_all("link", href=True):
        asset_url = urljoin(page_url, tag["href"].replace(" ", "%20"))
        local_path = url_to_local_path(asset_url)
        relative_path = os.path.relpath(local_path, os.path.dirname(url_to_local_path(page_url)))
        if download_file(asset_url, local_path):
            tag["href"] = relative_path

    # Process <script> tags (JavaScript)
    for tag in soup.find_all("script", src=True):
        asset_url = urljoin(page_url, tag["src"].replace(" ", "%20"))
        local_path = url_to_local_path(asset_url)
        relative_path = os.path.relpath(local_path, os.path.dirname(url_to_local_path(page_url)))
        if download_file(asset_url, local_path):
            tag["src"] = relative_path

    # Process <img> tags
    for tag in soup.find_all("img", src=True):
        asset_url = urljoin(page_url, tag["src"].replace(" ", "%20"))
        local_path = url_to_local_path(asset_url)
        relative_path = os.path.relpath(local_path, os.path.dirname(url_to_local_path(page_url)))
        if download_file(asset_url, local_path):
            tag["src"] = relative_path

def process_links(soup, page_url):
    """
    For anchor tags (<a>) pointing to internal pages, rewrite the href attribute
    to use a relative local path.
    """
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        # Skip fragment-only links (e.g. "#section")
        if href.startswith("#"):
            continue
        full_url = urljoin(page_url, href.replace(" ", "%20"))
        # Only rewrite if the link is internal.
        if is_valid(full_url) and urlparse(full_url).netloc == urlparse(page_url).netloc:
            local_path = url_to_local_path(full_url)
            relative_path = os.path.relpath(local_path, os.path.dirname(url_to_local_path(page_url)))
            tag["href"] = relative_path

# --- Link Extraction ---

def get_all_links(html_content, base_url):
    """
    Parse HTML and return a set of internal links.
    
    The function scans for URLs in common tag attributes, meta refresh tags,
    inline CSS references, and via regex.
    Any literal spaces are replaced with '%20'.
    Only links that belong to the same domain as base_url (or are file:// URLs)
    are kept.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    links = set()
    url_attrs = ["href", "src", "action", "data-href", "data-src", "data-url", "data-link", "onclick", "onmousedown", "onmouseup", "onmouseover", "onmouseout", "onfocus", "onblur", "data"]
    for tag in soup.find_all(True):
        for attr in url_attrs:
            if tag.has_attr(attr):
                url_candidate = tag.get(attr)
                if url_candidate:
                    url_candidate = url_candidate.replace(" ", "%20")
                    full_url = urljoin(base_url, url_candidate)
                    if full_url.startswith("file://"):
                        links.add(full_url)
                    elif is_valid(full_url) and urlparse(full_url).netloc == urlparse(base_url).netloc:
                        links.add(full_url)
    for meta in soup.find_all("meta", attrs={"http-equiv": lambda x: x and x.lower() == "refresh"}):
        content = meta.get("content", "")
        match = re.search(r'url=([\S]+)', content, re.IGNORECASE)
        if match:
            url_candidate = match.group(1).strip().strip('\'"').replace(" ", "%20")
            full_url = urljoin(base_url, url_candidate)
            if full_url.startswith("file://"):
                links.add(full_url)
            elif is_valid(full_url) and urlparse(full_url).netloc == urlparse(base_url).netloc:
                links.add(full_url)
    css_urls = re.findall(r'url\(([^)]+)\)', html_content)
    for css_url in css_urls:
        css_url = css_url.strip().strip('\'"').replace(" ", "%20")
        full_url = urljoin(base_url, css_url)
        if full_url.startswith("file://"):
            links.add(full_url)
        elif is_valid(full_url) and urlparse(full_url).netloc == urlparse(base_url).netloc:
            links.add(full_url)
    regex_pattern = r'https?://[^\s"\'<>]+'
    for match in re.findall(regex_pattern, html_content):
        fixed_match = match.replace(" ", "%20")
        full_url = urljoin(base_url, fixed_match)
        if full_url.startswith("file://"):
            links.add(full_url)
        elif is_valid(full_url) and urlparse(full_url).netloc == urlparse(base_url).netloc:
            links.add(full_url)
    return links

# --- Page Scraping and Offline Saving ---

def scrape_page(url):
    """
    Download a page, process its asset files (CSS, JS, images), rewrite the HTML to reference
    local copies (both for assets and internal links), and save the page offline.
    Returns a dictionary with page info.
    """
    try:
        response = session.get(url, timeout=10)
        if response.status_code != 200:
            print(f"Warning: Received status code {response.status_code} for URL: {url}")
            return None
        response.encoding = "utf-8"
        content = response.text
        soup = BeautifulSoup(content, "html.parser")
        # Download assets and update their paths.
        process_assets(soup, url)
        # Update internal links to use relative paths.
        process_links(soup, url)
        modified_html = str(soup)
        local_path = url_to_local_path(url)
        ensure_dir(local_path)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(modified_html)
        links = get_all_links(modified_html, url)
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        return {"url": url, "title": title, "html": modified_html, "links": links}
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def build_tree(url, base_domain, max_depth, visited):
    """
    Recursively scrape pages and build a tree structure representing the site.
    Only follows links that belong to the same domain.
    """
    if url in visited:
        return None
    print(f"Scraping: {url}")
    visited.add(url)
    page_data = scrape_page(url)
    if not page_data:
        return None
    node = {
        "url": page_data["url"],
        "title": page_data["title"],
        "links": sorted(page_data["links"]),
        "children": []
    }
    if max_depth > 0:
        for link in page_data["links"]:
            if urlparse(link).netloc == base_domain:
                child = build_tree(link, base_domain, max_depth - 1, visited)
                if child:
                    node["children"].append(child)
    return node

def traverse_tree(node, unique_links=None):
    """
    Recursively traverse the link tree to collect unique URLs with their titles.
    Returns a dictionary with URLs as keys and titles as values.
    """
    if node is None:
        return unique_links if unique_links is not None else {}
    if unique_links is None:
        unique_links = {}
    url = node.get("url")
    if url and url not in unique_links:
        unique_links[url] = node.get("title", "")
    for child in node.get("children", []):
        traverse_tree(child, unique_links)
    return unique_links

# --- CLI / Main Execution ---

def main():
    args = parse_args()
    website_url = args.url
    max_depth = args.depth

    global OFFLINE_ROOT
    OFFLINE_ROOT = args.output

    parsed_base = urlparse(website_url)
    base_domain = website_url if parsed_base.scheme == "file" else parsed_base.netloc

    visited = set()
    tree = build_tree(website_url, base_domain, max_depth, visited)

    # Ensure output directory exists
    os.makedirs(OFFLINE_ROOT, exist_ok=True)

    # Save the link tree
    output_json = os.path.join(OFFLINE_ROOT, "link_tree.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
    print(f"\nLink tree has been saved to {output_json}")

    # Collect unique URLs
    unique_links = traverse_tree(tree)
    output_csv = os.path.join(OFFLINE_ROOT, "unique_links.csv")
    with open(output_csv, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["URL", "Title"])
        for url, title in unique_links.items():
            writer.writerow([url, title])
    print(f"Unique links have been saved to {output_csv}")

    print("\nOffline site has been saved under the directory:", OFFLINE_ROOT)


if __name__ == "__main__":
    main()
