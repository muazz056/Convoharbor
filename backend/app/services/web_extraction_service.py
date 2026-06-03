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
from urllib.robotparser import RobotFileParser
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


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
            'Accept-Encoding': 'gzip, deflate, br',
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
    
    def crawl_full_website(self, start_url: str, description: str = "", tenant_id: str = None, user_id: str = None, progress_callback=None) -> Dict[str, Any]:
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
                    combined_content = self._combine_extracted_content(start_url, domain_name)
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
        
        # --- 1. Fetch page content with enhanced detection ---
        fetch_result = self._fetch_page_content_enhanced(url)
        if not fetch_result["success"]:
            return fetch_result
            
        page_content = fetch_result["content"]
        content_type = fetch_result.get("content_type", "html")
        
        # --- 2. Pre-process content based on type ---
        processed_content = self._preprocess_content_by_type(page_content, content_type, url)
        if not processed_content:
            return self._try_alternative_extraction(url, "Content preprocessing failed")
        
        # --- 3. Extract content with OpenAI (Gemini commented out for now) or fallback ---
        try:
            extracted_content = self._extract_with_openai(
                processed_content,
                url,
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            # --- 4. Validate Gemini's response ---
            if not extracted_content:
                current_app.logger.warning(f"⚠️ OpenAI returned empty content for {url}")
                return self._try_alternative_extraction(url, "OpenAI returned empty content")
            
            # Check for poor quality responses
            quality_issues = self._check_extraction_quality(extracted_content, url)
            if quality_issues:
                current_app.logger.warning(f"⚠️ Poor extraction quality for {url}: {quality_issues}")
                return self._try_alternative_extraction(url, f"Poor extraction quality: {quality_issues}")

            current_app.logger.info(f"✅ Successfully extracted {len(extracted_content)} characters from {url} using OpenAI")
            return {"success": True, "content": extracted_content}

        except Exception as e:
            current_app.logger.error(f"❌ OpenAI extraction failed for {url}: {e}")
            # Try fallback extraction when Gemini is not available
            if "API key" in str(e) or "not available" in str(e):
                return self._try_fallback_extraction(processed_content, url, str(e))
            else:
                return self._try_alternative_extraction(url, str(e))

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
                    except:
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
                    except:
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
            
        except:
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
        prompt = f"""You are a professional knowledge base extractor for a chatbot training system.

YOUR TASK: Extract ALL USEFUL INFORMATION from this webpage in a well-structured, comprehensive format.

🎯 WHAT TO EXTRACT (Be thorough and complete):

**1. PAGE TITLE & OVERVIEW**
- Main heading/title
- Brief description of what this page/site is about
- Purpose and key message

**2. MAIN CONTENT**
- ALL substantive text content organized by sections
- Headings and subheadings preserved
- Complete paragraphs with full information
- Lists, tables, and structured data

**3. CONTACT & LOCATION DETAILS** (if present)
- Company/organization name
- Physical addresses with full details
- Phone numbers, email addresses
- Website URLs
- Operating hours or availability
- Multiple locations listed separately

**4. PRODUCTS, SERVICES, OR OFFERINGS** (if applicable)
- Names and descriptions
- Prices with currency
- Features and specifications
- Categories and variants
- Availability information

**5. KEY FACTS & DATA**
- Dates, numbers, statistics
- Technical specifications
- Certifications, awards, credentials
- Policies, terms, conditions
- Requirements or prerequisites

**6. INSTRUCTIONS & PROCEDURES** (if present)
- Step-by-step guides
- How-to information
- Setup or configuration details
- Usage instructions

**7. ADDITIONAL INFORMATION**
- Special offers or announcements
- Updates or news
- FAQs
- Any other factual content

❌ SKIP THESE (Navigation/UI elements):
- Menu navigation links
- "Click here" / "Read more" buttons
- Social media buttons
- Cookie/privacy popups
- Footer boilerplate (copyright, legal)
- Newsletter signup prompts
- Login/signup forms

📋 OUTPUT FORMAT (Markdown with clear structure):

# [Page/Site Title]

## Overview
[What this page/site is about - 2-3 sentences]

## [Section 1 Name]
[Complete content from this section]
- Use bullet points for lists
- Preserve all details

## [Section 2 Name]
### [Subsection if needed]
[Complete content]

## Contact Information
[All contact details if present]

## [Additional Sections as Needed]
[Organize content logically]

CRITICAL RULES:
1. Extract EVERYTHING useful - be comprehensive, not brief
2. Preserve the hierarchical structure with ## and ### headings
3. Include ALL numbers, prices, dates, addresses, specifications
4. Organize content logically by topic
5. Use bullet points (-) for lists
6. Keep technical terms and specific names exactly as written
7. If a section has no content, skip it entirely
8. Focus on FACTS and INFORMATION, not marketing fluff
9. Do NOT add your own commentary - extract only what's on the page

URL: {url}

Content to analyze (extract ALL useful information):
{cleaned_html[:50000]}{"...[Content truncated]" if len(cleaned_html) > 50000 else ""}"""

        # Prepare the messages for the LLM
        messages = [{"role": "user", "content": prompt}]
        
        # Use Gemini directly for web extraction with higher token limits
        # We need more tokens for comprehensive content extraction
        try:
            import os
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            # Get API key from environment
            gemini_api_key = os.getenv('GEMINI_API_KEY')
            
            # Try multiple Gemini models in order of preference
            models_to_try = [
                "gemini-2.0-flash-exp",  # Latest experimental flash
                "gemini-1.5-flash-002",  # Stable 1.5 flash
                "gemini-1.5-pro-002",    # Stable 1.5 pro
                "gemini-1.5-flash",      # Base flash
                "gemini-pro"             # Fallback
            ]
            
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
        """Discover all URLs on a website from multiple sources."""
        discovered_urls = []
        unique_urls = set()
        
        current_app.logger.info(f"🔍 Discovering URLs for {base_domain}")
        
        # 1. Try to get sitemap.xml
        sitemap_urls = self._get_sitemap_urls(base_domain)
        for url in sitemap_urls:
            if url not in unique_urls:
                unique_urls.add(url)
                discovered_urls.append({
                    'url': url,
                    'depth': 0,
                    'source': 'sitemap',
                    'priority': 1
                })
        
        # 2. Crawl navigation and internal links from main pages
        main_pages = [
            start_url,
            f"{base_domain}/",
            f"{base_domain}/about",
            f"{base_domain}/contact",
            f"{base_domain}/products",
            f"{base_domain}/services",
            f"{base_domain}/solutions",
            f"{base_domain}/company",
            f"{base_domain}/info",
            f"{base_domain}/help",
            f"{base_domain}/support"
        ]
        
        for page_url in main_pages:
            if len(discovered_urls) >= self.max_pages:
                break
                
            page_links = self._extract_internal_links(page_url, base_domain)
            for link in page_links:
                if link not in unique_urls and len(discovered_urls) < self.max_pages:
                    unique_urls.add(link)
                    discovered_urls.append({
                        'url': link,
                        'depth': 1,
                        'source': 'navigation',
                        'priority': 2
                    })
        
        # 3. Sort by priority and limit - PRIORITY PAGES FIRST
        discovered_urls.sort(key=lambda x: (x['priority'], x['depth']))
        
        # Add high-priority pages that should be crawled first
        high_priority_pages = [
            start_url,  # Original URL - highest priority
            f"{base_domain}/",  # Homepage
            f"{base_domain}/about",
            f"{base_domain}/contact", 
            f"{base_domain}/products",
            f"{base_domain}/services",
            f"{base_domain}/solutions",
            f"{base_domain}/company"
        ]
        
        # Ensure high-priority pages are at the front
        prioritized_urls = []
        remaining_urls = []
        
        for url_info in discovered_urls:
            if url_info['url'] in high_priority_pages:
                url_info['priority'] = 0  # Highest priority
                prioritized_urls.append(url_info)
            else:
                remaining_urls.append(url_info)
        
        # Sort prioritized by original order, remaining by priority
        prioritized_urls.sort(key=lambda x: high_priority_pages.index(x['url']) if x['url'] in high_priority_pages else 999)
        remaining_urls.sort(key=lambda x: (x['priority'], x['depth']))
        
        # Combine: high-priority first, then others
        final_urls = prioritized_urls + remaining_urls
        
        # Filter out non-content pages and non-important pages for chatbot
        content_urls = []
        for url_info in final_urls:
            url = url_info['url']
            # Skip XML files, XSL files, and other non-content
            if not self._is_content_page(url):
                continue
            # Skip pages not important for chatbot (blogs, case studies, etc.)
            if not self._is_important_for_chatbot(url):
                current_app.logger.debug(f"⏭️ Skipping non-essential page: {url}")
                continue
            content_urls.append(url_info)
        
        # Set the actual total for progress tracking
        self.total_discovered_pages = len(content_urls)
        
        current_app.logger.info(f"🎯 Prioritized crawling: {len(prioritized_urls)} high-priority, {len(remaining_urls)} regular pages")
        current_app.logger.info(f"📊 Total content pages to crawl: {self.total_discovered_pages}")
        
        return content_urls
    
    def _get_sitemap_urls(self, base_domain: str) -> List[str]:
        """Extract URLs from sitemap.xml."""
        sitemap_urls = []
        
        sitemap_locations = [
            f"{base_domain}/sitemap.xml",
            f"{base_domain}/sitemap_index.xml",
            f"{base_domain}/sitemaps.xml",
            f"{base_domain}/robots.txt"  # Check robots.txt for sitemap location
        ]
        
        for sitemap_url in sitemap_locations:
            try:
                current_app.logger.info(f"🗺️ Checking sitemap: {sitemap_url}")
                response = self.session.get(sitemap_url, timeout=10)
                
                if response.status_code == 200:
                    content = response.text
                    
                    # Parse XML sitemap
                    if 'sitemap.xml' in sitemap_url or 'sitemaps.xml' in sitemap_url:
                        urls = self._parse_sitemap_xml(content)
                        sitemap_urls.extend(urls)
                        current_app.logger.info(f"✅ Found {len(urls)} URLs in sitemap")
                        break
                    
                    # Parse robots.txt for sitemap references
                    elif 'robots.txt' in sitemap_url:
                        sitemap_refs = re.findall(r'Sitemap:\s*(.+)', content, re.IGNORECASE)
                        for ref in sitemap_refs:
                            ref_urls = self._get_sitemap_urls(ref.strip())
                            sitemap_urls.extend(ref_urls)
                            
            except Exception as e:
                current_app.logger.debug(f"Failed to fetch sitemap {sitemap_url}: {e}")
                continue
        
        return list(set(sitemap_urls))  # Remove duplicates
    
    def _parse_sitemap_xml(self, xml_content: str) -> List[str]:
        """Parse XML sitemap content to extract URLs."""
        urls = []
        
        try:
            # Simple regex parsing for URLs (more reliable than XML parsing for malformed XML)
            url_patterns = [
                r'<loc>(.*?)</loc>',
                r'<url>(.*?)</url>',
                r'href=["\']([^"\']*)["\']'
            ]
            
            for pattern in url_patterns:
                matches = re.findall(pattern, xml_content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    clean_url = match.strip()
                    if clean_url.startswith('http'):
                        urls.append(clean_url)
                        
        except Exception as e:
            current_app.logger.debug(f"Failed to parse sitemap XML: {e}")
        
        return urls
    
    def _extract_internal_links(self, page_url: str, base_domain: str) -> List[str]:
        """Extract internal links from a webpage."""
        internal_links = []
        
        try:
            current_app.logger.debug(f"🔗 Extracting links from: {page_url}")
            response = self.session.get(page_url, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all links
                links = soup.find_all('a', href=True)
                
                for link in links:
                    href = link['href']
                    
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(page_url, href)
                    parsed_url = urlparse(absolute_url)
                    
                    # Only include internal links (same domain)
                    if parsed_url.netloc in base_domain or base_domain in parsed_url.netloc:
                        # Clean URL (remove fragments, normalize)
                        clean_url = urlunparse((
                            parsed_url.scheme,
                            parsed_url.netloc,
                            parsed_url.path,
                            parsed_url.params,
                            parsed_url.query,
                            ''  # Remove fragment
                        ))
                        
                        # Filter out unwanted URLs
                        if self._is_valid_crawl_url(clean_url):
                            internal_links.append(clean_url)
                            
        except Exception as e:
            current_app.logger.debug(f"Failed to extract links from {page_url}: {e}")
        
        return list(set(internal_links))  # Remove duplicates
    
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
            r'\.atom$', # Atom feeds
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
        """Filter to only extract pages useful for a chatbot knowledge base."""
        url_lower = url.lower()
        
        # Skip these patterns - not useful for chatbot
        skip_patterns = [
            r'/blog/',          # Blog posts
            r'/category/',      # Category archives
            r'/tag/',           # Tag archives
            r'/author/',        # Author pages
            r'/news/',          # News articles
            r'/press/',         # Press releases
            r'/media/',         # Media/press
            r'/case-studies?/', # Case studies (usually marketing)
            r'/portfolio/',     # Portfolio items
            r'/careers?/',      # Job listings
            r'/jobs?/',         # Job listings
            r'/privacy-policy', # Legal (not chatbot relevant)
            r'/terms',          # Terms of service
            r'/cookie',         # Cookie policy
            r'/legal/',         # Legal pages
            r'-\d{4}-\d{2}-\d{2}',  # Date-based URLs (blog posts)
            r'/\d{4}/',         # Year-based archives
            r'/page/\d+/',      # Pagination
            r'/search',         # Search results
            r'/login',          # Login pages
            r'/register',       # Registration
            r'/checkout',       # E-commerce checkout
            r'/cart',           # Shopping cart
            r'/thank-you',      # Thank you pages
        ]
        
        for pattern in skip_patterns:
            if re.search(pattern, url_lower):
                return False
        
        # Keep these - important for chatbot
        # Homepage, about, services, products, pricing, features, solutions, contact, support, help, faq
        important_keywords = [
            'about', 'service', 'product', 'pricing', 'price', 'feature', 
            'solution', 'contact', 'support', 'help', 'faq', 'how', 'what',
            'hire', 'developer', 'tech', 'technology', 'industry',
            'infrastructure', 'development', 'software', 'app', 'web',
            'mobile', 'cloud', 'ai', 'ml', 'blockchain', 'iot'
        ]
        
        # Homepage is always important
        parsed = urlparse(url_lower)
        if parsed.path in ['', '/', '/index.html', '/home', '/index']:
            return True
        
        # Check if URL contains important keywords
        has_important = any(keyword in url_lower for keyword in important_keywords)
        
        # If no important keywords and path is deep (3+ levels), skip it
        path_depth = len([p for p in parsed.path.split('/') if p])
        if not has_important and path_depth > 2:
            return False
        
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
                                                'pages_failed': len(self.failed_urls)
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
                
                except Exception as timeout_error:
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
        """Crawl a single page and extract its content."""
        try:
            # Rotate user agent for each request
            self._rotate_user_agent()
            
            # CRITICAL FIX: Use direct HTTP fetching to avoid Flask context issues
            page_content = self._fetch_page_content_direct(url)
            if not page_content:
                return None
                
            content_type = "html"
            
            # Process content based on type
            if content_type == "html":
                processed_content = self._preprocess_html_content_safe(page_content, url)
                
                if processed_content:
                    # Simple text extraction - no AI during crawl for speed
                    # AI processing will happen AFTER all pages are crawled
                    return {
                        'url': url,
                        'content': processed_content,
                        'depth': depth,
                        'extraction_method': 'html_text_parser',
                        'timestamp': datetime.now().isoformat()
                    }
            
        except Exception as e:
            # Use print instead of current_app.logger to avoid context issues
            print(f"❌ Single page crawl failed for {url}: {e}")
        
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
                except:
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
            prompt = f"""You are a professional knowledge base extractor for a chatbot training system.

YOUR TASK: Extract ALL USEFUL INFORMATION from this webpage in a well-structured, comprehensive format.

🎯 WHAT TO EXTRACT (Be thorough and complete):

**1. PAGE TITLE & OVERVIEW**
- Main heading/title
- Brief description of what this page/site is about
- Purpose and key message

**2. MAIN CONTENT**
- ALL substantive text content organized by sections
- Headings and subheadings preserved
- Complete paragraphs with full information
- Lists, tables, and structured data

**3. CONTACT & LOCATION DETAILS** (if present)
- Company/organization name
- Physical addresses with full details
- Phone numbers, email addresses
- Website URLs
- Operating hours or availability
- Multiple locations listed separately

**4. PRODUCTS, SERVICES, OR OFFERINGS** (if applicable)
- Names and descriptions
- Prices with currency
- Features and specifications
- Categories and variants
- Availability information

**5. KEY FACTS & DATA**
- Dates, numbers, statistics
- Technical specifications
- Certifications, awards, credentials
- Policies, terms, conditions
- Requirements or prerequisites

**6. INSTRUCTIONS & PROCEDURES** (if present)
- Step-by-step guides
- How-to information
- Setup or configuration details
- Usage instructions

**7. ADDITIONAL INFORMATION**
- Special offers or announcements
- Updates or news
- FAQs
- Any other factual content

❌ SKIP THESE (Navigation/UI elements):
- Menu navigation links
- "Click here" / "Read more" buttons
- Social media buttons
- Cookie/privacy popups
- Footer boilerplate (copyright, legal)
- Newsletter signup prompts
- Login/signup forms

📋 OUTPUT FORMAT (Markdown with clear structure):

# [Page/Site Title]

## Overview
[What this page/site is about - 2-3 sentences]

## [Section 1 Name]
[Complete content from this section]
- Use bullet points for lists
- Preserve all details

## [Section 2 Name]
### [Subsection if needed]
[Complete content]

## Contact Information
[All contact details if present]

## [Additional Sections as Needed]
[Organize content logically]

CRITICAL RULES:
1. Extract EVERYTHING useful - be comprehensive, not brief
2. Preserve the hierarchical structure with ## and ### headings
3. Include ALL numbers, prices, dates, addresses, specifications
4. Organize content logically by topic
5. Use bullet points (-) for lists
6. Keep technical terms and specific names exactly as written
7. If a section has no content, skip it entirely
8. Focus on FACTS and INFORMATION, not marketing fluff
9. Do NOT add your own commentary - extract only what's on the page

URL: {url}

Content to analyze (extract ALL useful information):
{cleaned_html[:50000]}{"...[Content truncated]" if len(cleaned_html) > 50000 else ""}"""

            # Try multiple Gemini models in order of preference
            models_to_try = [
                "gemini-2.0-flash-exp",
                "gemini-1.5-flash-002", 
                "gemini-1.5-pro-002",
                "gemini-1.5-flash",
                "gemini-pro"
            ]

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
        """Builds a general-purpose extraction prompt for OpenAI."""
        prompt = f"""You are a professional knowledge base extractor for a chatbot training system.

Extract ALL useful information from this webpage in a well-structured Markdown format.

Output structure:

# [Page/Site Title]

## Overview
[2-3 sentences summary]

## [Sections]
- Preserve headings and subheadings using ## and ###
- Include complete paragraphs and bullet lists
- Keep all numbers, prices, dates, addresses, specs as written

## Contact Information
- Include any addresses, phones, emails, hours if present

Rules:
- Extract facts only; skip navigation/UI elements, cookie banners, and boilerplate
- No added commentary; only extract what's in the content

URL: {url}

Content to analyze:
{cleaned_html[:50000]}{"...[Content truncated]" if len(cleaned_html) > 50000 else ""}
"""
        return prompt

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
                    model=os.getenv('OPENAI_WEB_EXTRACTION_MODEL', 'gpt-4o-mini'),
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

            # Use a fast, cost-effective model for extraction
            model = os.getenv('OPENAI_WEB_EXTRACTION_MODEL', 'gpt-4o-mini')
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
    
    def _combine_extracted_content(self, start_url: str, domain_name: str) -> str:
        """Combine all extracted content and intelligently structure with OpenAI."""
        
        if not self.extracted_content:
            return f"# {domain_name}\n\nNo content could be extracted from this website."
        
        # Sort content by URL for consistent organization
        sorted_content = sorted(self.extracted_content, key=lambda x: x['url'])
        
        current_app.logger.info(f"🤖 Starting intelligent content structuring with OpenAI for {len(sorted_content)} pages...")
        
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
            structured_content = self._intelligent_structure_with_openai(raw_content, domain_name, start_url)
            if structured_content:
                current_app.logger.info(f"✅ Successfully structured content with OpenAI: {len(structured_content)} chars")
                return structured_content
            else:
                current_app.logger.warning(f"⚠️ OpenAI structuring failed, using raw content")
                return raw_content
        except Exception as e:
            current_app.logger.error(f"❌ OpenAI structuring failed: {e}, using raw content")
            return raw_content
    
    def _intelligent_structure_with_openai(self, raw_content: str, domain_name: str, start_url: str) -> Optional[str]:
        """Use OpenAI to intelligently structure and organize website content with tiktoken-based chunking."""
        try:
            import tiktoken
            import os
            from openai import OpenAI
            
            # Initialize tiktoken for token counting
            enc = tiktoken.encoding_for_model("gpt-4o-mini")
            
            # Count tokens in raw content
            total_tokens = len(enc.encode(raw_content))
            current_app.logger.info(f"📊 Raw content tokens: {total_tokens}")
            
            # If content is small enough, process in one go
            if total_tokens < 50000:
                return self._structure_single_chunk(raw_content, domain_name, start_url)
            
            # Otherwise, split into chunks and process
            current_app.logger.info(f"📦 Content too large, splitting into chunks...")
            chunks = self._split_content_by_tokens(raw_content, enc, max_tokens=40000)
            current_app.logger.info(f"📦 Split into {len(chunks)} chunks")
            
            structured_chunks = []
            for i, chunk in enumerate(chunks, 1):
                current_app.logger.info(f"🤖 Processing chunk {i}/{len(chunks)}...")
                structured = self._structure_single_chunk(chunk, domain_name, start_url, chunk_num=i, total_chunks=len(chunks))
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
    
    def _structure_single_chunk(self, content: str, domain_name: str, start_url: str, chunk_num: int = 1, total_chunks: int = 1) -> Optional[str]:
        """Use OpenAI to structure a single content chunk."""
        try:
            import os
            from openai import OpenAI
            
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise Exception("OpenAI API key not found")
            
            client = OpenAI(api_key=api_key)
            
            prompt = f"""You are a knowledge base organizer for a chatbot. Your task is to structure and organize website content into a clean, well-formatted knowledge base.

Website: {domain_name}
Source: {start_url}
{"Chunk: " + str(chunk_num) + "/" + str(total_chunks) if total_chunks > 1 else ""}

TASK: Organize the following website content into a structured, hierarchical format optimized for chatbot knowledge retrieval.

REQUIREMENTS:
1. Create clear sections with ## headings for main topics
2. Use ### for subsections
3. Preserve ALL important information (services, products, features, pricing, contact info)
4. Remove duplicate information
5. Organize by topic/theme, not by original page URL
6. Keep factual information intact - no commentary
7. Use bullet points for lists
8. Include numbers, prices, specifications exactly as provided

OUTPUT FORMAT:
## [Topic Name]
[Content organized by topic]

### [Subtopic]
- Key point 1
- Key point 2

Example sections you might create:
- Company Overview
- Services & Products
- Pricing & Plans
- Technical Specifications
- Contact Information & Locations
- Key Features
- How It Works

Raw website content to structure:
{content[:100000]}{"...[Content truncated]" if len(content) > 100000 else ""}
"""

            model = os.getenv('OPENAI_WEB_STRUCTURING_MODEL', 'gpt-4o-mini')
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=8000
            )
            
            if response.choices:
                return response.choices[0].message.content
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
