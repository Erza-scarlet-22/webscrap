import streamlit as st
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
from urllib.parse import urljoin, urlparse
import re

# Function to scrape website content
def scrape_website(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup
    except requests.exceptions.RequestException as e:
        st.error(f"Error during web scraping: {e}")
        return None

# Function to extract clean text from BeautifulSoup object
def extract_clean_text(element):
    if element:
        text = element.get_text()
        text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces, newlines, tabs with single space
        text = text.strip()  # Remove leading and trailing whitespace
        return text
    else:
        return ""

# Function to generate PDF from text content
def create_pdf(content, output_filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    for item in content:
        text = item['text']
        is_heading = item['is_heading']
        is_question = item['is_question']
        if is_heading:
            pdf.set_font("Helvetica", style='B', size=12)
            pdf.multi_cell(0, 10, text.encode('latin-1', 'replace').decode('latin-1'))
            pdf.set_font("Helvetica", size=12)  # Reset to normal font
        elif is_question:
            pdf.set_font("Helvetica", style='B', size=12)
            pdf.multi_cell(0, 10, f"Question: {text}".encode('latin-1', 'replace').decode('latin-1'))
            pdf.set_font("Helvetica", size=12)  # Reset to normal font
        else:
            pdf.multi_cell(0, 10, f"Reply: {text}".encode('latin-1', 'replace').decode('latin-1'))
    
    pdf.output(output_filename)

# Function to check if a page is a detailed topic page
def is_topic_page(soup):
    return soup.find('div', {'class': 'lia-thread-container'}) is not None

# Function to extract texts from a detailed topic page
def extract_texts_from_topic(soup):
    texts = []
    discussion_title = soup.find('h1', {'class': 'lia-message-subject'})
    if discussion_title:
        texts.append({'text': extract_clean_text(discussion_title), 'is_heading': True, 'is_question': False})

    question = soup.find('div', {'class': 'lia-message-body-content'})
    if question:
        texts.append({'text': extract_clean_text(question), 'is_heading': False, 'is_question': True})

    replies = soup.find_all('div', {'class': 'lia-message-body-content'})
    for reply in replies[1:]:  # Skip the first one as it is the question
        texts.append({'text': extract_clean_text(reply), 'is_heading': False, 'is_question': False})

    return texts

# Function to extract texts from headings and paragraphs within the Community Activity section
def extract_texts_from_soup(soup):
    texts = []
    community_activity_section = soup.find('div', {'class': 'custom-community-activity'})  # Adjust the class or tag accordingly
    if community_activity_section:
        for element in community_activity_section.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p']):
            text = extract_clean_text(element)
            is_heading = element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
            if text:
                texts.append({'text': text, 'is_heading': is_heading, 'is_question': False})
    return texts

# Function to scrape threads from a specific discussion category
def scrape_threads(base_url):
    try:
        response = requests.get(base_url)
        response.raise_for_status()  # Raise an error for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')
        thread_links = []

        # Extract thread links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/t5/' in href and '/td-p/' in href:
                thread_links.append(urljoin(base_url, href))

        # Scrape each thread
        all_texts = []
        visited_links = set()
        for link in thread_links:
            if link not in visited_links:
                visited_links.add(link)
                try:
                    response = requests.get(link)
                    response.raise_for_status()
                    sub_soup = BeautifulSoup(response.content, 'html.parser')
                    sub_texts = extract_texts_from_topic(sub_soup)
                    if sub_texts:
                        all_texts.extend(sub_texts)
                        st.success(f"Scraped content from {link}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Error scraping {link}: {e}")

        return all_texts

    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching threads from {base_url}: {e}")
        return []

# Function to find and scrape all categories from the main page
def scrape_categories(main_url):
    categories = []
    soup = scrape_website(main_url)
    if soup:
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Exclude specified categories
            excluded_categories = [
                '/t5/简体中文-simplified-chinese/ct-p/simplified-chinese-community',
                '/t5/japan-community/ct-p/LiveJP',
                '/t5/korean-community/ct-p/Korean-Community',
                '/t5/繁體中文-traditional-chinese/ct-p/traditional-chinese-community',
                '/t5/get-started/ct-p/get_started',
                '/t5/news-events/ct-p/News-Events',
                '/t5/events/ct-p/events',
                '/t5/ignite-conference/ct-p/Ignite'
            ]
            if any(excluded in href for excluded in excluded_categories):
                continue
            if '/t5/' in href and '/ct-p/' in href:
                categories.append(urljoin(main_url, href))
    return categories

# Streamlit app
def main():
    st.title("Palo Alto Networks Community Content Scraper")

    # Main URL
    main_url = "https://live.paloaltonetworks.com/"

    if st.button("Export to PDF"):
        st.info("Scraping website...")

        # Scrape all categories from the main page
        categories = scrape_categories(main_url)

        if categories:
            all_texts = []
            visited_links = set()

            for category in categories:
                st.info(f"Scraping category: {category}")
                category_texts = scrape_threads(category)
                if category_texts:
                    all_texts.extend(category_texts)

            if all_texts:
                # Generate single PDF with all content
                create_pdf(all_texts, "all_content.pdf")
                st.success("All content aggregated into a single PDF. Download below.")

                # Provide download link for the generated PDF
                with open("all_content.pdf", "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(label="Download All Content PDF", data=pdf_bytes, file_name="all_content.pdf")
            else:
                st.error("No content scraped. Please check the URL and try again.")
        else:
            st.error("No categories found. Please check the URL and try again.")

if __name__ == "__main__":
    main()
