import requests
from bs4 import BeautifulSoup
import re
import socket
import ipaddress
from urllib.parse import urlparse
import uuid
from models import DocumentContent

MAX_RESPONSE_SIZE = 5 * 1024 * 1024 # 5 MB

def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        # Check against basic internal names
        if hostname.lower() in ('localhost', '127.0.0.1', '::1'):
            return False
            
        # Resolve IP to check for private networks (SSRF protection)
        try:
            ip = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                return False
        except socket.gaierror:
            return False
            
        return True
    except Exception:
        return False

def scrape_article(url: str) -> DocumentContent | None:
    """
    Downloads the HTML from a given URL, parses it, and extracts clean text from relevant tags.
    Returns a DocumentContent representation.
    """
    if not is_safe_url(url):
        print(f"URL validation failed (potential SSRF or unsupported scheme): {url}")
        return None
        
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    
    try:
        # Use stream=True to enforce response size limit
        response = requests.get(url, headers=headers, timeout=10, stream=True)
        response.raise_for_status()
        
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_RESPONSE_SIZE:
                response.close()
                print(f"Response too large for {url}")
                return None
                
        soup = BeautifulSoup(content, 'html.parser')
        
        title = soup.title.string if soup.title else url
        
        # Remove noisy elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
            
        # Extract meaningful tags sequentially to preserve document flow
        content_tags = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li'])
        
        docs = []
        current_heading = "Introduction"
        current_text = []
        
        for tag in content_tags:
            text = tag.get_text(strip=True)
            if not text:
                continue
                
            if tag.name in ['h1', 'h2', 'h3', 'h4']:
                # Save previous section if it has content
                if current_text:
                    section_text = "\n\n".join(current_text)
                    section_text = re.sub(r'\n{3,}', '\n\n', section_text)
                    if len(section_text) > 20:
                        docs.append(DocumentContent(
                            document_id=str(uuid.uuid4()),
                            document_name=title,
                            source_type='web',
                            text=section_text,
                            metadata={'source_url': url, 'section': current_heading}
                        ))
                current_heading = text
                current_text = [text] # include the heading in the text
            else:
                if len(text) > 20 or tag.name == 'li':
                    current_text.append(text)
                    
        # Add final section
        if current_text:
            section_text = "\n\n".join(current_text)
            section_text = re.sub(r'\n{3,}', '\n\n', section_text)
            if len(section_text) > 20:
                docs.append(DocumentContent(
                    document_id=str(uuid.uuid4()),
                    document_name=title,
                    source_type='web',
                    text=section_text,
                    metadata={'source_url': url, 'section': current_heading}
                ))
                
        # Fallback if no specific tags found
        if not docs:
            full_text = soup.get_text(separator='\n\n', strip=True)
            if full_text.strip():
                docs.append(DocumentContent(
                    document_id=str(uuid.uuid4()),
                    document_name=title,
                    source_type='web',
                    text=full_text,
                    metadata={'source_url': url}
                ))

        return docs
        
    except requests.exceptions.RequestException as e:
        print(f"Error scraping {url}: {e}")
        return []
