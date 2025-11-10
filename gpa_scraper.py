"""
PowerSchool HomeAccess GPA Scraper
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import Optional, Dict, Any


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
    
    def _fetch_dashboard_html(self) -> Optional[str]:
        """Retrieve the dashboard page HTML after login."""
        try:
            dashboard_url = f"{self.base_url}/HomeAccess"
            response = self.session.get(dashboard_url, allow_redirects=True)
            response.raise_for_status()
            return response.text
        except Exception:
            return None

    def navigate_to_transcript(self, dashboard_html: Optional[str] = None) -> Optional[str]:
        """Navigate to the transcript page using optional cached dashboard HTML."""
        try:
            if dashboard_html is None:
                dashboard_html = self._fetch_dashboard_html()
            if not dashboard_html:
                return None
            
            soup = BeautifulSoup(dashboard_html, 'html.parser')
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
    
    def _extract_weighted_cumulative_gpa(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract Weighted Cumulative GPA from parsed transcript HTML"""
        try:
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

    def _parse_year_start(self, year_str: str) -> Optional[int]:
        match = re.match(r'(\d{4})', year_str)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def _extract_latest_transcript_section(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Extract the most recent transcript summary using text segmentation."""
        text = soup.get_text(' ', strip=True)
        # Normalize whitespace to simplify regex matching
        text = re.sub(r'\s+', ' ', text)

        year_pattern = re.compile(r'Year:\s*([0-9]{4}-[0-9]{2})', re.IGNORECASE)
        grade_pattern = re.compile(r'Grade:\s*([0-9A-Za-z]+)', re.IGNORECASE)
        building_pattern = re.compile(
            r'Building:\s*(.*?)(?=Year:|Grade:|Course\s+Description|Sem1|Sem2|Credit|Total\s+Credit|Weighted|Unweighted|$)',
            re.IGNORECASE
        )

        matches = list(year_pattern.finditer(text))
        if not matches:
            return None

        sections = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block = text[start:end]

            section: Dict[str, str] = {'year': match.group(1)}

            grade_match = grade_pattern.search(block)
            if grade_match:
                section['grade'] = grade_match.group(1)

            building_match = building_pattern.search(block)
            if building_match:
                school_raw = building_match.group(1).strip()
                school_clean = re.split(r'(?:Course\s+Description|Sem1|Sem2|Credit|Total\s+Credit)', school_raw, flags=re.IGNORECASE)[0].strip(' -,:;')
                section['school'] = school_clean

            sections.append(section)

        latest_section: Optional[Dict[str, str]] = None
        latest_year_start: Optional[int] = None

        for section in sections:
            year_str = section.get('year')
            if not year_str:
                continue
            start_year = self._parse_year_start(year_str)
            if start_year is None:
                continue

            if latest_year_start is None or start_year > latest_year_start:
                latest_year_start = start_year
                latest_section = section

        return latest_section

    def _is_valid_student_name(self, name: str) -> bool:
        if not name:
            return False
        parts = [part.strip() for part in name.split() if part.strip()]
        if len(parts) < 2 or len(parts) > 5:
            return False
        banned_tokens = {'total', 'credit', 'weighted', 'unweighted', 'gpa', 'grade', 'school'}
        for part in parts:
            normalized = part.lower().strip(".,'-")
            if normalized in banned_tokens:
                return False
            if not re.match(r"^[A-Za-z][A-Za-z.'-]*$", part):
                return False
        return True

    def _extract_student_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract student name using the dashboard header identity menu."""
        try:
            identity_span = soup.select_one('.sg-banner-menu-element.sg-menu-element-identity span')
            if identity_span:
                candidate = identity_span.get_text(strip=True)
                if self._is_valid_student_name(candidate):
                    return candidate

            banner_container = soup.find('div', attrs={'data-student-id': True})
            if banner_container:
                for span in banner_container.find_all('span'):
                    candidate = span.get_text(strip=True)
                    if self._is_valid_student_name(candidate):
                        return candidate

            logout_link = soup.find('a', string=re.compile(r'logout', re.I))
            if logout_link:
                identity_li = logout_link.find_previous('li', class_=re.compile(r'sg-menu-element-identity', re.I))
                if identity_li:
                    span = identity_li.find('span')
                    if span:
                        candidate = span.get_text(strip=True)
                        if self._is_valid_student_name(candidate):
                            return candidate

                parent_menu = logout_link.find_parent('ul')
                if parent_menu:
                    for li in parent_menu.find_all('li', recursive=False):
                        classes = ' '.join(li.get('class', []))
                        if re.search(r'identity', classes, re.I):
                            span = li.find('span')
                            if span:
                                candidate = span.get_text(strip=True)
                                if self._is_valid_student_name(candidate):
                                    return candidate

            return None
        except Exception:
            return None

    def extract_transcript_info(
        self,
        html: str,
        dashboard_soup: Optional[BeautifulSoup] = None,
        student_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Extract transcript summary details including student name, latest year, school, and GPA."""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            info: Dict[str, Any] = {}

            resolved_name = student_name
            if resolved_name is None and dashboard_soup is not None:
                resolved_name = self._extract_student_name(dashboard_soup)
            if resolved_name is None:
                resolved_name = self._extract_student_name(soup)

            if resolved_name:
                info['student_name'] = resolved_name

            gpa = self._extract_weighted_cumulative_gpa(soup)
            if gpa is not None:
                info['weighted_cumulative_gpa'] = gpa

            latest_section = self._extract_latest_transcript_section(soup)
            if latest_section:
                if latest_section.get('year'):
                    info['latest_transcript_year'] = latest_section['year']
                if latest_section.get('school'):
                    info['latest_transcript_school'] = latest_section['school']
                if latest_section.get('grade'):
                    info['latest_transcript_grade'] = latest_section['grade']

            return info or None

        except Exception:
            return None

    def extract_gpa(self, html: str) -> Optional[float]:
        """Extract only the Weighted Cumulative GPA from transcript HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            return self._extract_weighted_cumulative_gpa(soup)
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
    
    def get_transcript_info(self) -> Optional[Dict[str, Any]]:
        """Main method that orchestrates all steps to collect transcript summary info including student name."""
        try:
            self.select_district()
            
            if not self.login():
                return None

            dashboard_html = self._fetch_dashboard_html()
            dashboard_soup = BeautifulSoup(dashboard_html, 'html.parser') if dashboard_html else None
            student_name = self._extract_student_name(dashboard_soup) if dashboard_soup else None
            
            transcript_html = self.navigate_to_transcript(dashboard_html)
            if not transcript_html:
                return None
            
            info = self.extract_transcript_info(transcript_html, dashboard_soup, student_name)

            if info is None:
                # Fall back to GPA-only extraction if the richer parser fails
                gpa_only = self.extract_gpa(transcript_html)
                if gpa_only is not None:
                    info = {'weighted_cumulative_gpa': gpa_only}
                    if student_name:
                        info['student_name'] = student_name

            return info
            
        except Exception:
            return None

    def get_gpa(self) -> Optional[float]:
        """Backward-compatible helper that returns only the weighted GPA."""
        transcript_info = self.get_transcript_info()
        if not transcript_info:
            return None
        gpa = transcript_info.get('weighted_cumulative_gpa')
        return gpa if isinstance(gpa, (int, float)) else None
