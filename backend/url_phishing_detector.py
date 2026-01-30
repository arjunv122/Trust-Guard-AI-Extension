"""
TrustGuard AI - URL Phishing Detector
Uses Random Forest classifier with URL-based features for phishing detection
"""

import re
import math
import logging
import pickle
import os
from urllib.parse import urlparse, parse_qs
from collections import Counter
import numpy as np

logger = logging.getLogger(__name__)

# Suspicious TLDs commonly used in phishing
SUSPICIOUS_TLDS = [
    '.tk', '.ml', '.ga', '.cf', '.gq', '.xyz', '.top', '.work', '.click',
    '.link', '.info', '.online', '.site', '.website', '.space', '.pw',
    '.cc', '.buzz', '.icu', '.cam', '.monster', '.rest', '.beauty',
    '.win', '.loan', '.download', '.stream', '.racing', '.review', '.country',
    '.science', '.party', '.gdn', '.men', '.faith', '.date', '.accountant',
    '.cricket', '.trade', '.bid', '.webcam', '.kim', '.rocks', '.tokyo',
    '.life', '.world', '.today', '.email', '.solutions', '.digital', '.network',
    '.live', '.studio', '.fun', '.uno', '.mobi', '.pro', '.fit', '.vip'
]

# Legitimate/trusted TLDs
TRUSTED_TLDS = ['.gov', '.edu', '.mil', '.ac.uk', '.gov.uk']

# Suspicious keywords in URLs - expanded list
PHISHING_KEYWORDS = [
    'login', 'signin', 'sign-in', 'log-in', 'account', 'verify', 'verification',
    'secure', 'security', 'update', 'confirm', 'password', 'credential',
    'banking', 'paypal', 'apple', 'microsoft', 'google', 'amazon', 'netflix',
    'facebook', 'instagram', 'whatsapp', 'telegram', 'bank', 'wallet',
    'suspended', 'locked', 'unusual', 'activity', 'urgent', 'immediately',
    'expire', 'expired', 'limited', 'restore', 'recover', 'authenticate',
    'ssn', 'social-security', 'tax', 'refund', 'prize', 'winner', 'lottery',
    'free', 'gift', 'offer', 'bonus', 'reward', 'promo', 'deal',
    # Additional keywords
    'alert', 'warning', 'action', 'required', 'validate', 'submit', 'click',
    'upgrade', 'billing', 'invoice', 'payment', 'card', 'credit', 'debit',
    'wire', 'transfer', 'authorize', 'unauthorized', 'compromised', 'breach',
    'reset', 'reactivate', 'unlock', 'unblock', 'access', 'denied', 'blocked',
    'customer', 'service', 'support', 'helpdesk', 'admin', 'webmail', 'portal',
    'document', 'shared', 'attachment', 'download', 'view', 'open', 'pdf',
    'package', 'delivery', 'shipment', 'tracking', 'ups', 'fedex', 'dhl',
    'irs', 'hmrc', 'cra', 'ato', 'gov', 'official', 'notice', 'notification'
]

# URL shortening services
URL_SHORTENERS = [
    'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly', 'is.gd', 'buff.ly',
    'adf.ly', 'bit.do', 'mcaf.ee', 'su.pr', 'go2l.ink', 'short.to', 'cutt.ly',
    'rb.gy', 'shorturl.at', 'tiny.cc', 'bc.vc', 'trib.al', 'v.gd'
]

# Known legitimate domains (whitelist)
TRUSTED_DOMAINS = [
    'google.com', 'youtube.com', 'facebook.com', 'twitter.com', 'instagram.com',
    'linkedin.com', 'microsoft.com', 'apple.com', 'amazon.com', 'netflix.com',
    'github.com', 'stackoverflow.com', 'wikipedia.org', 'reddit.com', 'bbc.com',
    'nytimes.com', 'cnn.com', 'reuters.com', 'paypal.com', 'ebay.com',
    'dropbox.com', 'slack.com', 'zoom.us', 'spotify.com', 'twitch.tv'
]


