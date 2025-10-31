"""
PowerSchool HomeAccess GPA Scraper
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import Optional


class PowerSchoolGPAScraper:
    """Scraper for extracting GPA from PowerSchool HomeAccess"""
    
    def __init__(self, username: str, password: str, district: str = "Bentonville School District"):
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.district = district
        self.base_url = "https://hac23.esp.k12.ar.us"
        self.login_url = f"{self.base_url}/HomeAccess/Account/LogOn?ReturnUrl=%2fhomeaccess"
        self.login_page_html = None
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def _parse_form(self, soup: BeautifulSoup) -> dict:
        """Extract form data including hidden fields"""
        form_data = {}
        form = soup.find('form')
        
        if not form:
            return form_data
        
        for inp in form.find_all('input'):
            name = inp.get('name')
            value = inp.get('value', '')
            if name:
                form_data[name] = value
        
        for select in form.find_all('select'):
            name = select.get('name')
            if name:
                selected = select.find('option', selected=True) or select.find('option')
                if selected:
                    form_data[name] = selected.get('value', '')
        
        return form_data
    
    def select_district(self) -> bool:
        """Select the school district on the login page"""
        try:
            response = self.session.get(self.login_url, allow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            district_select = soup.find('select', {'id': 'Database'}) or \
                            soup.find('select', {'name': 'Database'})
            
            if district_select:
                district_option = district_select.find('option', string=re.compile(self.district, re.I))
                if district_option:
                    district_value = district_option.get('value')
                    form_data = self._parse_form(soup)
                    form_data['Database'] = district_value
                    
                    form = soup.find('form')
                    form_action = form.get('action', '') if form else ''
                    action_url = self._resolve_url(form_action) if form_action else self.login_url
                    
                    response = self.session.post(action_url, data=form_data, allow_redirects=True)
                    response.raise_for_status()
                    
                    self.login_page_html = response.text
                    
                    soup_after = BeautifulSoup(response.text, 'html.parser')
                    username_field = soup_after.find('input', {'name': re.compile(r'UserName', re.I)})
                    password_field = soup_after.find('input', {'type': 'password'})
                    
                    if username_field and password_field:
                        return True
                    return False
            
            login_form = soup.find('input', {'type': 'password'})
            return login_form is not None
            
        except Exception:
            return False
    
    def login(self) -> bool:
        """Login with username and password"""
        try:
            if self.login_page_html:
                html = self.login_page_html
            else:
                response = self.session.get(self.login_url, allow_redirects=True)
                response.raise_for_status()
                html = response.text
            
            soup = BeautifulSoup(html, 'html.parser')
            login_form = soup.find('form')
            
            if not login_form:
                return False
            
            form_data = self._parse_form(soup)
            
            username_field = soup.find('input', {'name': re.compile(r'UserName', re.I)})
            password_fields = soup.find_all('input', {'type': 'password'})
            password_field = None
            
            for pf in password_fields:
                if 'temp' not in pf.get('id', '').lower():
                    password_field = pf
                    break
            
            if not username_field or not password_field:
                return False
            
            form_data[username_field.get('name')] = self.username
            form_data[password_field.get('name')] = self.password
            
            form_action = login_form.get('action', '')
            action_url = self._resolve_url(form_action) if form_action else self.login_url
            
            response = self.session.post(action_url, data=form_data, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            validation_summary = soup.find('div', class_=re.compile(r'validation-summary-errors', re.I))
            if validation_summary:
                return False
            
            if 'LogOn' in response.url.lower():
                return False
            
            return True
            
        except Exception:
            return False
    
    def navigate_to_transcript(self) -> Optional[str]:
        """Navigate to the transcript page"""
        try:
            dashboard_url = f"{self.base_url}/HomeAccess"
            response = self.session.get(dashboard_url, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            transcript_link = None
            
            for link in soup.find_all('a', href=True):
                if 'transcript' in link.get('href', '').lower():
                    transcript_link = link.get('href')
                    break
            
            if not transcript_link:
                transcript_link = '/HomeAccess/Content/Student/Transcript.aspx'
            
            transcript_url = self._resolve_url(transcript_link)
            response = self.session.get(transcript_url, allow_redirects=True)
            response.raise_for_status()
            
            return response.text
            
        except Exception:
            return None
    
    def extract_gpa(self, html: str) -> Optional[float]:
        """Extract Weighted Cumulative GPA from transcript HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            patterns = [
                r'Weighted\s+Cumulative\s+GPA[:\s]*([\d.]+)',
                r'Cumulative\s+Weighted\s+GPA[:\s]*([\d.]+)',
                r'Weighted\s+GPA[:\s]*([\d.]+)',
            ]
            
            text_content = soup.get_text()
            
            for pattern in patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    return float(match.group(1))
            
            tables = soup.find_all('table')
            for table in tables:
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    cell_text = ' '.join([cell.get_text(strip=True) for cell in cells])
                    
                    if re.search(r'weighted.*cumulative.*gpa', cell_text, re.IGNORECASE):
                        for cell in cells:
                            cell_value = cell.get_text(strip=True)
                            if re.match(r'^([\d.]+)$', cell_value):
                                gpa_value = float(cell_value)
                                if 0.0 <= gpa_value <= 5.0:
                                    return gpa_value
            
            return None
            
        except Exception:
            return None
    
    def _resolve_url(self, url: str) -> str:
        """Resolve relative URLs to absolute URLs"""
        if url.startswith('http'):
            return url
        elif url.startswith('/'):
            return f"{self.base_url}{url}"
        else:
            return f"{self.base_url}/{url}"
    
    def get_gpa(self) -> Optional[float]:
        """Main method that orchestrates all steps to get GPA"""
        try:
            self.select_district()
            
            if not self.login():
                return None
            
            transcript_html = self.navigate_to_transcript()
            if not transcript_html:
                return None
            
            return self.extract_gpa(transcript_html)
            
        except Exception:
            return None
