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
    
    transcript_info = scraper.get_transcript_info()

    if not transcript_info:
        print("Failed to retrieve transcript information")
        gpa_only = scraper.get_gpa()
        if gpa_only is not None:
            print(f"Weighted Cumulative GPA: {gpa_only}")
        return

    student_name = transcript_info.get('student_name')
    latest_year = transcript_info.get('latest_transcript_year')
    latest_school = transcript_info.get('latest_transcript_school')
    latest_grade = transcript_info.get('latest_transcript_grade')
    gpa = transcript_info.get('weighted_cumulative_gpa')

    if student_name:
        print(f"Student Name: {student_name}")
    if latest_year:
        print(f"Latest Transcript Year: {latest_year}")
    if latest_grade:
        print(f"Latest Transcript Grade: {latest_grade}")
    if latest_school:
        print(f"Latest Transcript School: {latest_school}")

    if gpa is not None:
        print(f"Weighted Cumulative GPA: {gpa}")
    else:
        print("Weighted Cumulative GPA not found")

if __name__ == "__main__":
    main()
