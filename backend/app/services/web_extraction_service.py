# chat_project/app/services/web_extraction_service.py

import requests
from flask import current_app
from typing import Optional, Dict, Any, List, Set
from urllib.parse import urlparse, urljoin, urlunparse
import time
import re
from bs4 import BeautifulSoup
import json
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


def _prompt_svc():
    """Lazy access to PromptService to avoid circular imports at module load."""
    from .prompt_service import PromptService
    return PromptService()

# Robust scraping libraries (installed for the rewrite 2026-06-06)
try:
    import cloudscraper  # type: ignore
    _HAS_CLOUDSCRAPER = True
except Exception:  # noqa: BLE001
    _HAS_CLOUDSCRAPER = False

try:
    import trafilatura  # type: ignore
    _HAS_TRAFILATURA = True
except Exception:  # noqa: BLE001
    _HAS_TRAFILATURA = False

try:
    from readability import Document as ReadabilityDocument  # type: ignore
    _HAS_READABILITY = True
except Exception:  # noqa: BLE001
    _HAS_READABILITY = False

try:
    import justext  # type: ignore
    _HAS_JUSTEXT = True
except Exception:  # noqa: BLE001
    _HAS_JUSTEXT = False

try:
    import html2text  # type: ignore
    _HAS_HTML2TEXT = True
except Exception:  # noqa: BLE001
    _HAS_HTML2TEXT = False

try:
    import httpx  # type: ignore
    _HAS_HTTPX = True
except Exception:  # noqa: BLE001
    _HAS_HTTPX = False


