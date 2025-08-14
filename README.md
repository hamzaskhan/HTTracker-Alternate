# Picnic Day Series Offline Site Copier

This Python script replicates the core functionality of HTTrack by crawling a website, downloading its pages, assets, and rewriting links for offline browsing. It creates a local copy of the site—including a JSON file representing the site's link tree and a CSV file of unique URLs—making it easy to browse offline. The script is designed to be easily adaptable across platforms, including macOS. Currently it works for windows but you are welcome to extend it's capability across MacOs directory structure.

## Features

- **Recursive Crawling:** Follow internal links to a specified depth.
- **Asset Management:** Downloads CSS, JavaScript, images, and rewrites paths to point to local copies.
- **Offline Saving:** Saves the entire site structure under a designated directory.
- **Link Tree & Unique URLs:** Generates a JSON file of the site structure and a CSV list of unique links.
- **Cross-Platform Compatibility:** Adaptable for macOS and other environments.

## How to Use

1. **Run the Script:**  
   Execute the script using Python 3.
   ```bash
   python Download_Website_OfflineV2.py
   ```

2. **Provide Inputs:**  
   - Enter the website URL to crawl (default: `https://hamzak.cloud`).
   - Specify the maximum depth for crawling (default: `1`).

3. **View Outputs:**  
   - The offline site is saved under the `downloaded_site` directory.
   - A JSON file (`link_tree.json`) and a CSV file (`unique_links.csv`) are created with the site's link data.

4. **Enjoy Offline Browsing!**  
   Open the saved HTML files locally and browse the site without an internet connection.

---

## requirements.txt

```txt
requests
beautifulsoup4
```

### Check out my Picnic-Day-Scrapers repo to gain a further understanding.

Thankyou,
Hamza Khan
