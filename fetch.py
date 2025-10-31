"""
HAC GPA Fetcher
"""

from gpa_scraper import PowerSchoolGPAScraper

# Configure credentials
USERNAME = input("Enter your HAC username: ")
PASSWORD = input("Enter your HAC password: ")
DISTRICT = "Bentonville School District"

def main():
    scraper = PowerSchoolGPAScraper(
        username=USERNAME,
        password=PASSWORD,
        district=DISTRICT
    )
    
    gpa = scraper.get_gpa()
    
    if gpa:
        print(f"Weighted Cumulative GPA: {gpa}")
    else:
        print("Failed to retrieve GPA")

if __name__ == "__main__":
    main()