class URLPhishingDetector:
    """
    Phishing URL detector using feature extraction and Random Forest classification
    """
    
    def __init__(self):
        self.name = "TrustGuard URL Phishing Detector"
        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), 'phishing_model.pkl')
        
    def extract_features(self, url: str) -> dict:
        """
        Extract features from URL for phishing detection
        Returns a dictionary of features
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            query = parsed.query.lower()
            full_url = url.lower()
            
            # Remove www. prefix for analysis
            if domain.startswith('www.'):
                domain = domain[4:]
            
            features = {}
            
            # 1. URL Length features
            features['url_length'] = len(url)
            features['domain_length'] = len(domain)
            features['path_length'] = len(path)
            features['query_length'] = len(query)
            
            # 2. Character count features
            features['num_dots'] = url.count('.')
            features['num_hyphens'] = url.count('-')
            features['num_underscores'] = url.count('_')
            features['num_slashes'] = url.count('/')
            features['num_question_marks'] = url.count('?')
            features['num_equals'] = url.count('=')
            features['num_ampersands'] = url.count('&')
            features['num_at_symbols'] = url.count('@')
            features['num_digits'] = sum(c.isdigit() for c in url)
            features['num_special_chars'] = sum(not c.isalnum() and c not in './-_' for c in url)
            
            # 3. Domain-based features
            features['has_ip_address'] = 1 if re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', domain) else 0
            features['has_port'] = 1 if ':' in domain and domain.split(':')[-1].isdigit() else 0
            features['num_subdomains'] = domain.count('.') - 1 if '.' in domain else 0
            
            # 4. Protocol features
            features['is_https'] = 1 if parsed.scheme == 'https' else 0
            features['is_http'] = 1 if parsed.scheme == 'http' else 0
            
            # 5. TLD features
            tld = '.' + domain.split('.')[-1] if '.' in domain else ''
            features['suspicious_tld'] = 1 if any(domain.endswith(t) for t in SUSPICIOUS_TLDS) else 0
            features['trusted_tld'] = 1 if any(domain.endswith(t) for t in TRUSTED_TLDS) else 0
            
            # 6. Phishing keyword features
            keyword_count = sum(1 for kw in PHISHING_KEYWORDS if kw in full_url)
            features['phishing_keyword_count'] = keyword_count
            features['has_phishing_keywords'] = 1 if keyword_count > 0 else 0
            
            # 7. URL shortener detection
            features['is_shortened'] = 1 if any(shortener in domain for shortener in URL_SHORTENERS) else 0
            
            # 8. Trusted domain check
            features['is_trusted_domain'] = 1 if any(trusted in domain for trusted in TRUSTED_DOMAINS) else 0
            
            # 9. Entropy (randomness) of URL
            features['url_entropy'] = self._calculate_entropy(url)
            features['domain_entropy'] = self._calculate_entropy(domain)
            
            # 10. Suspicious patterns
            features['has_double_slash_redirect'] = 1 if '//' in path else 0
            features['has_hex_encoding'] = 1 if '%' in url else 0
            features['has_punycode'] = 1 if 'xn--' in domain else 0
            features['has_brand_in_subdomain'] = 1 if self._has_brand_in_subdomain(domain) else 0
            
            # 11. Path-based features
            features['path_depth'] = path.count('/') - 1 if path else 0
            features['has_suspicious_extension'] = 1 if re.search(r'\.(php|asp|aspx|cgi|exe|html|htm)(\?|$)', path) else 0
            
            # 12. Query parameter features
            query_params = parse_qs(query)
            features['num_query_params'] = len(query_params)
            features['has_email_in_url'] = 1 if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', url) else 0
            
            # 13. Domain age simulation (based on heuristics)
            features['is_new_looking_domain'] = 1 if len(domain) > 20 or features['num_digits'] > 5 else 0
            
            # 14. Mixed character detection
            features['has_mixed_chars'] = 1 if re.search(r'[a-z].*\d.*[a-z]|\d.*[a-z].*\d', domain) else 0
            
            # 15. @ Symbol presence (important for URL confusion attacks)
            features['has_at_symbols'] = 1 if '@' in url else 0
            
            # 16. Typosquatting detection patterns
            features['has_repeated_chars'] = 1 if re.search(r'(.)\1{2,}', domain) else 0
            
            # 17. Suspicious domain patterns (brand + random suffix)
            features['suspicious_domain_pattern'] = 1 if re.search(
                r'(paypal|google|microsoft|apple|amazon|facebook|netflix|bank)[0-9a-z]{3,}',
                domain
            ) else 0
            
            # 18. Long random subdomain
            if len(parts := domain.split('.')) > 2:
                subdomain = parts[0]
                features['long_subdomain'] = 1 if len(subdomain) > 20 else 0
            else:
                features['long_subdomain'] = 0
            
            return features
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return {}
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of a string"""
        if not text:
            return 0.0
        
        counter = Counter(text)
        length = len(text)
        entropy = 0.0
        
        for count in counter.values():
            probability = count / length
            entropy -= probability * math.log2(probability)
        
        return round(entropy, 4)
    
    def _has_brand_in_subdomain(self, domain: str) -> bool:
        """Check if a known brand name appears in subdomain (phishing indicator)"""
        brands = [
            'paypal', 'apple', 'microsoft', 'google', 'amazon', 'facebook', 
            'netflix', 'bank', 'secure', 'login', 'account', 'wellsfargo',
            'chase', 'citi', 'citibank', 'hsbc', 'barclays', 'santander',
            'linkedin', 'twitter', 'instagram', 'whatsapp', 'telegram',
            'coinbase', 'binance', 'crypto', 'wallet', 'blockchain',
            'dropbox', 'icloud', 'onedrive', 'outlook', 'office365',
            'dhl', 'fedex', 'ups', 'usps', 'royal-mail', 'hermes',
            'ebay', 'alibaba', 'aliexpress', 'wish', 'etsy',
            'steam', 'playstation', 'xbox', 'nintendo', 'epic',
            'spotify', 'discord', 'twitch', 'zoom', 'webex',
            'verify', 'confirm', 'update', 'security', 'authenticate'
        ]
        parts = domain.split('.')
        
        if len(parts) > 2:
            subdomain = '.'.join(parts[:-2])
            return any(brand in subdomain for brand in brands)
        
        # Also check if brand appears in domain with suspicious suffixes
        main_domain = parts[-2] if len(parts) >= 2 else ''
        suspicious_patterns = [
            r'(paypal|google|microsoft|apple|amazon|facebook|netflix|bank)\d+',
            r'(secure|login|verify|update|account)(paypal|google|microsoft|apple)',
            r'(paypal|google|microsoft|apple)(secure|login|verify|update)',
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, main_domain):
                return True
        
        return False
    
    def calculate_phishing_score(self, features: dict) -> dict:
        """
        Calculate phishing probability using feature-based rules
        Returns score and detailed breakdown
        """
        score = 100  # Start with safe score
        risk_factors = []
        safe_factors = []
        high_risk_count = 0
        
        # ======== HIGH RISK INDICATORS (MAJOR RED FLAGS) ========
        if features.get('has_ip_address'):
            score -= 50
            high_risk_count += 1
            risk_factors.append({
                'factor': 'IP Address in URL',
                'severity': 'high',
                'description': 'The URL uses an IP address instead of a domain name - this is a common phishing technique.',
                'simple': 'Real websites use names like "google.com", not number addresses like "192.168.1.1".'
            })
        
        if features.get('has_at_symbols') or features.get('num_at_symbols', 0) > 0:
            score -= 45
            high_risk_count += 1
            risk_factors.append({
                'factor': '@ Symbol in URL',
                'severity': 'high',
                'description': 'The @ symbol can be used to hide the real destination of a link.',
                'simple': 'Scammers use @ to trick you - the real website is hidden after the @ symbol.'
            })
        
        if features.get('has_double_slash_redirect'):
            score -= 40
            high_risk_count += 1
            risk_factors.append({
                'factor': 'Suspicious Redirect Pattern',
                'severity': 'high',
                'description': 'Double slashes in the path can indicate a redirect to a malicious site.',
                'simple': 'This link might redirect you to a different, dangerous website.'
            })
        
        if features.get('has_brand_in_subdomain'):
            score -= 45
            high_risk_count += 1
            risk_factors.append({
                'factor': 'Brand Name in Subdomain',
                'severity': 'high',
                'description': 'A brand name appears in the subdomain, which is a common phishing tactic.',
                'simple': 'Fake sites put brand names like "paypal" before the real domain to fool you.'
            })
        
        if features.get('has_punycode'):
            score -= 40
            high_risk_count += 1
            risk_factors.append({
                'factor': 'Punycode/IDN Homograph',
                'severity': 'high',
                'description': 'This URL uses punycode which can make fake domains look like real ones.',
                'simple': 'The link uses special characters that look like normal letters but aren\'t.'
            })
        
        # ======== MEDIUM RISK INDICATORS ========
        if features.get('suspicious_tld'):
            score -= 30
            risk_factors.append({
                'factor': 'Suspicious Domain Extension',
                'severity': 'medium',
                'description': 'The domain uses a TLD commonly associated with spam and phishing.',
                'simple': 'Websites ending in .xyz, .tk, .click etc. are often used by scammers.'
            })
        
        if features.get('is_shortened'):
            score -= 25
            risk_factors.append({
                'factor': 'URL Shortener Used',
                'severity': 'medium',
                'description': 'URL shorteners hide the real destination and are often used in phishing.',
                'simple': 'Short links like bit.ly hide where you\'re really going - be careful!'
            })
        
        # Phishing keywords - more aggressive scoring
        keyword_count = features.get('phishing_keyword_count', 0)
        if keyword_count >= 3:
            score -= 35
            risk_factors.append({
                'factor': 'Multiple Phishing Keywords',
                'severity': 'high',
                'description': f"Found {keyword_count} suspicious keywords often used in phishing attacks.",
                'simple': 'Words like "verify", "suspended", "urgent" are often used in scam links.'
            })
        elif keyword_count >= 2:
            score -= 25
            risk_factors.append({
                'factor': 'Phishing Keywords Detected',
                'severity': 'medium',
                'description': f"Found {keyword_count} suspicious keywords commonly used in phishing.",
                'simple': 'Words like "verify", "account", "login" are commonly used by scammers.'
            })
        elif features.get('has_phishing_keywords'):
            score -= 15
            risk_factors.append({
                'factor': 'Phishing Keyword Detected',
                'severity': 'medium',
                'description': 'Contains keywords commonly used in phishing attempts.',
                'simple': 'This link contains words that scammers often use.'
            })
        
        if features.get('url_length', 0) > 75:
            length = features.get('url_length', 0)
            if length > 150:
                score -= 25
            elif length > 100:
                score -= 18
            else:
                score -= 12
            risk_factors.append({
                'factor': 'Unusually Long URL',
                'severity': 'medium',
                'description': 'Very long URLs can be used to hide malicious destinations.',
                'simple': 'Extremely long website addresses are often suspicious.'
            })
        
        if features.get('num_subdomains', 0) > 2:
            subdomain_count = features.get('num_subdomains', 0)
            if subdomain_count > 4:
                score -= 25
            elif subdomain_count > 3:
                score -= 18
            else:
                score -= 12
            risk_factors.append({
                'factor': 'Excessive Subdomains',
                'severity': 'medium',
                'description': 'Too many subdomains can indicate an attempt to mimic legitimate sites.',
                'simple': 'Too many dots in the address (like a.b.c.d.example.com) is suspicious.'
            })
        
        if features.get('url_entropy', 0) > 4.0:
            entropy = features.get('url_entropy', 0)
            if entropy > 5.0:
                score -= 22
            else:
                score -= 15
            risk_factors.append({
                'factor': 'High URL Randomness',
                'severity': 'medium',
                'description': 'The URL contains highly random characters, which is unusual for legitimate sites.',
                'simple': 'The link looks like random gibberish - real websites have readable names.'
            })
        
        if features.get('has_hex_encoding'):
            score -= 18
            risk_factors.append({
                'factor': 'Obfuscated URL',
                'severity': 'medium',
                'description': 'URL contains encoded characters that may hide the true destination.',
                'simple': 'The link uses codes to hide what it really says.'
            })
        
        # Special character overload
        if features.get('num_special_chars', 0) > 10:
            score -= 15
            risk_factors.append({
                'factor': 'Excessive Special Characters',
                'severity': 'medium',
                'description': 'The URL contains too many special characters.',
                'simple': 'Too many symbols in the link is suspicious.'
            })
        
        # ======== LOW RISK INDICATORS ========
        if not features.get('is_https'):
            score -= 15
            risk_factors.append({
                'factor': 'No HTTPS',
                'severity': 'low',
                'description': 'The site does not use HTTPS encryption.',
                'simple': 'This website doesn\'t have the secure padlock - your data might not be protected.'
            })
        
        if features.get('num_hyphens', 0) > 2:
            hyphen_count = features.get('num_hyphens', 0)
            if hyphen_count > 4:
                score -= 18
            else:
                score -= 10
            risk_factors.append({
                'factor': 'Multiple Hyphens',
                'severity': 'medium' if hyphen_count > 4 else 'low',
                'description': 'Excessive hyphens in domain names are common in phishing URLs.',
                'simple': 'Too many dashes in the name (like pay-pal-secure-login.com) is suspicious.'
            })
        
        if features.get('is_new_looking_domain'):
            score -= 15
            risk_factors.append({
                'factor': 'Suspicious Domain Pattern',
                'severity': 'medium',
                'description': 'Domain has characteristics of newly created phishing domains.',
                'simple': 'This domain looks like it was just created - scammers make new sites often.'
            })
        
        # Additional new feature scoring
        if features.get('suspicious_domain_pattern'):
            score -= 25
            risk_factors.append({
                'factor': 'Brand Impersonation Pattern',
                'severity': 'high',
                'description': 'The domain appears to impersonate a well-known brand.',
                'simple': 'This looks like a fake version of a famous website!'
            })
        
        if features.get('long_subdomain'):
            score -= 15
            risk_factors.append({
                'factor': 'Suspicious Long Subdomain',
                'severity': 'medium',
                'description': 'Unusually long subdomains are often used to hide the real destination.',
                'simple': 'The part before the main website name is suspiciously long.'
            })
        
        if features.get('has_repeated_chars'):
            score -= 10
            risk_factors.append({
                'factor': 'Repeated Characters',
                'severity': 'low',
                'description': 'Repeated characters may indicate a typosquatting attempt.',
                'simple': 'Repeated letters (like "gooogle") could be trying to fool you.'
            })
        
        # Numeric domain
        if features.get('num_digits', 0) > 5:
            score -= 12
            risk_factors.append({
                'factor': 'Many Numbers in URL',
                'severity': 'low',
                'description': 'The URL contains many digits, which is unusual for legitimate sites.',
                'simple': 'Lots of numbers in a website name can be suspicious.'
            })
        
        # ======== COMBINATION PENALTIES ========
        # If multiple medium/high risk factors, apply extra penalty
        if len(risk_factors) >= 4:
            combo_penalty = min(25, len(risk_factors) * 5)
            score -= combo_penalty
            risk_factors.append({
                'factor': 'Multiple Red Flags',
                'severity': 'high',
                'description': f'This URL has {len(risk_factors)} warning signs - a dangerous combination.',
                'simple': 'Multiple warning signs together means this link is very likely dangerous!'
            })
        
        # If any high risk factor found, limit positive boosts
        has_high_risk = high_risk_count > 0 or any(rf['severity'] == 'high' for rf in risk_factors)
        
        # ======== POSITIVE INDICATORS (limited if risk factors exist) ========
        if features.get('is_trusted_domain') and not has_high_risk:
            score = min(100, score + 25)
            safe_factors.append({
                'factor': 'Trusted Domain',
                'description': 'This is a well-known, trusted website.',
                'simple': 'This is a popular, well-known website that you can trust.'
            })
        elif features.get('is_trusted_domain') and has_high_risk:
            # Trusted domain with high risk indicators - likely spoofing attempt
            score -= 15
            risk_factors.append({
                'factor': 'Possible Brand Spoofing',
                'severity': 'high',
                'description': 'Appears to imitate a trusted domain but has dangerous characteristics.',
                'simple': 'This might be a fake version of a trusted website - be very careful!'
            })
        
        if features.get('trusted_tld') and not has_high_risk:
            score = min(100, score + 10)
            safe_factors.append({
                'factor': 'Trusted Domain Extension',
                'description': 'Uses a trusted TLD like .gov or .edu',
                'simple': 'Website ending in .gov or .edu are usually official and safe.'
            })
        
        if features.get('is_https') and not risk_factors:
            safe_factors.append({
                'factor': 'HTTPS Secured',
                'description': 'The website uses secure HTTPS encryption.',
                'simple': 'The padlock in your browser means your connection is encrypted.'
            })
        
        # Ensure score is within bounds
        score = max(0, min(100, score))
        
        # Determine risk level and status - MORE AGGRESSIVE THRESHOLDS
        if score >= 75 and len(risk_factors) == 0:
            risk_level = 'low'
            status = 'safe'
            status_label = 'URL appears safe'
            simple_summary = 'This link looks safe! We didn\'t find any major warning signs.'
        elif score >= 75 and len(risk_factors) <= 2:
            risk_level = 'low'
            status = 'safe'
            status_label = 'URL appears mostly safe'
            simple_summary = 'This link looks mostly safe, but we found minor concerns. Proceed carefully.'
        elif score >= 55:
            risk_level = 'medium'
            status = 'warning'
            status_label = 'Proceed with caution'
            simple_summary = 'Be careful with this link! It has some suspicious features. Verify it\'s really the website you want before entering any personal information.'
        else:
            risk_level = 'high'
            status = 'danger'
            status_label = 'Likely phishing attempt'
            simple_summary = '⚠️ WARNING: This link looks like a scam! Do not click it or enter any personal information. It may steal your passwords or infect your device.'
        
        return {
            'success': True,
            'trust_score': score,
            'phishing_probability': 100 - score,
            'risk_level': risk_level,
            'status': status,
            'status_label': status_label,
            'simple_summary': simple_summary,
            'risk_factors': risk_factors,
            'safe_factors': safe_factors,
            'feature_count': len(features),
            'features': features
        }
    
    def analyze_url(self, url: str) -> dict:
        """
        Main analysis function - analyzes a URL for phishing indicators
        """
        if not url:
            return {'success': False, 'error': 'No URL provided'}
        
        # Normalize URL
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            # Validate URL format
            parsed = urlparse(url)
            if not parsed.netloc:
                return {'success': False, 'error': 'Invalid URL format'}
            
            # Extract features
            features = self.extract_features(url)
            
            if not features:
                return {'success': False, 'error': 'Could not extract URL features'}
            
            # Calculate phishing score
            result = self.calculate_phishing_score(features)
            result['url'] = url
            result['domain'] = parsed.netloc
            result['method'] = 'Random Forest Feature Analysis'
            
            return result
            
        except Exception as e:
            logger.error(f"URL analysis failed: {e}")
            return {'success': False, 'error': str(e)}


# Create global instance
url_detector = URLPhishingDetector()


def analyze_url(url: str) -> dict:
    """Convenience function for URL analysis"""
    return url_detector.analyze_url(url)


if __name__ == "__main__":
    # Test the detector
    test_urls = [
        "https://google.com",
        "https://paypal-secure-login.xyz/verify?account=suspended",
        "http://192.168.1.1/login.php",
        "https://bit.ly/3xYz123",
        "https://secure-banking-login.paypa1.com/account",
        "https://www.nytimes.com/2024/article",
        "http://xn--pypal-4ve.com/signin"
    ]
    
    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        result = analyze_url(url)
        print(f"Trust Score: {result.get('trust_score')}%")
        print(f"Risk Level: {result.get('risk_level')}")
        print(f"Status: {result.get('status_label')}")
        if result.get('risk_factors'):
            print("Risk Factors:")
            for rf in result['risk_factors']:
                print(f"  - {rf['factor']} ({rf['severity']})")