class WebExtractionService:
    """Service for extracting meaningful content from web pages using Gemini AI."""

    # Pool of realistic User-Agents to rotate for better success rate
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

    def _resolve_extraction_model(self, provider: str) -> str:
        """Return an active model name for the given provider (from the Super Admin's AiModel table)."""
        try:
            from .model_resolver import get_default_llm_model
            model_name, _ = get_default_llm_model(provider=provider)
            if model_name:
                return model_name
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(
            f"No active {provider} model configured. Super Admin must add a model in the AI Models page."
        )

    def __init__(self):
        self.session = requests.Session()
        self._rotate_user_agent()

        # Full site crawling state
        self.crawled_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.url_queue: deque = deque()
        self.extracted_content: List[Dict[str, Any]] = []
        self.crawl_lock = threading.Lock()
        self.max_pages = 100  # Higher limit, but will be calculated dynamically
        self.max_depth = 3   # Maximum crawl depth
        self.crawl_delay = 1  # Delay between requests (seconds)
        self.total_discovered_pages = 0  # Actual number of pages discovered
        self.progress_callback = None  # Callback for progress updates
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        })
        # Configure session for better reliability
        self.session.max_redirects = 10
        # Add retry adapter for better reliability
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _rotate_user_agent(self):
        """Rotate user agent for each request to avoid detection."""
        import random
        self.session.headers['User-Agent'] = random.choice(self.USER_AGENTS)

    def crawl_full_website(self, start_url: str, description: str = "", tenant_id: str = None, user_id: str = None, progress_callback=None, model_name: str = None, model_provider: str = None) -> Dict[str, Any]:
        """
        Crawl an entire website starting from the given URL.
        Discovers and extracts content from all accessible pages.
        """
        current_app.logger.info(f"🕷️ Starting FULL WEBSITE CRAWL for: {start_url}")

        # Reset crawling state
        self.crawled_urls.clear()
        self.failed_urls.clear()
        self.url_queue.clear()
        self.extracted_content.clear()
        self.progress_callback = progress_callback  # Store callback for progress updates
        self._structure_model_name = model_name
        self._structure_model_provider = model_provider

        # Parse the starting URL to get domain info
        parsed_start = urlparse(start_url)
        base_domain = f"{parsed_start.scheme}://{parsed_start.netloc}"
        domain_name = parsed_start.netloc

        current_app.logger.info(f"🎯 Target domain: {domain_name}")
        current_app.logger.info(f"📊 Crawl settings: max {self.max_pages} pages, {self.max_depth} depth")

        try:
            # Step 1: Discover URLs from multiple sources
            discovered_urls = self._discover_website_urls(start_url, base_domain)
            current_app.logger.info(f"🔍 Discovered {len(discovered_urls)} URLs to crawl")

            # Step 2: Add URLs to crawling queue
            for url_info in discovered_urls:
                self.url_queue.append(url_info)

            # Step 3: Process crawling queue with threading (with error handling)
            crawl_error = None
            try:
                self._process_crawl_queue(base_domain)
            except Exception as e:
                crawl_error = str(e)
                current_app.logger.warning(f"⚠️ Crawling stopped early due to error: {e}")

            # Step 4: Compile results (ALWAYS, even if crawling stopped early)
            total_crawled = len(self.crawled_urls)
            total_failed = len(self.failed_urls)
            total_extracted = len(self.extracted_content)

            if crawl_error:
                current_app.logger.info(f"⚠️ PARTIAL CRAWL COMPLETE: {total_crawled} pages crawled, {total_extracted} content pieces extracted, {total_failed} failed (stopped early: {crawl_error})")
            else:
                current_app.logger.info(f"✅ FULL CRAWL COMPLETE: {total_crawled} pages crawled, {total_extracted} content pieces extracted, {total_failed} failed")

            # CRITICAL: Always try to combine extracted content, even if partial
            combined_content = None
            if total_extracted > 0:
                try:
                    combined_content = self._combine_extracted_content(
                        start_url, domain_name,
                        model_name=self._structure_model_name,
                        model_provider=self._structure_model_provider
                    )
                    current_app.logger.info(f"✅ Successfully combined {total_extracted} pieces of extracted content")
                except Exception as combine_error:
                    current_app.logger.error(f"❌ Failed to combine content: {combine_error}")

            # Check if we got ANY meaningful content (partial success is still success!)
            if total_extracted == 0:
                current_app.logger.warning(f"⚠️ Crawl completed but no content was extracted from {start_url}")
                return {
                    'success': False,
                    'error': 'no_content_extracted',
                    'message': f"Website crawl completed but no content could be extracted. Discovered {len(discovered_urls)} URLs, but all {total_failed} failed to extract content. This may be due to the website's anti-bot protection or technical issues.",
                    'stats': {
                        'pages_crawled': total_crawled,
                        'pages_failed': total_failed,
                        'content_pieces': total_extracted,
                        'discovered_urls': len(discovered_urls),
                        'crawl_error': crawl_error
                    }
                }

            # SUCCESS: We have extracted content (even if partial)
            success_message = f"Successfully extracted content from {total_extracted} pages"
            if crawl_error:
                success_message += f" (crawling stopped early: {crawl_error})"

            return {
                'success': True,
                'content': combined_content,
                'source_url': start_url,
                'extraction_method': 'full_site_crawl',
                'message': success_message,
                'partial_crawl': crawl_error is not None,
                'stats': {
                    'pages_crawled': total_crawled,
                    'pages_failed': total_failed,
                    'content_pieces': total_extracted,
                    'discovered_urls': len(discovered_urls),
                    'crawl_error': crawl_error
                }
            }

        except Exception as e:
            current_app.logger.error(f"❌ Full website crawl failed: {e}")
            return {
                'success': False,
                'error': 'full_crawl_failed',
                'message': f"Full website crawl failed: {str(e)}"
            }

    def extract_content_from_url(self, url: str, description: str = "", tenant_id: str = None, user_id: str = None) -> Dict[str, Any]:
        """
        Robust single-URL scraping (rewrite 2026-06-06).

        Strategy (always tries them in order until something useful comes back):
            1. Multi-strategy fetch (requests → cloudscraper → httpx)
            2. Multi-strategy content extraction (trafilatura → readability → justext → html2text → BS4)
            3. If extraction is weak, augment with AI extraction (OpenAI or Gemini)
            4. If everything else fails, fall back to the Wayback Machine snapshot
        """

        # --- 1. Multi-strategy fetch ---
        try:
            fetch_result = self._fetch_url(url, timeout=30, allow_cloudscraper=True)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning(f"⚠️ Fetch failed for {url}: {exc}")
            fetch_result = None

        # Try Wayback Machine as an immediate fallback for blocked pages
        if not fetch_result or not fetch_result.get('content') or self._looks_blocked(fetch_result.get('content', '')):
            current_app.logger.info(f"🌐 Trying Wayback Machine for {url}")
            wb_html = self._fetch_from_wayback(url)
            if wb_html:
                fetch_result = {'content': wb_html, 'status_code': 200, 'url': url, 'method': 'wayback'}

        if not fetch_result or not fetch_result.get('content'):
            return {
                "success": False,
                "error": "fetch_failed",
                "message": f"Could not fetch {url} with any of the available strategies (requests, cloudscraper, httpx, wayback).",
            }

        page_content = fetch_result["content"]

        # --- 2. Multi-strategy content extraction (no AI needed for most sites) ---
        extracted = self._extract_content_multi(page_content, url)
        quality_issues = self._check_extraction_quality(extracted, url) if extracted else ['empty']

        # --- 3. If extraction is weak, fall back to AI extraction ---
        ai_augmented = False
        if (not extracted or quality_issues) and len(page_content) < 200_000:
            try:
                processed_for_ai = self._preprocess_html_content(page_content[:60000], url)
                if processed_for_ai and len(processed_for_ai) > 200:
                    ai_result = self._extract_with_openai(
                        processed_for_ai,
                        url,
                        tenant_id=tenant_id,
                        user_id=user_id,
                    )
                    if ai_result and len(ai_result) > max(len(extracted or ''), 200):
                        extracted = ai_result
                        ai_augmented = True
                        quality_issues = []
            except Exception as exc:  # noqa: BLE001
                current_app.logger.debug(f"AI extraction fallback failed: {exc}")

        if not extracted or len(extracted.strip()) < 80:
            return {
                "success": False,
                "error": "extraction_failed",
                "message": f"Page fetched (method={fetch_result.get('method', '?')}) but no readable content could be extracted.",
            }

        if quality_issues:
            current_app.logger.warning(f"⚠️ Extraction quality issues for {url}: {quality_issues}")

        current_app.logger.info(
            f"✅ Extracted {len(extracted)} chars from {url} "
            f"(method={fetch_result.get('method', '?')}, ai={ai_augmented})"
        )
        return {
            "success": True,
            "content": extracted,
            "fetch_method": fetch_result.get('method', 'requests'),
            "ai_augmented": ai_augmented,
        }

    def _fetch_page_content_enhanced(self, url: str) -> Dict[str, Any]:
        """Enhanced page content fetching with better content type detection and handling."""
        # First try the original method
        result = self._fetch_page_content(url)
        if not result["success"]:
            return result

        html_content = result["content"]

        # Analyze content type and structure
        content_analysis = self._analyze_content_structure(html_content, url)

        # Determine content type based on analysis
        if content_analysis["is_obfuscated"] and not content_analysis["has_meaningful_content"]:
            content_type = "obfuscated"
        elif content_analysis["has_meaningful_content"]:
            content_type = "html"
        else:
            content_type = "html"  # Default to HTML processing

        return {
            "success": True,
            "content": html_content,
            "content_type": content_type,
            "analysis": content_analysis
        }

    def _analyze_content_structure(self, html_content: str, url: str) -> Dict[str, Any]:
        """Analyze HTML content to determine its structure and type."""
        analysis = {
            "type": "html",
            "has_javascript": False,
            "is_obfuscated": False,
            "has_meaningful_content": False,
            "content_ratio": 0.0,
            "suspicious_patterns": []
        }

        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Check for JavaScript
            scripts = soup.find_all('script')
            analysis["has_javascript"] = len(scripts) > 0

            # Check for obfuscated content patterns
            obfuscated_patterns = [
                r'[A-Za-z0-9+/]{100,}={0,2}',  # Base64-like strings
                r'\\x[0-9a-fA-F]{2}',  # Hex encoded
                r'&#\d+;',  # HTML entities
                r'javascript:void\(0\)',
                r'eval\(',
                r'unescape\(',
                r'fromCharCode\('
            ]

            for pattern in obfuscated_patterns:
                if re.search(pattern, html_content):
                    analysis["suspicious_patterns"].append(pattern)
                    analysis["is_obfuscated"] = True

            # Calculate content ratio (text vs HTML tags)
            text_content = soup.get_text()
            clean_text = re.sub(r'\s+', ' ', text_content).strip()

            if len(clean_text) > 100:
                analysis["has_meaningful_content"] = True
                analysis["content_ratio"] = len(clean_text) / len(html_content)

            # Check for meaningful content indicators (general purpose)
            # Check if there's substantial text content
            if len(clean_text) > 200:
                analysis["has_meaningful_content"] = True

            current_app.logger.info(f"🔍 Content analysis for {url}: {analysis}")

        except Exception as e:
            current_app.logger.warning(f"⚠️ Content analysis failed for {url}: {e}")

        return analysis

    def _preprocess_content_by_type(self, content: str, content_type: str, url: str) -> Optional[str]:
        """Preprocess content based on its detected type."""
        try:
            if content_type == "html":
                return self._preprocess_html_content(content, url)
            elif content_type == "obfuscated":
                return self._handle_obfuscated_content(content, url)
            else:
                return content
        except Exception as e:
            current_app.logger.error(f"❌ Content preprocessing failed for {url}: {e}")
            return None

    def _preprocess_html_content(self, html_content: str, url: str) -> str:
        """Enhanced HTML preprocessing using BeautifulSoup."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove unwanted elements aggressively
            unwanted_tags = ['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'iframe']
            for tag in unwanted_tags:
                for element in soup.find_all(tag):
                    element.decompose()

            # Remove elements with unwanted classes/IDs (expanded list)
            unwanted_selectors = [
                '[class*="nav"]', '[class*="navigation"]', '[class*="menu"]', '[class*="sidebar"]',
                '[class*="ad"]', '[class*="advertisement"]', '[class*="popup"]', '[class*="modal"]',
                '[class*="cookie"]', '[class*="social"]', '[class*="share"]', '[class*="breadcrumb"]',
                '[class*="header"]', '[class*="footer"]', '[class*="banner"]',
                '[id*="nav"]', '[id*="navigation"]', '[id*="menu"]', '[id*="sidebar"]',
                '[id*="ad"]', '[id*="advertisement"]', '[id*="popup"]', '[id*="header"]', '[id*="footer"]',
                'button[type="submit"]', 'input', 'form', 'select'
            ]

            for selector in unwanted_selectors:
                for element in soup.select(selector):
                    element.decompose()

            # Remove elements with minimal text (likely navigation/buttons)
            for element in soup.find_all(['a', 'button', 'span']):
                text = element.get_text(strip=True)
                # Remove short links that are likely navigation
                if len(text) < 30 and element.name == 'a':
                    # Check if it's a standalone link (not part of a paragraph)
                    parent = element.parent
                    if parent and parent.name not in ['p', 'li', 'td']:
                        element.decompose()

            # DON'T prioritize just main - we need ALL content for restaurants
            # Comment out to get full page content including location lists
            # main_content = soup.find('main') or soup.find(id='main') or soup.find(id='content')
            # if main_content:
            #     current_app.logger.info(f"✅ Found main content area in {url}")
            #     soup = main_content

            # Extract meaningful content with better structure
            content_parts = []

            # Extract title
            title = soup.find('h1')
            if title:
                content_parts.append(f"# {title.get_text(strip=True)}\n")

            # Extract structured content
            for element in soup.find_all(['h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'td', 'article', 'section']):
                text = element.get_text(strip=True)
                text = ' '.join(text.split())  # Normalize whitespace

                # Skip very short text but allow longer text for comprehensive extraction
                if not text or len(text) < 10:
                    continue

                # Allow up to 1000 chars for location lists and detailed content
                if len(text) > 1000:
                    continue

                # Skip common navigation phrases
                skip_phrases = ['click here', 'read more', 'learn more', 'see all', 'view all',
                                'select', 'choose', 'subscribe', 'sign up', 'log in', 'register']
                if any(phrase in text.lower() for phrase in skip_phrases) and len(text) < 50:
                    continue

                # Add with appropriate formatting
                tag_name = element.name
                if tag_name in ['h2', 'h3', 'h4', 'h5', 'h6']:
                    content_parts.append(f"\n## {text}\n")
                elif tag_name == 'li':
                    content_parts.append(f"- {text}")
                elif tag_name == 'p':
                    content_parts.append(f"{text}\n")
                else:
                    # For other elements, only add if they seem meaningful
                    if len(text) > 30:
                        content_parts.append(text)

            processed_content = '\n'.join(content_parts)

            # Clean up excessive whitespace
            processed_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', processed_content)
            processed_content = re.sub(r'[ \t]+', ' ', processed_content)

            # Remove duplicate lines
            lines = processed_content.split('\n')
            seen = set()
            unique_lines = []
            for line in lines:
                line_clean = line.strip()
                if line_clean and line_clean not in seen:
                    unique_lines.append(line)
                    seen.add(line_clean)

            processed_content = '\n'.join(unique_lines)

            current_app.logger.info(f"✅ Processed HTML content: {len(processed_content)} chars from {url}")
            return processed_content.strip()

        except Exception as e:
            current_app.logger.error(f"❌ HTML preprocessing failed for {url}: {e}")
            return html_content

    def _handle_obfuscated_content(self, content: str, url: str) -> Optional[str]:
        """Handle obfuscated or encoded content."""
        try:
            current_app.logger.info(f"🔍 Attempting to decode obfuscated content from {url}")

            # Try different decoding methods
            decoded_content = None

            # Method 1: Try to find JSON-LD structured data
            json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
            json_ld_matches = re.findall(json_ld_pattern, content, re.DOTALL | re.IGNORECASE)

            if json_ld_matches:
                for match in json_ld_matches:
                    try:
                        json_data = json.loads(match)
                        if isinstance(json_data, dict):
                            decoded_content = self._extract_from_json_ld(json_data)
                            if decoded_content:
                                break
                    except json.JSONDecodeError:
                        continue

            # Method 2: Try to extract meta tags
            if not decoded_content:
                soup = BeautifulSoup(content, 'html.parser')
                meta_content = []

                # Extract meta descriptions
                for meta in soup.find_all('meta'):
                    name = meta.get('name', '').lower()
                    content_attr = meta.get('content', '')

                    if name in ['description', 'keywords'] and content_attr:
                        meta_content.append(f"{name.title()}: {content_attr}")

                # Extract title
                title = soup.find('title')
                if title and title.get_text():
                    meta_content.append(f"Title: {title.get_text()}")

                if meta_content:
                    decoded_content = '\n'.join(meta_content)

            # Method 3: Try to decode base64 content
            if not decoded_content:
                base64_pattern = r'[A-Za-z0-9+/]{100,}={0,2}'
                base64_matches = re.findall(base64_pattern, content)

                for match in base64_matches:
                    try:
                        import base64
                        decoded = base64.b64decode(match).decode('utf-8', errors='ignore')
                        if len(decoded) > 50:  # Any meaningful decoded content
                            decoded_content = decoded
                            break
                    except Exception:
                        continue

            if decoded_content:
                current_app.logger.info(f"✅ Successfully decoded obfuscated content: {len(decoded_content)} chars")
                return decoded_content
            else:
                current_app.logger.warning(f"⚠️ Could not decode obfuscated content from {url}")
                return None

        except Exception as e:
            current_app.logger.error(f"❌ Obfuscated content handling failed for {url}: {e}")
            return None

    def _extract_from_json_ld(self, json_data: dict) -> Optional[str]:
        """Extract meaningful content from JSON-LD structured data."""
        try:
            content_parts = []

            # Extract common business/organization information
            if 'name' in json_data:
                content_parts.append(f"Name: {json_data['name']}")

            if 'description' in json_data:
                content_parts.append(f"Description: {json_data['description']}")

            if 'address' in json_data:
                address = json_data['address']
                if isinstance(address, dict):
                    address_parts = []
                    for key in ['streetAddress', 'addressLocality', 'addressRegion', 'postalCode']:
                        if key in address:
                            address_parts.append(address[key])
                    if address_parts:
                        content_parts.append(f"Address: {', '.join(address_parts)}")

            if 'telephone' in json_data:
                content_parts.append(f"Phone: {json_data['telephone']}")

            if 'url' in json_data:
                content_parts.append(f"Website: {json_data['url']}")

            if 'openingHours' in json_data:
                hours = json_data['openingHours']
                if isinstance(hours, list):
                    content_parts.append(f"Hours: {', '.join(hours)}")
                elif isinstance(hours, str):
                    content_parts.append(f"Hours: {hours}")

            # Extract any additional structured data
            for key, value in json_data.items():
                if key not in ['name', 'description', 'address', 'telephone', 'url', 'openingHours']:
                    if isinstance(value, (str, int, float)) and len(str(value)) < 200:
                        content_parts.append(f"{key.title()}: {value}")
                    elif isinstance(value, list) and len(value) < 10:
                        content_parts.append(f"{key.title()}: {', '.join(str(v) for v in value)}")

            if content_parts:
                return '\n'.join(content_parts)

        except Exception as e:
            current_app.logger.warning(f"⚠️ JSON-LD extraction failed: {e}")

        return None

    def _fetch_page_content(self, url: str) -> Dict[str, Any]:
        """Fetch raw HTML content from the URL with optimized retry logic and better error handling."""
        max_retries = 3
        timeouts = [20, 35, 50]  # Optimized progressive timeout increase

        for attempt in range(max_retries):
            try:
                # Rotate user agent for each attempt
                self._rotate_user_agent()

                timeout = timeouts[min(attempt, len(timeouts) - 1)]
                current_app.logger.info(f"📥 Fetching page content from: {url} (attempt {attempt + 1}/{max_retries}, timeout: {timeout}s)")

                # Add delay between retries to avoid rate limiting
                if attempt > 0:
                    delay = 2 * attempt  # 2s, 4s
                    current_app.logger.info(f"⏱️ Waiting {delay}s before retry to avoid rate limiting...")
                    time.sleep(delay)

                # Make request with updated headers
                response = self.session.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    verify=True  # Verify SSL certificates
                )
                response.raise_for_status()

                # Check if content is HTML
                content_type = response.headers.get('content-type', '').lower()
                if 'html' not in content_type:
                    current_app.logger.warning(f"⚠️ Non-HTML content type: {content_type}")
                    # Continue anyway - some sites misreport content type

                html_content = response.text
                current_app.logger.info(f"📄 Successfully fetched {len(html_content)} characters of HTML content")

                # Basic validation - ensure we got actual content
                if len(html_content.strip()) < 100:
                    current_app.logger.warning(f"⚠️ Suspiciously short content: {len(html_content)} chars")
                    if attempt < max_retries - 1:
                        continue  # Retry if we got too little content

                # Check for common blocking pages
                blocking_indicators = [
                    'access denied',
                    'cloudflare',
                    'security check',
                    'captcha',
                    'blocked',
                    'forbidden',
                    'rate limit'
                ]
                content_lower = html_content.lower()
                if any(indicator in content_lower for indicator in blocking_indicators):
                    current_app.logger.warning(f"⚠️ Possible blocking page detected")
                    if attempt < max_retries - 1:
                        continue  # Retry with different user agent

                return {"success": True, "content": html_content}

            except requests.exceptions.SSLError as e:
                current_app.logger.warning(f"🔒 SSL error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": "ssl_error",
                        "message": f"SSL certificate verification failed for {url}. The website may have security issues."
                    }
                # Try with SSL verification disabled on last attempt
                if attempt == max_retries - 2:
                    try:
                        response = self.session.get(url, timeout=timeout, allow_redirects=True, verify=False)
                        if response.status_code == 200:
                            return {"success": True, "content": response.text}
                    except Exception:
                        pass
                continue

            except requests.exceptions.Timeout as e:
                current_app.logger.warning(f"⏰ Timeout on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    current_app.logger.error(f"❌ All {max_retries} attempts timed out for {url}")
                    return {
                        "success": False,
                        "error": "timeout",
                        "message": f"The website took too long to respond. This may be due to: (1) The site is slow or overloaded, (2) The site has anti-bot protection, or (3) Network connectivity issues. Try a different URL from the same domain or a simpler page."
                    }
                continue

            except requests.exceptions.TooManyRedirects as e:
                current_app.logger.error(f"❌ Too many redirects for {url}: {e}")
                return {
                    "success": False,
                    "error": "too_many_redirects",
                    "message": f"The URL redirected too many times. Please use the final destination URL directly."
                }

            except requests.exceptions.ConnectionError as e:
                current_app.logger.warning(f"🌐 Connection error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": "connection_error",
                        "message": f"Could not connect to the website. The site may be down or blocking automated requests."
                    }
                continue

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else None
                current_app.logger.warning(f"🚫 HTTP error {status_code} on attempt {attempt + 1}: {e}")

                if status_code == 403:
                    return {
                        "success": False,
                        "error": "forbidden",
                        "message": f"Access denied (HTTP 403). The website is blocking automated requests. Try: (1) A different page from the same domain, (2) Manually copying the content, or (3) Contacting the website owner for API access."
                    }
                elif status_code == 404:
                    return {
                        "success": False,
                        "error": "not_found",
                        "message": f"Page not found (HTTP 404). Please check the URL and try again."
                    }
                elif status_code == 429:
                    if attempt < max_retries - 1:
                        current_app.logger.info("⏳ Rate limited, will retry with longer delay...")
                        time.sleep(5 * (attempt + 1))  # Progressive delay for rate limiting
                        continue
                    return {
                        "success": False,
                        "error": "rate_limited",
                        "message": f"Rate limit exceeded (HTTP 429). Please try again in a few minutes."
                    }
                elif status_code == 503:
                    if attempt < max_retries - 1:
                        continue
                    return {
                        "success": False,
                        "error": "service_unavailable",
                        "message": f"The website is temporarily unavailable (HTTP 503). Please try again later."
                    }

                if attempt == max_retries - 1:
                    return {
                        "success": False,
                        "error": "http_error",
                        "message": f"HTTP error {status_code}: {str(e)}"
                    }
                continue

            except requests.exceptions.RequestException as e:
                current_app.logger.warning(f"🌐 Request error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    current_app.logger.error(f"❌ All {max_retries} attempts failed for {url}: {e}")
                    return {
                        "success": False,
                        "error": "fetch_failed",
                        "message": f"Could not fetch content from the URL: {str(e)}"
                    }
                continue

            except Exception as e:
                current_app.logger.error(f"❌ Unexpected error fetching {url}: {e}")
                return {
                    "success": False,
                    "error": "unexpected_error",
                    "message": f"An unexpected error occurred: {str(e)}"
                }

        return {
            "success": False,
            "error": "fetch_failed",
            "message": f"Could not fetch content from the URL after {max_retries} attempts. The website may be blocking automated access or experiencing issues."
        }

    def _try_alternative_extraction(self, url: str, error_reason: str) -> Dict[str, Any]:
        """Alternative extraction method - provide helpful error message for difficult websites."""
        current_app.logger.info(f"🔄 Website appears to be blocking requests or timing out: {url}")

        # Try enhanced BeautifulSoup extraction as fallback
        enhanced_extraction = self._try_enhanced_beautifulsoup_extraction(url)
        if enhanced_extraction:
            return enhanced_extraction

        # Analyze the URL to provide helpful suggestions
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        suggestions = []
        if any(site in domain for site in ['facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com']):
            suggestions.append("Social media sites often block automated access")
            suggestions.append("Try copying and pasting the content manually instead")
        elif any(site in domain for site in ['amazon.com', 'ebay.com', 'alibaba.com']):
            suggestions.append("E-commerce sites often have anti-scraping protection")
            suggestions.append("Try a product support or help page instead")
        else:
            suggestions.append("This website may have timeout issues or anti-bot protection")
            suggestions.append("Try a simpler page from the same domain")
            suggestions.append("Try accessing specific content pages (about, contact, products, services)")
            suggestions.append("Consider using a direct article or documentation URL")

        error_message = f"Unable to access {domain}. " + ". ".join(suggestions)

        return {
            'success': False,
            'error': error_message,
            'content': None,
            'metadata': {
                'url': url,
                'status': 'failed',
                'error_type': 'access_blocked_or_timeout',
                'suggestions': suggestions
            }
        }

    def _try_enhanced_beautifulsoup_extraction(self, url: str) -> Optional[Dict[str, Any]]:
        """Try enhanced BeautifulSoup extraction as fallback for any website."""
        try:
            current_app.logger.info(f"🔧 Attempting enhanced BeautifulSoup extraction for {url}")

            # Try to fetch with different headers including mobile user agents
            fallback_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }

            # Try different common URLs
            parsed_url = urlparse(url)
            base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

            urls_to_try = [
                url,  # Original URL
                f"{base_domain}/about",
                f"{base_domain}/contact",
                f"{base_domain}/products",
                f"{base_domain}/services",
                f"{base_domain}/",
                f"{base_domain}/home",
                f"{base_domain}/info",
                f"{base_domain}/company"
            ]

            for test_url in urls_to_try:
                try:
                    response = requests.get(test_url, headers=fallback_headers, timeout=30)
                    if response.status_code == 200:
                        content = response.text

                        # Check if this has meaningful content
                        if self._has_meaningful_content(content):
                            current_app.logger.info(f"✅ Found meaningful content at {test_url}")

                            # Extract structured information using BeautifulSoup
                            extracted_info = self._extract_structured_content(content, test_url)
                            if extracted_info:
                                return {
                                    'success': True,
                                    'content': extracted_info,
                                    'source_url': test_url,
                                    'extraction_method': 'beautifulsoup_fallback'
                                }

                except Exception as e:
                    current_app.logger.debug(f"Failed to fetch {test_url}: {e}")
                    continue

            return None

        except Exception as e:
            current_app.logger.error(f"❌ Restaurant-specific extraction failed: {e}")
            return None

    def _has_meaningful_content(self, content: str) -> bool:
        """Check if content has substantial meaningful text (general purpose)."""
        try:
            soup = BeautifulSoup(content, 'html.parser')

            # Remove scripts and styles
            for script in soup(["script", "style", "noscript"]):
                script.decompose()

            # Get text
            text = soup.get_text()
            clean_text = ' '.join(text.split())

            # Check if there's substantial content (at least 500 characters of text)
            return len(clean_text) > 500

        except Exception:
            return False

    def _extract_structured_content(self, content: str, url: str) -> Optional[str]:
        """Extract structured information from content using BeautifulSoup."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            info_parts = []

            # Extract title
            title = soup.find('title')
            if title and title.get_text():
                title_text = title.get_text().strip()
                if title_text:
                    info_parts.append(f"# {title_text}\n")

            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if not meta_desc:
                meta_desc = soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc and meta_desc.get('content'):
                info_parts.append(f"## About\n{meta_desc.get('content')}\n")

            # Extract all visible text content (even from obfuscated HTML)
            # Remove script and style elements
            for script in soup(["script", "style", "noscript"]):
                script.decompose()

            # Get text content
            text = soup.get_text()

            # Break into lines and remove leading and trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            visible_text = '\n'.join(chunk for chunk in chunks if chunk)

            # Extract structured information
            # Extract contact information
            contact_info = self._extract_contact_info(soup)
            if contact_info:
                info_parts.append("## Contact Information")
                info_parts.extend(contact_info)
                info_parts.append("")

            # Extract hours/availability information
            hours_info = self._extract_hours_info(soup)
            if hours_info:
                info_parts.append("## Hours & Availability")
                info_parts.extend(hours_info)
                info_parts.append("")

            # If we have visible text, include it (general purpose)
            if visible_text and len(visible_text) > 200:
                # Include the visible text with reasonable limits
                if len(visible_text) > 5000:
                    info_parts.append("## Content")
                    info_parts.append(visible_text[:5000] + "...")
                else:
                    info_parts.append("## Content")
                    info_parts.append(visible_text)

            if info_parts:
                structured_content = "\n".join(info_parts)
                structured_content += f"\n\n---\nSource: {url}"
                current_app.logger.info(f"✅ Extracted {len(structured_content)} characters of structured content")
                return structured_content

            return None

        except Exception as e:
            current_app.logger.error(f"❌ Structured content extraction failed: {e}")
            return None

    def _extract_contact_info(self, soup) -> list:
        """Extract contact information from soup."""
        contact_info = []

        # Get all text content
        text = soup.get_text()

        # Look for phone numbers with better pattern
        phone_pattern = r'(?:phone|tel|call)[\s:]*(\+?[\d\s\-\(\)\.]{10,20})|(\+?[\d\s\-\(\)]{10,20})'
        phone_matches = re.findall(phone_pattern, text, re.IGNORECASE)
        seen_phones = set()
        for match in phone_matches:
            phone = match[0] if match[0] else match[1]
            phone = phone.strip()
            # Clean up phone number
            digits_only = re.sub(r'[^\d+]', '', phone)
            if 8 <= len(digits_only) <= 15 and digits_only not in seen_phones:
                contact_info.append(f"- Phone: {phone}")
                seen_phones.add(digits_only)
                break  # Only take first phone

        # Look for email addresses
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        email_matches = re.findall(email_pattern, text)
        if email_matches:
            # Filter out common fake emails
            fake_emails = ['example.com', 'test.com', 'domain.com']
            real_emails = [e for e in email_matches if not any(fake in e.lower() for fake in fake_emails)]
            if real_emails:
                contact_info.append(f"- Email: {real_emails[0]}")

        # Look for addresses with common patterns
        address_keywords = ['rue', 'avenue', 'chemin', 'route', 'place', 'street', 'strasse', 'str.', 'ave.', 'rd.', 'road', 'lane', 'drive', 'blvd', 'boulevard', 'way', 'court', 'plaza']
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if any(keyword in line.lower() for keyword in address_keywords) and 10 < len(line) < 100:
                # Try to get city/postal code from next line
                address_line = line
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Check if next line has postal code pattern
                    if re.search(r'\d{4,5}', next_line) and len(next_line) < 50:
                        address_line += f", {next_line}"
                contact_info.append(f"- Address: {address_line}")
                break

        # Look for website URL
        url_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
        url_matches = re.findall(url_pattern, text)
        if url_matches:
            # Filter out common domains
            common_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'google.com', 'youtube.com']
            real_urls = [u for u in url_matches if not any(common in u.lower() for common in common_domains)]
            if real_urls:
                contact_info.append(f"- Website: {real_urls[0]}")

        return contact_info

    def _extract_hours_info(self, soup) -> list:
        """Extract operating hours or availability information from soup."""
        hours_info = []

        # Look for hours-related headings first
        hours_headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'div', 'span'],
                                      string=re.compile(r'hours?|horaires?|öffnungszeiten|opening|availability|schedule|operating', re.I))

        if hours_headers:
            for header in hours_headers[:1]:  # Take first match
                # Get content after this header
                next_element = header.find_next_sibling()
                count = 0
                while next_element and count < 10:
                    text = next_element.get_text(strip=True)
                    if text and len(text) > 5:
                        # Check if it contains day or time information
                        if re.search(r'\d{1,2}:\d{2}|monday|tuesday|wednesday|thursday|friday|saturday|sunday|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|24/7|24 hours', text, re.I):
                            clean_text = ' '.join(text.split())
                            hours_info.append(f"- {clean_text}")
                            count += 1
                    next_element = next_element.find_next_sibling()

        # If no structured hours found, look for patterns in text
        if not hours_info:
            text = soup.get_text()
            hours_patterns = [
                r'(?:open|available|operating)[\s:]*(\d{1,2}[:\.]?\d{0,2}\s*(?:am|pm|h)?.*?\d{1,2}[:\.]?\d{0,2}\s*(?:am|pm|h)?)',
                r'((?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)[\s\-:]*\d{1,2}[:\.]?\d{0,2}.*?\d{1,2}[:\.]?\d{0,2})',
                r'(\d{1,2}[:\.]?\d{2}\s*[-–]\s*\d{1,2}[:\.]?\d{2})',
                r'(24/7|24 hours|always open)',
            ]

            seen_hours = set()
            for pattern in hours_patterns:
                matches = re.findall(pattern, text, re.I)
                for match in matches[:5]:  # Limit to first 5 matches
                    hours_text = match if isinstance(match, str) else ' '.join(match)
                    hours_text = ' '.join(hours_text.split())  # Clean whitespace
                    if hours_text and hours_text not in seen_hours and len(hours_text) < 100:
                        hours_info.append(f"- {hours_text}")
                        seen_hours.add(hours_text)

        return hours_info

    def _try_fallback_extraction(self, html_content: str, url: str, error_reason: str) -> Dict[str, Any]:
        """Fallback extraction method when AI services are not available."""
        current_app.logger.info(f"🔄 Using basic regex fallback extraction for {url}")

        try:
            import re

            # Remove script and style tags
            html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

            # Remove HTML tags but keep the text
            text_content = re.sub(r'<[^>]+>', ' ', html_content)

            # Clean up whitespace
            text_content = re.sub(r'\s+', ' ', text_content)
            text_content = text_content.strip()

            # Split into lines and clean
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            if not lines:
                # If no lines, split by sentences
                sentences = [s.strip() for s in text_content.split('.') if s.strip() and len(s.strip()) > 10]
                cleaned_text = '\n'.join(sentences[:50])  # Limit to first 50 sentences
            else:
                cleaned_text = '\n'.join(lines)

            if len(cleaned_text) > 100:
                current_app.logger.info(f"✅ Fallback extraction successful: {len(cleaned_text)} characters from {url}")
                fallback_notice = f"""⚠️ NOTICE: This content was extracted using basic text parsing because AI services are not configured.

For better, AI-powered content extraction, please:
1. Set GEMINI_API_KEY environment variable
2. Restart the application

URL: {url}

--- EXTRACTED CONTENT ---

{cleaned_text[:5000]}{'...' if len(cleaned_text) > 5000 else ''}"""
                return {"success": True, "content": fallback_notice}
            else:
                current_app.logger.warning(f"⚠️ Fallback extraction produced insufficient content for {url}")
                return {
                    'success': False,
                    'error': f"Web extraction failed: {error_reason}. Basic text extraction also produced insufficient content. Please set GEMINI_API_KEY for better extraction.",
                    'content': None
                }

        except Exception as fallback_error:
            current_app.logger.error(f"❌ Fallback extraction failed: {fallback_error}")
            return {
                'success': False,
                'error': f"Web extraction failed: {error_reason}. Please set GEMINI_API_KEY environment variable for web crawling functionality.",
                'content': None
            }

    def _extract_with_gemini(self, html_content: str, url: str, tenant_id: str = None, user_id: str = None) -> Optional[str]:
        """Sends HTML content to Gemini for extraction with improved prompting."""

        llm_service = getattr(current_app, 'llm_service', None)
        if not llm_service or not llm_service.gemini_client:
            current_app.logger.warning("⚠️ Gemini client not available - using fallback extraction")
            raise Exception("Web extraction requires Gemini API key. Please set GEMINI_API_KEY environment variable and restart the application.")

        # Pre-process HTML to reduce noise and improve extraction
        cleaned_html = self._preprocess_html(html_content)

        # IMPROVED: General-purpose, comprehensive content extraction
        # The full instruction prompt is sourced from prompts.yml (web_extraction).
        truncated_marker = "...[Content truncated]" if len(cleaned_html) > 50000 else ""
        prompt = _prompt_svc().render(
            'web_extraction',
            html_content=(
                f"URL: {url}\n\n"
                f"{cleaned_html[:50000]}{truncated_marker}"
            ),
        )

        # Use Gemini directly for web extraction with higher token limits
        # We need more tokens for comprehensive content extraction
        try:
            import os
            from langchain_google_genai import ChatGoogleGenerativeAI

            # Get API key from environment
            gemini_api_key = os.getenv('GEMINI_API_KEY')

            # Resolve Gemini models dynamically from the Super Admin's AiModel table
            from .model_resolver import get_active_models
            models_to_try = [m.model_name for m in get_active_models(provider='gemini')]

            response_content = None
            model_used = None

            for model_name in models_to_try:
                try:
                    current_app.logger.info(f"🤖 Trying Gemini model: {model_name}")

                    extraction_client = ChatGoogleGenerativeAI(
                        model=model_name,
                        temperature=0.3,
                        max_output_tokens=4000,  # Reduced to avoid quota issues
                        google_api_key=gemini_api_key
                    )

                    # Invoke the model with the prompt
                    from langchain_core.messages import HumanMessage
                    response = extraction_client.invoke([HumanMessage(content=prompt)])

                    # Extract content from response
                    if hasattr(response, 'content'):
                        response_content = response.content
                    elif isinstance(response, dict):
                        response_content = response.get('content', '')
                    else:
                        response_content = str(response)

                    if response_content and len(response_content) > 100:
                        model_used = model_name
                        current_app.logger.info(f"✅ Gemini extraction successful with {model_name}: {len(response_content)} chars")
                        break

                except Exception as model_error:
                    error_str = str(model_error)
                    current_app.logger.warning(f"⚠️ Model {model_name} failed: {error_str[:100]}")

                    # Check for quota exceeded error
                    if "quota" in error_str.lower() or "429" in error_str:
                        current_app.logger.warning(f"🚫 Quota exceeded for {model_name}, skipping remaining models")
                        break  # Stop trying other models if quota is exceeded

                    continue

            if response_content:
                response_data = {
                    "content": response_content,
                    "usage": {},
                    "model": model_used
                }
            else:
                raise Exception("All Gemini models failed")

        except Exception as e:
            current_app.logger.error(f"❌ All Gemini models failed: {e}")
            # Don't fallback to regular LLM service - it has token limits
            # Instead, return None to trigger BeautifulSoup fallback extraction
            response_data = None

        if response_data and response_data.get("content"):
            extracted_content = response_data["content"].strip()

            # Log usage details if available
            usage = response_data.get("usage")
            if usage:
                current_app.logger.info(f"📊 Gemini usage for {url}: {usage['total_tokens']} total tokens")

            # Post-process the extracted content
            if extracted_content:
                # Clean up common AI response artifacts
                extracted_content = self._postprocess_content(extracted_content)
                current_app.logger.info(f"✅ Gemini returned content of length {len(extracted_content)} for {url}")
                current_app.logger.debug(f"🔍 Gemini response preview for {url}: {extracted_content[:200]}...")
            else:
                current_app.logger.warning(f"⚠️ Gemini returned an empty response for {url}")

            return extracted_content
        else:
            current_app.logger.error(f"❌ Failed to get a valid response from LLMService for {url}")
            return None

    def _preprocess_html(self, html_content: str) -> str:
        """Clean HTML before sending to Gemini to improve extraction quality."""
        import re

        # Remove script and style tags completely
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

        # Remove common navigation and noise elements
        noise_patterns = [
            r'<nav[^>]*>.*?</nav>',
            r'<header[^>]*>.*?</header>',
            r'<footer[^>]*>.*?</footer>',
            r'<aside[^>]*>.*?</aside>',
            r'<div[^>]*class="[^"]*(?:nav|menu|sidebar|ad|advertisement|popup|cookie|social|share)[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*(?:nav|menu|sidebar|ad|advertisement|popup|cookie|social|share)[^"]*"[^>]*>.*?</div>',
        ]

        for pattern in noise_patterns:
            html_content = re.sub(pattern, '', html_content, flags=re.DOTALL | re.IGNORECASE)

        # Clean up excessive whitespace
        html_content = re.sub(r'\s+', ' ', html_content)

        return html_content.strip()

    def _postprocess_content(self, content: str) -> str:
        """Clean up extracted content from common AI response artifacts."""
        import re

        # Remove common AI response prefixes
        prefixes_to_remove = [
            r'^Here is the extracted content:?\s*',
            r'^The extracted content is:?\s*',
            r'^Based on the HTML, here is the main content:?\s*',
            r'^The main content from the webpage is:?\s*',
        ]

        for prefix in prefixes_to_remove:
            content = re.sub(prefix, '', content, flags=re.IGNORECASE | re.MULTILINE)

        # Clean up excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Max 2 consecutive newlines
        content = re.sub(r'[ \t]+', ' ', content)  # Clean up spaces and tabs

        return content.strip()

    def _check_extraction_quality(self, content: str, url: str) -> str:
        """Check if extracted content meets quality standards. Returns issue description or empty string."""

        # Check minimum length - be more lenient for comprehensive extraction
        if len(content.strip()) < 50:
            return "Content too short (less than 50 characters)"

        # Check for common failure patterns (only critical ones)
        failure_patterns = [
            ("<!doctype", "Contains raw HTML"),
            ("no meaningful text content was found", "AI reported no meaningful content"),
            ("heavily obfuscated", "AI detected obfuscated content"),
            ("compressed, or encrypted", "AI detected encrypted content"),
            ("impossible to extract any useful information", "AI could not extract information"),
            ("non-standard characters and binary data", "AI detected binary data"),
            ("provided html content is not in a human-readable", "AI detected unreadable content"),
        ]

        content_lower = content.lower()
        for pattern, issue in failure_patterns:
            if pattern in content_lower:
                return issue

        # Check content-to-HTML ratio (if content is mostly HTML tags)
        import re
        html_tags = len(re.findall(r'<[^>]+>', content))
        if html_tags > len(content) / 20:  # More than 5% HTML tags (increased tolerance)
            return "Content contains too many HTML tags"

        # REMOVED: Repetitive content check - for comprehensive extraction, some repetition is OK
        # (e.g., pricing tables, feature lists with similar formatting)

        return ""  # No quality issues found

    # ==================== FULL SITE CRAWLING METHODS ====================

    def _discover_website_urls(self, start_url: str, base_domain: str) -> List[Dict[str, Any]]:
        """
        Robust multi-strategy URL discovery (rewrite 2026-06-06).

        Discovery sources, tried in order until we have enough URLs:
            1. The start URL itself is always first
            2. Sitemap (10+ paths + sitemap_index + page-sitemaps + robots.txt)
            3. RSS / Atom feeds
            4. Internal links from the start URL (via multiple fetchers: requests, cloudscraper)
            5. Wayback Machine CDX API (when internal links are JS-rendered or empty)
            6. Common-path probing (about, contact, products, services, etc.) as last resort

        Filtering is intentionally conservative: we keep anything that is a valid
        crawlable URL, only excluding obvious non-content (assets, admin, login, etc.).
        """
        discovered_urls: List[Dict[str, Any]] = []
        unique_urls: Set[str] = set()

        current_app.logger.info(f"🔍 Discovering URLs for {base_domain} (multi-strategy)")

        def add(url: str, depth: int, source: str, priority: int) -> None:
            url = (url or '').strip()
            if not url:
                return
            if not self._is_valid_crawl_url(url):
                return
            if not self._is_content_page(url):
                return
            if url in unique_urls:
                return
            unique_urls.add(url)
            discovered_urls.append({
                'url': url,
                'depth': depth,
                'source': source,
                'priority': priority,
            })

        # 1. The start URL is always first
        add(start_url, 0, 'start', 0)
        if not start_url.endswith('/'):
            add(start_url.rstrip('/') + '/', 0, 'start', 0)

        # 2. Sitemap discovery (covers robots.txt Sitemap: directive + multiple sitemaps)
        sitemap_urls = self._get_sitemap_urls(base_domain)
        for url in sitemap_urls:
            add(url, 0, 'sitemap', 1)

        # 3. RSS / Atom feed discovery
        feed_urls = self._get_feed_urls(start_url, base_domain)
        for url in feed_urls:
            add(url, 0, 'feed', 2)

        # 4. Internal links from the start URL via the multi-strategy fetcher
        if len(discovered_urls) < 5:
            page_links = self._extract_internal_links_robust(start_url, base_domain)
            for link in page_links:
                add(link, 1, 'homepage', 2)

        # 5. Wayback Machine CDX API — gives us every URL ever archived for the domain
        if len(discovered_urls) < 5:
            wayback_urls = self._get_wayback_urls(base_domain, limit=self.max_pages * 2)
            for link in wayback_urls:
                add(link, 1, 'wayback', 3)

        # 6. DuckDuckGo search fallback — `site:domain.com` query
        if len(discovered_urls) < 5:
            search_urls = self._get_search_urls(base_domain, limit=30)
            for link in search_urls:
                add(link, 1, 'search', 3)

        # 7. Common-path probing as a final safety net
        if len(discovered_urls) < 5:
            for guessed in self._get_common_paths(base_domain):
                add(guessed, 0, 'common-path', 2)

        # Sort by priority then depth, then dedupe
        discovered_urls.sort(key=lambda x: (x['priority'], x['depth'], x['url']))
        # De-dupe while preserving order
        seen = set()
        deduped = []
        for info in discovered_urls:
            if info['url'] in seen:
                continue
            seen.add(info['url'])
            deduped.append(info)
        discovered_urls = deduped[:self.max_pages]
        self.total_discovered_pages = len(discovered_urls)

        current_app.logger.info(
            f"✅ Discovered {len(discovered_urls)} URLs "
            f"(sources: {dict((s, sum(1 for u in discovered_urls if u['source']==s)) for s in {u['source'] for u in discovered_urls})})"
        )
        return discovered_urls

    # ===================================================================
    # Multi-strategy URL discovery (2026-06-06 rewrite)
    # ===================================================================

    SITEMAP_PATHS = [
        '/sitemap.xml',
        '/sitemap_index.xml',
        '/sitemaps.xml',
        '/sitemap/sitemap.xml',
        '/sitemap-index.xml',
        '/sitemap.php',
        '/sitemap.txt',
        '/wp-sitemap.xml',
        '/post-sitemap.xml',
        '/page-sitemap.xml',
        '/product-sitemap.xml',
        '/category-sitemap.xml',
        '/news-sitemap.xml',
    ]

    FEED_PATHS = [
        '/feed',
        '/feed/',
        '/feed.xml',
        '/feed.json',
        '/rss',
        '/rss.xml',
        '/rss/',
        '/atom.xml',
        '/atom/',
        '/index.xml',
        '/blog/feed',
    ]

    COMMON_PATHS = [
        '/', '/about', '/about-us', '/about/', '/contact', '/contact-us', '/contact/',
        '/products', '/products/', '/services', '/services/', '/solutions', '/solutions/',
        '/company', '/company/', '/team', '/team/', '/info', '/info/',
        '/help', '/help/', '/support', '/support/', '/faq', '/faq/',
        '/pricing', '/pricing/', '/features', '/features/',
        '/blog', '/blog/', '/news', '/news/',
    ]

    def _get_sitemap_urls(self, base_domain: str) -> List[str]:
        """Multi-path sitemap discovery. Tries robots.txt Sitemap: directive first,
        then a long list of common sitemap paths. Uses a tight per-path timeout so
        discovery stays fast even on sites with no sitemaps."""
        sitemap_urls: List[str] = []
        seen: Set[str] = set()

        # 1. robots.txt Sitemap: directive
        try:
            resp = self._fetch_url(f"{base_domain}/robots.txt", timeout=5)
            if resp and resp.get('content'):
                for ref in re.findall(r'(?im)^\s*Sitemap\s*:\s*(\S+)', resp['content']):
                    ref = ref.strip()
                    if ref and ref not in seen:
                        seen.add(ref)
                        for u in self._fetch_and_parse_sitemap(ref):
                            if u not in sitemap_urls:
                                sitemap_urls.append(u)
        except Exception:  # noqa: BLE001
            pass

        # 2. Try each common sitemap path with a short timeout
        for path in self.SITEMAP_PATHS:
            url = f"{base_domain}{path}"
            if url in seen:
                continue
            seen.add(url)
            for u in self._fetch_and_parse_sitemap(url):
                if u not in sitemap_urls:
                    sitemap_urls.append(u)
            if len(sitemap_urls) >= 500:
                break

        return list(dict.fromkeys(sitemap_urls))  # de-dup, preserve order

    def _fetch_and_parse_sitemap(self, url: str) -> List[str]:
        """Fetch a sitemap URL and return the URLs inside it. Handles sitemap_index too."""
        try:
            resp = self._fetch_url(url, timeout=5)
        except Exception:  # noqa: BLE001
            return []
        if not resp or not resp.get('content'):
            return []
        return self._parse_sitemap_xml(resp['content'])

    def _parse_sitemap_xml(self, xml_content: str) -> List[str]:
        """Parse sitemap XML, including <sitemapindex> (recursive)."""
        urls: List[str] = []
        if not xml_content:
            return urls

        # Find all <loc>...</loc> values
        locs = re.findall(r'<loc[^>]*>(.*?)</loc>', xml_content, flags=re.IGNORECASE | re.DOTALL)
        for loc in locs:
            loc = loc.strip()
            if not loc:
                continue
            if loc.lower().endswith('.xml') and '<sitemap' in xml_content.lower():
                # Sitemap index — recurse
                try:
                    sub = self._fetch_and_parse_sitemap(loc)
                    urls.extend(sub)
                except Exception:  # noqa: BLE001
                    continue
            else:
                if loc.startswith('http'):
                    urls.append(loc)

        return list(dict.fromkeys(urls))

    def _get_feed_urls(self, start_url: str, base_domain: str) -> List[str]:
        """Discover RSS / Atom feed URLs from a discovery path list and parse them
        for item URLs. Handles RSS 2.0, Atom 1.0, and RDF."""
        feed_urls: List[str] = []

        for path in self.FEED_PATHS:
            url = f"{base_domain}{path}"
            try:
                resp = self._fetch_url(url, timeout=5)
            except Exception:  # noqa: BLE001
                resp = None
            if not resp or not resp.get('content'):
                continue
            content = resp['content']
            low = content[:2000].lower()
            is_feed = '<item' in low or '<entry' in low or '<rss' in low or '<feed' in low or '<rdf' in low
            if not is_feed:
                continue
            current_app.logger.info(f"📡 Found feed at {url}")

            # RSS 2.0: <item><link>URL</link></item>
            for m in re.finditer(r'<item\b[^>]*>(.*?)</item>', content, flags=re.IGNORECASE | re.DOTALL):
                item_xml = m.group(1)
                link_m = re.search(r'<link[^>]*>(.*?)</link>', item_xml, flags=re.IGNORECASE | re.DOTALL)
                if link_m:
                    u = link_m.group(1).strip()
                    if u.startswith('http') and self._is_internal_url(u, urlparse(base_domain).netloc):
                        feed_urls.append(u)

            # Atom 1.0: <entry><link href="URL"/></entry>
            for m in re.finditer(r'<entry\b[^>]*>(.*?)</entry>', content, flags=re.IGNORECASE | re.DOTALL):
                entry_xml = m.group(1)
                link_m = re.search(r'<link[^>]*href=["\']([^"\']+)["\']', entry_xml, flags=re.IGNORECASE)
                if link_m:
                    u = link_m.group(1).strip()
                    if u.startswith('http') and self._is_internal_url(u, urlparse(base_domain).netloc):
                        feed_urls.append(u)

            if feed_urls:
                break  # we found a feed; no need to try more paths

        return list(dict.fromkeys(feed_urls))[:50]

    def _get_search_urls(self, base_domain: str, limit: int = 30) -> List[str]:
        """DuckDuckGo HTML search fallback for `site:domain.com` queries.
        This is a last-resort URL source when sitemaps, feeds, internal links, and
        Wayback all fail. DDG HTML is more permissive than Google."""
        urls: List[str] = []
        host = urlparse(base_domain).netloc
        if not host:
            return urls
        query = f"site:{host}"
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={query}"
            resp = self._fetch_url(search_url, timeout=10, allow_cloudscraper=True)
        except Exception:  # noqa: BLE001
            return urls
        if not resp or not resp.get('content'):
            return urls
        html = resp['content']
        # DDG wraps results in <a class="result__a" href="URL">TITLE</a>
        for m in re.finditer(r'class=["\']result__a["\'][^>]*href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
            u = m.group(1).strip()
            # DDG sometimes uses redirect URLs like //duckduckgo.com/l/?uddg=...
            if 'uddg=' in u:
                real = re.search(r'uddg=([^&]+)', u)
                if real:
                    from urllib.parse import unquote
                    u = unquote(real.group(1))
            if self._is_internal_url(u, host):
                urls.append(u)
            if len(urls) >= limit:
                break
        return list(dict.fromkeys(urls))

    def _get_wayback_urls(self, base_domain: str, limit: int = 200) -> List[str]:
        """Fetch all known URLs for the domain from the Wayback Machine CDX API."""
        urls: List[str] = []
        try:
            parsed = urlparse(base_domain)
            host = parsed.netloc or parsed.path
            cdx_url = (
                f"https://web.archive.org/cdx/search/cdx"
                f"?url={host}/*&output=json&fl=original&limit={limit}&filter=statuscode:200&collapse=urlkey"
            )
            resp = self._fetch_url(cdx_url, timeout=15, allow_cloudscraper=False)
            if not resp or not resp.get('content'):
                return urls
            data = json.loads(resp['content'])
            if not data or len(data) < 2:
                return urls
            # First row is the header, data rows follow
            for row in data[1:]:
                if row and isinstance(row, list) and row[0]:
                    u = row[0]
                    if not u.startswith('http'):
                        u = f"{parsed.scheme}://{host}{u if u.startswith('/') else '/' + u}"
                    urls.append(u)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.debug(f"Wayback CDX failed: {exc}")
        return urls

    def _get_common_paths(self, base_domain: str) -> List[str]:
        """Probe a small set of common page paths (HEAD requests only). Returns only paths that return 200."""
        alive: List[str] = []
        for path in self.COMMON_PATHS:
            url = f"{base_domain}{path}"
            try:
                resp = self.session.head(url, timeout=5, allow_redirects=True)
                if resp.status_code == 200:
                    alive.append(url)
            except Exception:  # noqa: BLE001
                continue
        return alive

    # ===================================================================
    # Multi-strategy page fetching
    # ===================================================================

    def _is_binary_content(self, text: str) -> bool:
        """Detect if extracted text is actually compressed/binary garbage."""
        if not text:
            return False
        # Check for high ratio of non-printable characters
        sample = text[:2000]
        non_printable = sum(1 for c in sample if ord(c) < 32 and c not in '\n\r\t')
        return non_printable > len(sample) * 0.15

    def _decompress_response(self, resp) -> str:
        """Safely decompress a response, handling edge cases where
        requests/r.content doesn't auto-decode."""
        import gzip
        import zlib
        # If requests already decoded it, r.text will be clean
        text = resp.text
        if not self._is_binary_content(text):
            return text
        # Try manual decompression from raw bytes
        raw = resp.content
        for decoder in (gzip.decompress, zlib.decompress, zlib.decompressobj(-zlib.MAX_WBITS).decompress):
            try:
                decoded = decoder(raw)
                result = decoded.decode('utf-8', errors='replace')
                if not self._is_binary_content(result):
                    return result
            except Exception:
                continue
        # Last resort: force decode as utf-8 with replacement
        return raw.decode('utf-8', errors='replace')

    def _fetch_url(self, url: str, timeout: int = 15, allow_cloudscraper: bool = True) -> Optional[Dict[str, Any]]:
        """Fetch a URL with a 3-tier strategy:
            1. `cloudscraper` first (bypasses Cloudflare / anti-bot) — works on most protected sites
            2. `requests` session as a fast fallback
            3. `httpx` as a modern alternative
        Returns {'content', 'status_code', 'headers', 'url'} or None.
        """
        last_error = None

        # Tier 1: cloudscraper (handles Cloudflare, anti-bot, JA3 fingerprinting)
        if allow_cloudscraper and _HAS_CLOUDSCRAPER:
            try:
                scraper = cloudscraper.create_scraper(
                    browser={'browser': 'chrome', 'platform': 'linux', 'desktop': True}
                )
                scraper.headers.update(self.session.headers)
                r = scraper.get(url, timeout=timeout)
                if r.status_code == 200:
                    text = self._decompress_response(r)
                    if text and len(text.strip()) > 100:
                        if not self._looks_blocked(text):
                            return {
                                'content': text,
                                'status_code': r.status_code,
                                'headers': dict(r.headers),
                                'url': r.url,
                                'method': 'cloudscraper',
                            }
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        # Tier 2: requests (fast, works on unprotected sites)
        try:
            self._rotate_user_agent()
            r = self.session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                text = self._decompress_response(r)
                if text and len(text.strip()) > 100:
                    if not self._looks_blocked(text):
                        return {
                            'content': text,
                            'status_code': r.status_code,
                            'headers': dict(r.headers),
                            'url': r.url,
                            'method': 'requests',
                        }
        except Exception as exc:  # noqa: BLE001
            last_error = exc

        # Tier 3: httpx
        if _HAS_HTTPX:
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True, headers=self.session.headers) as client:
                    r = client.get(url)
                    if r.status_code == 200:
                        text = self._decompress_response(r)
                        if text and len(text.strip()) > 100:
                            if not self._looks_blocked(text):
                                return {
                                    'content': text,
                                    'status_code': r.status_code,
                                    'headers': dict(r.headers),
                                    'url': str(r.url),
                                    'method': 'httpx',
                                }
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error:
            current_app.logger.debug(f"All fetch strategies failed for {url}: {last_error}")
        return None

    @staticmethod
    def _looks_blocked(html: str) -> bool:
        """Heuristic to detect a Cloudflare / WAF / captcha challenge page."""
        if not html:
            return True
        low = html.lower()
        if len(html.strip()) < 800:
            # Tiny pages that just say "checking your browser" are blocked
            blocked_phrases = [
                'checking your browser before accessing',
                'just a moment',
                'attention required',
                'access denied',
                'please complete the security check',
                'ddos protection by',
                'this site is blocked',
                'request rejected',
                'your request has been blocked',
            ]
            return any(p in low for p in blocked_phrases)
        # For larger pages, only flag obvious block pages
        blocked_phrases = [
            'ddos protection by',
            'attention required! | cloudflare',
            'please complete the security check to access',
        ]
        return any(p in low for p in blocked_phrases)

    # ===================================================================
    # Multi-strategy link extraction
    # ===================================================================

    def _extract_internal_links_robust(self, page_url: str, base_domain: str) -> List[str]:
        """Robust link extraction: tries multi-strategy fetch, then parses
        <a href>, <link href>, <area href>, <iframe src>, and inline JSON
        navigations."""
        internal: Set[str] = set()
        parsed_base = urlparse(base_domain)
        base_host = parsed_base.netloc

        try:
            resp = self._fetch_url(page_url, timeout=20)
        except Exception:  # noqa: BLE001
            resp = None
        if not resp or not resp.get('content'):
            return []

        html = resp['content']
        # 1. Standard <a href>
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup.find_all(['a', 'link', 'area']):
                href = tag.get('href')
                if not href:
                    continue
                abs_url = urljoin(page_url, href)
                if self._is_internal_url(abs_url, base_host):
                    internal.add(self._normalize_url(abs_url))
        except Exception as exc:  # noqa: BLE001
            current_app.logger.debug(f"BS4 link extraction failed: {exc}")

        # 2. Regex-based extraction of hrefs (catches JS templates, JSON-LD, etc.)
        try:
            for href in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
                abs_url = urljoin(page_url, href)
                if self._is_internal_url(abs_url, base_host):
                    internal.add(self._normalize_url(abs_url))
        except Exception:  # noqa: BLE001
            pass

        # 3. Inline JSON paths ("url":"/about")
        try:
            for href in re.findall(r'"(?:url|path|href|to|link)"\s*:\s*"(/[^"]+)"', html):
                abs_url = urljoin(page_url, href)
                if self._is_internal_url(abs_url, base_host):
                    internal.add(self._normalize_url(abs_url))
        except Exception:  # noqa: BLE001
            pass

        return list(internal)

    def _is_internal_url(self, url: str, base_host: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:  # noqa: BLE001
            return False
        if parsed.scheme not in ('http', 'https'):
            return False
        if not parsed.netloc:
            return False
        # Same host, or subdomain of the same registrable domain
        if parsed.netloc == base_host:
            return True
        if base_host and (parsed.netloc.endswith('.' + base_host) or base_host.endswith('.' + parsed.netloc)):
            return True
        return False

    @staticmethod
    def _normalize_url(url: str) -> str:
        try:
            p = urlparse(url)
            return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ''))
        except Exception:  # noqa: BLE001
            return url

    def _is_valid_crawl_url(self, url: str) -> bool:
        """Check if URL is valid for crawling."""

        # Skip certain file types and patterns
        skip_patterns = [
            r'\.(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|tar|gz)$',
            r'\.(jpg|jpeg|png|gif|bmp|svg|ico|webp)$',
            r'\.(css|js|json|xml|txt)$',
            r'/(wp-admin|admin|login|register|logout|cart|checkout)',
            r'/(api|ajax|webhook)',
            r'[?&](utm_|ref=|src=)',  # Tracking parameters
            r'#',  # Fragment-only URLs
            r'mailto:|tel:|javascript:|ftp:'
        ]

        url_lower = url.lower()
        for pattern in skip_patterns:
            if re.search(pattern, url_lower):
                return False

        return True

    def _is_content_page(self, url: str) -> bool:
        """Check if URL is a content page (not sitemap, XSL, etc.)."""

        # Skip non-content file types
        non_content_patterns = [
            r'\.xml$',  # XML files (sitemaps, etc.)
            r'\.xsl$',  # XSL stylesheets
            r'\.rss$',  # RSS feeds
            r'\.atom$',  # Atom feeds
            r'sitemap',  # Any sitemap-related URLs
            r'robots\.txt$',  # Robots.txt
            r'\.json$',  # JSON files
            r'/feed/',   # Feed URLs
            r'/rss/',    # RSS URLs
        ]

        url_lower = url.lower()
        for pattern in non_content_patterns:
            if re.search(pattern, url_lower):
                return False

        return True

    def _is_important_for_chatbot(self, url: str) -> bool:
        """Permissive filter (rewrite 2026-06-06) — we used to aggressively skip
        /blog, /category, etc. The new multi-strategy discovery no longer calls
        this. Kept as a permissive no-op so any external caller does not get
        the old broken behavior. Real filtering is now done by the user
        (max_pages) and by _is_valid_crawl_url (assets, admin, login, etc.)."""
        return True

    def _process_crawl_queue(self, base_domain: str):
        """Process the crawling queue with threading for efficiency."""
        current_app.logger.info(f"🚀 Processing crawl queue with {len(self.url_queue)} URLs")

        # Use ThreadPoolExecutor for concurrent crawling (increase for parallelism)
        max_workers = max(1, min(10, len(self.url_queue)))  # Process 1-10 pages in parallel

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit crawling tasks
            future_to_url = {}

            while self.url_queue and len(self.crawled_urls) < self.max_pages:
                # Get next batch of URLs
                batch_size = min(10, len(self.url_queue))
                batch_futures = []

                for _ in range(batch_size):
                    if not self.url_queue:
                        break

                    url_info = self.url_queue.popleft()
                    url = url_info['url']

                    # Skip if already crawled
                    if url in self.crawled_urls or url in self.failed_urls:
                        continue

                    # Submit crawling task
                    future = executor.submit(self._crawl_single_page, url, url_info['depth'])
                    future_to_url[future] = url
                    batch_futures.append(future)

                # Process completed futures with longer timeout and better error handling
                try:
                    for future in as_completed(batch_futures, timeout=60):
                        url = future_to_url[future]
                        try:
                            result = future.result()
                            if result:
                                with self.crawl_lock:
                                    self.extracted_content.append(result)
                                    self.crawled_urls.add(url)
                                    current_app.logger.info(f"✅ Crawled [{len(self.crawled_urls)}/{self.total_discovered_pages}]: {url}")

                                    # Send progress update via callback
                                    if self.progress_callback:
                                        try:
                                            progress_percent = int((len(self.crawled_urls) / self.total_discovered_pages) * 100) if self.total_discovered_pages > 0 else 0
                                            self.progress_callback({
                                                'pages_crawled': len(self.crawled_urls),
                                                'total_pages': self.total_discovered_pages,
                                                'progress_percent': progress_percent,
                                                'pages_failed': len(self.failed_urls),
                                                'current_page': url
                                            })
                                        except Exception as cb_error:
                                            current_app.logger.warning(f"Progress callback error: {cb_error}")
                            else:
                                with self.crawl_lock:
                                    self.failed_urls.add(url)

                        except Exception as e:
                            current_app.logger.debug(f"❌ Failed to crawl {url}: {e}")
                            with self.crawl_lock:
                                self.failed_urls.add(url)

                except Exception:
                    # Handle timeout - process completed futures and cancel remaining
                    completed_count = sum(1 for f in batch_futures if f.done())
                    unfinished_count = len(batch_futures) - completed_count

                    current_app.logger.warning(f"⚠️ Batch timeout after 60s: {completed_count} completed, {unfinished_count} unfinished")

                    # Process any completed futures first
                    for future, url in future_to_url.items():
                        if future.done() and not future.cancelled():
                            try:
                                result = future.result()
                                if result:
                                    with self.crawl_lock:
                                        self.extracted_content.append(result)
                                        self.crawled_urls.add(url)
                                        current_app.logger.info(f"✅ Crawled [{len(self.crawled_urls)}/{self.total_discovered_pages}]: {url}")

                                        # Send progress update via callback
                                        if self.progress_callback:
                                            try:
                                                progress_percent = int((len(self.crawled_urls) / self.total_discovered_pages) * 100) if self.total_discovered_pages > 0 else 0
                                                self.progress_callback({
                                                    'pages_crawled': len(self.crawled_urls),
                                                    'total_pages': self.total_discovered_pages,
                                                    'progress_percent': progress_percent,
                                                    'pages_failed': len(self.failed_urls)
                                                })
                                            except Exception as cb_error:
                                                current_app.logger.warning(f"Progress callback error: {cb_error}")
                                else:
                                    with self.crawl_lock:
                                        self.failed_urls.add(url)
                            except Exception as e:
                                with self.crawl_lock:
                                    self.failed_urls.add(url)
                                current_app.logger.debug(f"❌ Failed to get result from {url}: {e}")

                    # Cancel and mark remaining futures as failed
                    for future, url in future_to_url.items():
                        if not future.done():
                            future.cancel()
                            with self.crawl_lock:
                                self.failed_urls.add(url)
                            current_app.logger.debug(f"⏰ Cancelled slow crawl: {url}")

                # Add brief delay between batches
                if self.crawl_delay > 0:
                    time.sleep(max(0.2, self.crawl_delay * 0.5))

    def _crawl_single_page(self, url: str, depth: int) -> Optional[Dict[str, Any]]:
        """Robust single-page crawl with multi-strategy fetching and multi-strategy
        extraction. Returns a content dict or None on total failure."""
        # 1. Fetch the page with multi-strategy fetcher
        try:
            resp = self._fetch_url(url, timeout=30, allow_cloudscraper=True)
        except Exception:  # noqa: BLE001
            resp = None
        if not resp or not resp.get('content'):
            # Wayback fallback for the start URL
            if depth == 0:
                try:
                    wayback_html = self._fetch_from_wayback(url)
                    if wayback_html:
                        resp = {'content': wayback_html, 'status_code': 200, 'url': url, 'method': 'wayback'}
                except Exception:  # noqa: BLE001
                    pass
        if not resp or not resp.get('content'):
            print(f"❌ Could not fetch {url} with any strategy")
            return None

        html_content = resp['content']
        # 2. Extract content with the multi-strategy extractor
        extracted = self._extract_content_multi(html_content, url)
        if not extracted or not extracted.strip():
            return None
        if len(extracted.strip()) < 80:
            # Content is too thin to be useful
            return None

        return {
            'url': url,
            'content': extracted,
            'depth': depth,
            'extraction_method': resp.get('method', 'requests'),
            'timestamp': datetime.now().isoformat()
        }

    # ===================================================================
    # Multi-strategy content extraction
    # ===================================================================

    def _extract_content_multi(self, html: str, url: str) -> str:
        """Extract clean text from HTML using a fallback chain:
            1. trafilatura (best for article-style content)
            2. readability-lxml (Mozilla algorithm)
            3. justext (paragraph-based heuristic)
            4. html2text (markdown conversion of cleaned HTML)
            5. BeautifulSoup custom heuristics
        """
        # 1. trafilatura
        if _HAS_TRAFILATURA:
            try:
                out = trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=True,
                    include_links=False,
                    include_images=False,
                    favor_recall=True,
                    no_fallback=False,
                    with_metadata=False,
                )
                if out and len(out.strip()) > 200:
                    return self._postprocess_content(out)
            except Exception:  # noqa: BLE001
                pass

        # 2. readability-lxml
        if _HAS_READABILITY:
            try:
                doc = ReadabilityDocument(html, url=url)
                summary = doc.summary(html_partial=True)
                if summary:
                    soup = BeautifulSoup(summary, 'html.parser')
                    text = soup.get_text(separator='\n', strip=True)
                    text = re.sub(r'\n{3,}', '\n\n', text)
                    if text and len(text.strip()) > 200:
                        return self._postprocess_content(text)
            except Exception:  # noqa: BLE001
                pass

        # 3. justext
        if _HAS_JUSTEXT:
            try:
                from justext import get_stoplist  # type: ignore
                paragraphs = justext.justext(
                    html.encode('utf-8', 'ignore'),
                    get_stoplist('English'),
                )
                good = [p.text for p in paragraphs if not p.is_boilerplate and len(p.text.strip()) > 30]
                if good:
                    text = '\n\n'.join(good)
                    if len(text.strip()) > 200:
                        return self._postprocess_content(text)
            except Exception:  # noqa: BLE001
                pass

        # 4. html2text on a BS4-cleaned page
        if _HAS_HTML2TEXT:
            try:
                soup = BeautifulSoup(html, 'html.parser')
                for tag in soup(['script', 'style', 'noscript']):
                    tag.decompose()
                h = html2text.HTML2Text()
                h.ignore_links = True
                h.ignore_images = True
                h.body_width = 0
                md = h.handle(str(soup))
                if md and len(md.strip()) > 200:
                    return self._postprocess_content(md)
            except Exception:  # noqa: BLE001
                pass

        # 5. BeautifulSoup custom heuristics
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup(['script', 'style', 'noscript', 'iframe', 'header', 'footer', 'nav', 'aside']):
                tag.decompose()
            text = soup.get_text(separator='\n', strip=True)
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            if text and len(text.strip()) > 200:
                return self._postprocess_content(text)
        except Exception:  # noqa: BLE001
            pass

        # 6. Last-ditch: just return whatever we have from BS4
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup(['script', 'style']):
                tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return self._postprocess_content(text)
        except Exception:  # noqa: BLE001
            return ''

    def _fetch_from_wayback(self, url: str) -> Optional[str]:
        """Try to get the latest archived snapshot of `url` from the Wayback Machine."""
        try:
            # CDX API: find the most recent snapshot
            cdx = f"https://web.archive.org/cdx/search/cdx?url={url}&output=json&limit=1&fl=timestamp,original,statuscode&filter=statuscode:200"
            resp = self._fetch_url(cdx, timeout=10, allow_cloudscraper=False)
            if not resp or not resp.get('content'):
                return None
            data = json.loads(resp['content'])
            if not data or len(data) < 2:
                return None
            ts = data[1][0]
            archive_url = f"https://web.archive.org/web/{ts}id_/{url}"
            r = self._fetch_url(archive_url, timeout=20, allow_cloudscraper=True)
            if r and r.get('content'):
                return r['content']
        except Exception:  # noqa: BLE001
            return None
        return None

    def _fetch_page_content_direct(self, url: str) -> Optional[str]:
        """Thread-safe direct HTTP fetching without Flask context dependencies."""
        try:
            # Rotate user agent
            self._rotate_user_agent()

            # Direct HTTP request with timeout
            response = self.session.get(url, timeout=30, allow_redirects=True)

            if response.status_code == 200:
                return response.text
            else:
                print(f"❌ HTTP {response.status_code} for {url}")
                return None

        except Exception as e:
            print(f"❌ Failed to fetch {url}: {e}")
            return None

    def _preprocess_html_content_safe(self, html_content: str, url: str) -> Optional[str]:
        """Thread-safe HTML preprocessing using BeautifulSoup."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove only script and style elements
            unwanted_tags = ['script', 'style', 'noscript', 'iframe']
            for tag in unwanted_tags:
                for element in soup.find_all(tag):
                    element.decompose()

            # Keep navigation and menu content but remove ads and tracking
            unwanted_selectors = [
                '[class*="advertisement"]', '[class*="cookie"]', '[class*="tracking"]',
                '[class*="popup"]', '[class*="modal"]', '[class*="overlay"]',
                '[id*="cookie"]', '[id*="popup"]', '[id*="modal"]'
            ]

            for selector in unwanted_selectors:
                try:
                    for element in soup.select(selector):
                        element.decompose()
                except Exception:
                    continue

            # Log the content size (use print for thread safety)
            print(f"📝 Raw HTML size: {len(html_content)} chars")

            # Extract meaningful text content
            text_elements = []

            # Get all text-containing elements with better content extraction
            for element in soup.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th', 'article', 'section', 'main']):
                text = element.get_text(strip=True)
                if text and len(text) > 5:  # Keep more content, filter less aggressively
                    # Only skip very generic navigation text
                    text_lower = text.lower()
                    skip_phrases = ['click here', 'read more', 'learn more']
                    if not any(phrase in text_lower for phrase in skip_phrases):
                        # Log meaningful content found (use print for thread safety)
                        if len(text) > 100:  # Log substantial content for debugging
                            print(f"📄 Found content block ({len(text)} chars): {text[:100]}...")
                        text_elements.append(text)

            # Combine and clean
            combined_text = '\n'.join(text_elements)

            # Basic cleanup
            lines = combined_text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line and len(line) > 5:  # Skip very short lines
                    cleaned_lines.append(line)

            result = '\n'.join(cleaned_lines)
            print(f"✅ Preprocessed {url}: {len(result)} chars")
            return result

        except Exception as e:
            print(f"❌ HTML preprocessing failed for {url}: {e}")
            return html_content  # Return original content as fallback

    def _extract_structured_content_safe(self, content: str, url: str) -> Optional[str]:
        """Thread-safe structured content extraction using BeautifulSoup."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            info_parts = []

            # Extract title
            title = soup.find('title')
            if title:
                info_parts.append(f"# {title.get_text().strip()}")
                info_parts.append("")

            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                info_parts.append("## Overview")
                info_parts.append(meta_desc.get('content').strip())
                info_parts.append("")

            # Extract main content
            main_content = []

            # Look for headings and content
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                heading_text = heading.get_text().strip()
                if heading_text and len(heading_text) < 200:
                    level = int(heading.name[1])  # h1 -> 1, h2 -> 2, etc.
                    prefix = "#" * (level + 1)  # h1 -> ##, h2 -> ###, etc.
                    main_content.append(f"{prefix} {heading_text}")

                    # Get content after this heading
                    next_elements = []
                    for sibling in heading.find_next_siblings():
                        if sibling.name and sibling.name.startswith('h'):
                            break  # Stop at next heading
                        text = sibling.get_text(strip=True)
                        if text and len(text) > 20:
                            next_elements.append(text)
                        if len(next_elements) >= 3:  # Limit content per section
                            break

                    if next_elements:
                        main_content.extend(next_elements)
                        main_content.append("")

            # If no structured content found, extract paragraphs
            if not main_content:
                main_content.append("## Content")
                paragraphs = soup.find_all('p')
                for p in paragraphs[:10]:  # Limit to first 10 paragraphs
                    text = p.get_text().strip()
                    if text and len(text) > 30:
                        main_content.append(text)
                main_content.append("")

            if main_content:
                info_parts.extend(main_content)

            if info_parts:
                structured_content = "\n".join(info_parts)
                structured_content += f"\n\n---\nSource: {url}"
                print(f"✅ Extracted structured content from {url}: {len(structured_content)} chars")
                return structured_content

            return None

        except Exception as e:
            print(f"❌ Structured content extraction failed for {url}: {e}")
            return None

    def _extract_with_gemini_safe(self, cleaned_html: str, url: str) -> Dict[str, Any]:
        """Thread-safe Gemini extraction that doesn't rely on Flask context."""
        try:
            import os

            # Get Gemini API key directly from environment
            gemini_api_key = os.getenv('GEMINI_API_KEY')
            if not gemini_api_key:
                raise Exception("Gemini API key not found in environment")

            # Import Gemini client
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage

            # General-purpose, comprehensive content extraction prompt
            # (full prompt body lives in prompts.yml as `web_extraction`).
            truncated_marker_2 = "...[Content truncated]" if len(cleaned_html) > 50000 else ""
            prompt = _prompt_svc().render(
                'web_extraction',
                html_content=(
                    f"URL: {url}\n\n"
                    f"{cleaned_html[:50000]}{truncated_marker_2}"
                ),
            )

            # Try multiple Gemini models in order of preference (Super Admin configured)
            try:
                from .model_resolver import get_active_models
                models_to_try = [m.model_name for m in get_active_models(provider='gemini')]
            except Exception:  # noqa: BLE001
                models_to_try = []

            for model_name in models_to_try:
                try:
                    print(f"🤖 Trying Gemini model: {model_name}")

                    extraction_client = ChatGoogleGenerativeAI(
                        model=model_name,
                        temperature=0.3,
                        max_output_tokens=4000,  # Reduced to avoid quota issues
                        google_api_key=gemini_api_key
                    )

                    response = extraction_client.invoke([HumanMessage(content=prompt)])

                    # Extract content from response
                    if hasattr(response, 'content'):
                        response_content = response.content
                    elif isinstance(response, dict):
                        response_content = response.get('content', '')
                    else:
                        response_content = str(response)

                    if response_content and len(response_content) > 100:
                        print(f"✅ Gemini extraction successful with {model_name}: {len(response_content)} chars")
                        return {
                            'success': True,
                            'content': response_content,
                            'model': model_name
                        }

                except Exception as model_error:
                    error_str = str(model_error)
                    print(f"⚠️ Model {model_name} failed: {error_str[:100]}")

                    # Check for quota exceeded error
                    if "quota" in error_str.lower() or "429" in error_str:
                        print(f"🚫 Quota exceeded for {model_name}, skipping remaining models")
                        break  # Stop trying other models if quota is exceeded

                    continue

            # All models failed
            raise Exception("All Gemini models failed")

        except Exception as e:
            print(f"❌ Gemini extraction failed: {e}")
            return {'success': False, 'error': str(e)}

    # ==================== OPENAI EXTRACTORS (ACTIVE) ====================
    def _build_openai_prompt(self, cleaned_html: str, url: str) -> str:
        """Builds a general-purpose extraction prompt for OpenAI.

        The full prompt body lives in prompts.yml as ``web_extraction`` so
        that all web-extraction prompts share a single source of truth.
        """
        truncated_marker_3 = "...[Content truncated]" if len(cleaned_html) > 50000 else ""
        return _prompt_svc().render(
            'web_extraction',
            html_content=(
                f"URL: {url}\n\n"
                f"{cleaned_html[:50000]}{truncated_marker_3}"
            ),
        )

    def _extract_with_openai(self, html_content: str, url: str, tenant_id: str = None, user_id: str = None) -> Optional[str]:
        """Extract content using OpenAI (non-threaded path)."""
        try:
            # Clean HTML similarly to Gemini path
            cleaned_html = self._preprocess_html(html_content)
            prompt = self._build_openai_prompt(cleaned_html, url)

            # Access OpenAI client from app service if present, else create lightweight client
            llm_service = getattr(current_app, 'llm_service', None)
            openai_client = getattr(llm_service, 'openai_client', None) if llm_service else None

            response_content = None
            if openai_client:
                # Use LangChain ChatOpenAI if available
                try:
                    from langchain_core.messages import HumanMessage
                    result = openai_client.invoke([HumanMessage(content=prompt)])
                    if hasattr(result, 'content'):
                        response_content = result.content
                    elif isinstance(result, dict):
                        response_content = result.get('content', '')
                except Exception as e:
                    current_app.logger.warning(f"⚠️ OpenAI via llm_service failed, falling back to direct API: {e}")

            if response_content is None:
                # Fallback to direct OpenAI API
                import os
                from openai import OpenAI
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise Exception("OpenAI API key not found in environment")
                client = OpenAI(api_key=api_key)
                chat = client.chat.completions.create(
                    model=self._resolve_extraction_model('openai'),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2000
                )
                response_content = chat.choices[0].message.content if chat.choices else None

            if response_content and len(response_content) > 50:
                return self._postprocess_content(response_content)
            return None
        except Exception as e:
            current_app.logger.error(f"❌ OpenAI extraction failed (non-threaded): {e}")
            raise

    def _extract_with_openai_safe(self, cleaned_html: str, url: str) -> Dict[str, Any]:
        """Thread-safe OpenAI extraction (no Flask context usage)."""
        try:
            import os
            from openai import OpenAI
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise Exception("OpenAI API key not found in environment")

            prompt = self._build_openai_prompt(cleaned_html, url)
            client = OpenAI(api_key=api_key)

            # Use a model from the Super Admin's AiModel table
            model = self._resolve_extraction_model('openai')
            chat = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            response_content = chat.choices[0].message.content if chat.choices else None

            if response_content and len(response_content) > 50:
                return {
                    'success': True,
                    'content': self._postprocess_content(response_content),
                    'model': model
                }

            return {'success': False, 'error': 'empty_response'}
        except Exception as e:
            print(f"❌ OpenAI extraction failed (threaded): {e}")
            return {'success': False, 'error': str(e)}

    def _combine_extracted_content(self, start_url: str, domain_name: str, model_name: str = None, model_provider: str = None) -> str:
        """Combine all extracted content and intelligently structure with the chatbot's AI model."""

        if not self.extracted_content:
            return f"# {domain_name}\n\nNo content could be extracted from this website."

        # Sort content by URL for consistent organization
        sorted_content = sorted(self.extracted_content, key=lambda x: x['url'])

        current_app.logger.info(f"🤖 Starting intelligent content structuring for {len(sorted_content)} pages...")

        # Build comprehensive content with simple formatting
        combined_parts = []
        combined_parts.append(f"# {domain_name} - Website Content")
        combined_parts.append(f"*Crawled from: {start_url}*")
        combined_parts.append(f"*Pages extracted: {len(sorted_content)}*")
        combined_parts.append("")

        # Add all page content with URLs
        for i, item in enumerate(sorted_content, 1):
            combined_parts.append(f"\n## Page {i}: {item['url']}")
            combined_parts.append(item['content'])
            combined_parts.append("")

        raw_content = "\n".join(combined_parts)

        # Use OpenAI to intelligently structure and chunk the content
        try:
            structured_content = self._intelligent_structure_with_openai(
                raw_content, domain_name, start_url,
                model_name=model_name, model_provider=model_provider
            )
            if structured_content:
                current_app.logger.info(f"✅ Successfully structured content with OpenAI: {len(structured_content)} chars")
                return structured_content
            else:
                current_app.logger.warning(f"⚠️ OpenAI structuring failed, using raw content")
                return raw_content
        except Exception as e:
            current_app.logger.error(f"❌ OpenAI structuring failed: {e}, using raw content")
            return raw_content

    def _intelligent_structure_with_openai(self, raw_content: str, domain_name: str, start_url: str, model_name: str = None, model_provider: str = None) -> Optional[str]:
        """Intelligently structure website content using the chatbot's configured AI model."""
        try:
            import tiktoken

            # Initialize tiktoken for token counting (cl100k_base is the OpenAI encoding
            # used by the gpt-4 / gpt-3.5 / text-embedding families)
            enc = tiktoken.get_encoding("cl100k_base")

            # Count tokens in raw content
            total_tokens = len(enc.encode(raw_content))
            current_app.logger.info(f"📊 Raw content tokens: {total_tokens}")

            # If content is small enough, process in one go
            if total_tokens < 50000:
                return self._structure_single_chunk(
                    raw_content, domain_name, start_url,
                    model_name=model_name, model_provider=model_provider
                )

            # Otherwise, split into chunks and process
            current_app.logger.info(f"📦 Content too large, splitting into chunks...")
            chunks = self._split_content_by_tokens(raw_content, enc, max_tokens=40000)
            current_app.logger.info(f"📦 Split into {len(chunks)} chunks")

            structured_chunks = []
            for i, chunk in enumerate(chunks, 1):
                current_app.logger.info(f"🤖 Processing chunk {i}/{len(chunks)}...")
                structured = self._structure_single_chunk(
                    chunk, domain_name, start_url,
                    chunk_num=i, total_chunks=len(chunks),
                    model_name=model_name, model_provider=model_provider
                )
                if structured:
                    structured_chunks.append(structured)

            # Combine structured chunks
            if structured_chunks:
                final_content = f"# {domain_name} - Structured Knowledge Base\n\n"
                final_content += f"*Source: {start_url}*\n\n"
                final_content += "\n\n---\n\n".join(structured_chunks)
                return final_content

            return None

        except Exception as e:
            current_app.logger.error(f"❌ Intelligent structuring failed: {e}")
            return None

    def _split_content_by_tokens(self, content: str, encoder, max_tokens: int = 40000) -> List[str]:
        """Split content into chunks based on token count."""
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_tokens = 0

        for line in lines:
            line_tokens = len(encoder.encode(line))

            if current_tokens + line_tokens > max_tokens and current_chunk:
                # Save current chunk and start new one
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_tokens = line_tokens
            else:
                current_chunk.append(line)
                current_tokens += line_tokens

        # Add last chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def _structure_single_chunk(self, content: str, domain_name: str, start_url: str, chunk_num: int = 1, total_chunks: int = 1, model_name: str = None, model_provider: str = None) -> Optional[str]:
        """Structure a single content chunk using the chatbot's configured AI model. Returns None on failure."""
        try:
            import os
            from langchain_core.messages import HumanMessage

            prompt = _prompt_svc().render(
                'web_structuring',
                domain_name=domain_name,
                start_url=start_url,
                chunk_label=(
                    f"Chunk: {chunk_num}/{total_chunks}" if total_chunks > 1 else ""
                ),
                content=content[:100000],
                truncated_marker=(
                    "\n...[Content truncated]" if len(content) > 100000 else ""
                ),
            )

            # Provider API type map (mirrors llm_service.py)
            PROVIDER_API_TYPE_MAP = {
                'openai': 'openai',
                'claude': 'anthropic',
                'gemini': 'gemini',
                'groq': 'groq',
                'qwen': 'openai',
                'deepseek': 'openai',
                'mistral': 'openai',
                'xai': 'openai',
                'together': 'openai',
                'perplexity': 'openai',
                'openrouter': 'openai',
            }

            # Resolve the AI model from DB to get API key and base_url
            client = None
            ai_model = None
            if model_name and model_provider:
                try:
                    from ..models.ai_model import AiModel
                    ai_model = AiModel.query.filter_by(
                        model_name=model_name, is_active=True
                    ).first()
                except Exception:
                    pass

            if ai_model:
                api_key = ai_model.get_api_key()
                base_url = ai_model.base_url
                api_type = PROVIDER_API_TYPE_MAP.get(ai_model.provider, 'openai')

                if api_key and api_type == 'openai':
                    from langchain_openai import ChatOpenAI
                    client = ChatOpenAI(
                        model=ai_model.model_name,
                        temperature=0.3,
                        max_tokens=8000,
                        api_key=api_key,
                        base_url=base_url,
                        timeout=60,
                    )
                elif api_key and api_type == 'gemini':
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    client = ChatGoogleGenerativeAI(
                        model=ai_model.model_name,
                        temperature=0.3,
                        max_output_tokens=8000,
                        google_api_key=api_key,
                    )
                elif api_key and api_type == 'groq':
                    from groq import Groq
                    groq_client = Groq(api_key=api_key)
                    response = groq_client.chat.completions.create(
                        model=ai_model.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=8000,
                        stream=False,
                    )
                    result_text = response.choices[0].message.content
                    if result_text and len(result_text) > 100:
                        current_app.logger.info(
                            f"✅ Structured chunk {chunk_num}/{total_chunks} "
                            f"with Groq ({ai_model.model_name}): "
                            f"{len(result_text)} chars"
                        )
                        return result_text
                    return None

            # Fallback: try Gemini if no client built
            if not client:
                api_key = os.getenv('GEMINI_API_KEY')
                if api_key:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    from .model_resolver import get_active_models
                    fallback_models = [m.model_name for m in get_active_models(provider='gemini')]
                    if not fallback_models:
                        fallback_models = ['gemini-2.0-flash']
                    model_name_fb = fallback_models[0]
                    client = ChatGoogleGenerativeAI(
                        model=model_name_fb,
                        temperature=0.3,
                        max_output_tokens=8000,
                        google_api_key=api_key
                    )
                else:
                    current_app.logger.warning("⚠️ No API key available for structuring")
                    return None

            response = client.invoke([HumanMessage(content=prompt)])
            if hasattr(response, 'content') and response.content and len(response.content) > 100:
                current_app.logger.info(
                    f"✅ Structured chunk {chunk_num}/{total_chunks}: "
                    f"{len(response.content)} chars"
                )
                return response.content

            return None

        except Exception as e:
            current_app.logger.error(f"❌ Chunk structuring failed: {e}")
            return None

    def _extract_page_title(self, content: str) -> Optional[str]:
        """Extract page title from content."""
        # Look for markdown heading
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            return title_match.group(1).strip()

        # Look for first line as title
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('*') and len(line) < 100:
                return line

        return None
