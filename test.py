import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import fitz  # PyMuPDF
import re
import streamlit as st
import os

import subprocess, sys, os

# Ensure packages are installed even if Streamlit Cloud misses them
required = {
    'beautifulsoup4==4.12.3',
    'soupsieve==2.5'
}
installed = {pkg.key for pkg in __import__('pkg_resources').working_set}
missing = required - installed

if missing:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL)

# Now safely import
from bs4 import BeautifulSoup

# Initialize session state
if 'reset_counter' not in st.session_state:
    st.session_state.reset_counter = 0
if 'show_success' not in st.session_state:
    st.session_state.show_success = False
if 'xml_data' not in st.session_state:
    st.session_state.xml_data = None
if 'filename' not in st.session_state:
    st.session_state.filename = "formatted_article_set.xml"
if 'processed_xml' not in st.session_state:
    st.session_state.processed_xml = None
if 'show_combine_section' not in st.session_state:
    st.session_state.show_combine_section = False
if 'final_combined_xml' not in st.session_state:
    st.session_state.final_combined_xml = None

# === Helper functions ===
def parse_date(date_str):
    for fmt in ["%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return str(dt.year), f"{dt.month:02d}", f"{dt.day:02d}"
        except:
            continue
    return "null", "null", "null"

def extract_history_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        combined_date = r"(?:[A-Za-z]{3,9}\s+\d{1,2},?\s*\d{4}|\d{1,2}\s+[A-Za-z]{3,9},?\s*\d{4})"

        patterns = [
            re.compile(rf"(?i)Received\s*[:\-]?\s*({combined_date}),\s*Accepted\s*[:\-]?\s*({combined_date})"),
            re.compile(rf"(?i)Received\s+({combined_date})\s+Accepted\s+({combined_date})"),
            re.compile(rf"(?i)Received\s+on\s+({combined_date})\s*;\s*Accepted\s+on\s+({combined_date})"),
            re.compile(rf"(?i)Received[:\-]?\s*({combined_date})\s*\|\s*(?:Revised[:\-]?\s*{combined_date}\s*\|\s*)?Accepted[:\-]?\s*({combined_date})"),
            re.compile(rf"(?i)Received\s*[:\-]?\s*({combined_date})\s*;\s*Accepted\s*[:\-]?\s*({combined_date})"),
        ]

        for page in doc:
            text = page.get_text()
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    r, a = match.group(1).strip(), match.group(2).strip()
                    return parse_date(r), parse_date(a)
        return (("null", "null", "null"), ("null", "null", "null"))
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return (("null", "null", "null"), ("null", "null", "null"))

def clear_form():
    st.session_state.reset_counter += 1
    st.session_state.show_success = True
    st.session_state.xml_data = None
    st.session_state.processed_xml = None
    st.session_state.filename = "formatted_article_set.xml"
    st.session_state.show_combine_section = False
    st.session_state.final_combined_xml = None

def generate_filename(article_url, xml_content):
    try:
        # Extract first digit from XML file
        root = ET.fromstring(xml_content)
        doi_elem = root.find(".//ELocationID[@EIdType='doi']")
        
        # Extract last digit from DOI (default to "0" if not found)
        last_doi_digit = "0"
        if doi_elem is not None and doi_elem.text:
            doi = doi_elem.text.strip()
            last_doi_digit = doi[-1] if doi[-1].isdigit() else "0"

        ##first_digit = next((char for char in xml_content if char.isdigit()))
        
        # Extract last number from article URL
        numbers = re.findall(r'\d+', article_url)
        last_url_num = numbers[-1] if numbers else "-"
        
        # Parse XML to get volume, issue, and year
        root = ET.fromstring(xml_content)
        
        # Get volume
        volume = root.find(".//Volume")
        vol_num = volume.text if volume is not None else "-"
        
        # Get issue
        issue = root.find(".//Issue")
        issue_num = issue.text if issue is not None else "-"
        
        year = "null"
        try:
            response = requests.get(article_url)
            soup = BeautifulSoup(response.content, "html.parser")
            published_div = soup.find("div", class_="list-group-item date-published")
            if published_div:
                text = published_div.get_text(strip=True).replace("Published:", "").strip()
                year, _, _ = parse_date(text)
        except Exception as e:
            st.warning(f"Could not extract year from article URL: {str(e)}")
            # Fallback to XML pubdate if available
            pub_date = root.find(".//PubDate[@PubStatus='pub']")
            if pub_date is not None:
                year_elem = pub_date.find("Year")
                if year_elem is not None and year_elem.text:
                    year = year_elem.text.strip()
        
        
        # Construct filename
        parts = [
            last_doi_digit,
            last_url_num,
            f"Vol.{vol_num}",
            f"No.{issue_num}",
            year
        ]
        return "_".join(parts) + ".xml"
    
    except Exception as e:
        st.warning(f"Could not generate filename: {str(e)}")
        return "formatted_article_set.xml"

def indent(elem, level=0):
    """Improved XML indentation function"""
    indent_str = "  "  # Two spaces per level
    newline = "\n"
    
    # Check if element has children
    if len(elem):
        # Add newline and indentation if this is the first child
        if not elem.text or not elem.text.strip():
            elem.text = newline + indent_str * (level + 1)
        
        # Process each child
        for i, child in enumerate(elem):
            indent(child, level + 1)
            
            # Add newline and indentation after each child
            if i < len(elem) - 1:  # Not the last child
                if not child.tail or not child.tail.strip():
                    child.tail = newline + indent_str * (level + 1)
            else:  # Last child
                if not child.tail or not child.tail.strip():
                    child.tail = newline + indent_str * level
    
    else:  # No children
        if level > 0 and (not elem.tail or not elem.tail.strip()):
            elem.tail = newline + indent_str * level

def process_files(pdf_file, input_xml, article_url, pdf_link):
    try:
        temp_pdf = "temp_uploaded.pdf"
        temp_xml = "temp_uploaded.xml"
        
        with st.spinner("Processing files..."):
            # Save uploaded files temporarily
            with open(temp_pdf, "wb") as f:
                f.write(pdf_file.getbuffer())
            
            with open(temp_xml, "wb") as f:
                f.write(input_xml.getbuffer())
            
            # Read XML content for filename generation
            with open(temp_xml, "r", encoding="utf-8") as f:
                xml_content = f.read()
            
            # Generate filename first
            st.session_state.filename = generate_filename(article_url, xml_content)
            
            # === Process the XML ===
            journal_shortcodes = {
                "Journal of Informatics and Web Engineering": "JIWE",
                "Journal of Engineering Technology and Applied Physics": "JETAK",
                "Asian Journal of Law and Policy": "AJLP",
                "International Journal of Creative Multimedia": "IJCM",
                "Journal of Management, Finance and Accounting": "IJOMFA",
                "Journal on Robotics, Automation and Sciences": "IJORAS",
                "Issues and Perspectives in Business and Social Sciences": "IPBSS",
                "Journal of Communication, Language and Culture": "JCLC"
            }

            tree = ET.parse(temp_xml)
            root = tree.getroot()
            
            # Process each article (we'll just process the first one)
            article = root.find(".//Article")
            if article is not None:
                journal = article.find("Journal")
                jt_elem = journal.find("JournalTitle") if journal is not None else None
                issn_elem = journal.find("Issn") if journal is not None else None
                if jt_elem is None or issn_elem is None:
                    raise ValueError("Journal title or ISSN not found")

                journal_title = jt_elem.text.strip()
                if journal_title not in journal_shortcodes:
                    raise ValueError(f"Journal title '{journal_title}' not in shortcodes")

                shortcode = journal_shortcodes[journal_title]
                pmc_id = shortcode.lower()
                article_out = ET.Element("Article")

                # Journal-meta
                journal_meta = ET.SubElement(article_out, "Journal-meta")
                for id_type, val in [("pmc", pmc_id), ("pubmed", journal_title), ("publisher", shortcode)]:
                    ET.SubElement(journal_meta, "journal-id", {"journal-id-type": id_type}).text = val
                ET.SubElement(journal_meta, "Issn").text = issn_elem.text.strip()
                
                publisher = ET.SubElement(journal_meta, "Publisher")
                ET.SubElement(publisher, "PublisherName").text = "MMU Press, Multimedia University"
                
                ET.SubElement(journal_meta, "JournalTitle").text = journal_title

                # article-meta
                article_meta = ET.SubElement(article_out, "article-meta")

                # IDs
                doi_elem = article.find(".//ELocationID[@EIdType='doi']")
                ET.SubElement(article_meta, "article-id", {"pub-id-type": "doi"}).text = doi_elem.text.strip() if doi_elem is not None else "null"
                volume = article.findtext(".//Volume", "null").strip()
                issue = article.findtext(".//Issue", "null").strip()
                first_page = article.findtext(".//FirstPage", "null").strip()
                custom_id = f"{shortcode[0].lower()}{shortcode}.v{volume}.i{issue}.pg{first_page}"
                ET.SubElement(article_meta, "article-id", {"pub-id-type": "other"}).text = custom_id

                # Title
                title_elem = article.find("ArticleTitle")
                ET.SubElement(article_meta, "ArticleTitle").text = title_elem.text.strip() if title_elem is not None else "null"

                # AuthorList
                author_list = article.find("AuthorList")
                if author_list is not None:
                    article_meta.append(author_list)
                else:
                    ET.SubElement(article_meta, "AuthorList")

                # Web scrape
                try:
                    response = requests.get(article_url)
                    soup = BeautifulSoup(response.content, "html.parser")

                    # Published Date
                    year, month, day = "null", "null", "null"
                    published_div = soup.find("div", class_="list-group-item date-published")
                    if published_div:
                        text = published_div.get_text(strip=True).replace("Published:", "").strip()
                        year, month, day = parse_date(text)

                    # epublish, retrieve from xml
                    epublish_date = article.find(".//PubDate[@PubStatus='epublish']")
                    if epublish_date is not None:
                        article_meta.append(epublish_date)

                    for pub_type in ['pub', 'cover']:
                        pd_elem = ET.Element("PubDate", {"PubStatus": pub_type})
                        for tag, val in zip(["Year", "Month", "Day"], [year, month, day]):
                            ET.SubElement(pd_elem, tag).text = val
                        article_meta.append(pd_elem)

                    # Keywords
             
                    keywords_elem = ET.SubElement(article_meta, "Keywords")
                    for meta in soup.find_all("meta", {"name": "citation_keywords"}):
                        keywords_content = meta.get("content", "")
                        # Split on either commas or semicolons, with optional whitespace
                        for kw in re.split(r'[;,]\s*', keywords_content):
                            kw = kw.strip()
                            if kw:
                                kw_elem = ET.SubElement(keywords_elem, "Keyword")
                                ET.SubElement(kw_elem, "italic").text = kw
                except Exception as e:
                    st.warning(f"Could not scrape article URL: {str(e)}")

                # Volume, Issue, FirstPage, LastPage
                for tag in ["Volume", "Issue", "FirstPage", "LastPage"]:
                    val = article.findtext(f".//{tag}", "null").strip()
                    ET.SubElement(article_meta, tag).text = val

                # PageCount
                try:
                    fp = int(article.findtext(".//FirstPage", "0").strip())
                    lp = int(article.findtext(".//LastPage", "0").strip())
                    page_count = str(max(0, lp - fp + 1))
                except:
                    page_count = "null"
                ET.SubElement(article_meta, "PageCount").text = page_count

                # History from PDF
                (r_year, r_month, r_day), (a_year, a_month, a_day) = extract_history_from_pdf(temp_pdf)
                history_elem = ET.Element("History")
                for status, y, m, d in [("received", r_year, r_month, r_day), ("accepted", a_year, a_month, a_day)]:
                    pubdate = ET.SubElement(history_elem, "PubDate", {"PubStatus": status})
                    ET.SubElement(pubdate, "Year").text = y
                    ET.SubElement(pubdate, "Month").text = m  # This line had the typo (was 'pudate')
                    ET.SubElement(pubdate, "Day").text = d
                article_meta.append(history_elem)

                # Abstract
                abstract = article.find("Abstract")
                abs_elem = ET.SubElement(article_meta, "abstract")
                p_elem = ET.SubElement(abs_elem, "p")
                p_elem.text = abstract.text.strip() if abstract is not None else "null"

                # Fulltext links and lang
                ET.SubElement(article_meta, "pdf-link").text = pdf_link if pdf_link else "null"
                ET.SubElement(article_meta, "full_text_url").text = article_url if article_url else "null"
                ET.SubElement(article_meta, "Language").text = "eng"

                # Format XML with improved indentation
                indent(article_out)
                
                # Convert to string without XML declaration
                xml_str = ET.tostring(article_out, encoding='utf-8', method='xml').decode()
                
                st.session_state.processed_xml = xml_str
                st.session_state.show_combine_section = True
                
                st.success("Initial XML processing complete! You can now combine with template XML.")
                
                # Preview
                with st.expander("Preview Processed XML Output"):
                    st.code(xml_str[:2000] + "..." if len(xml_str) > 2000 else xml_str, language="xml")
            else:
                raise ValueError("No Article element found in the input XML")
                
    except Exception as e:
        st.error(f"An error occurred during processing: {str(e)}")
    finally:
        # Clean up temporary files
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)
        if os.path.exists(temp_xml):
            os.remove(temp_xml)

def combine_with_template(template_file):
    try:
        temp_template = "temp_template.xml"
        
        with st.spinner("Combining with template..."):
            # Save template file temporarily
            with open(temp_template, "wb") as f:
                f.write(template_file.getbuffer())
            
            # Get processed XML content
            processed_root = ET.fromstring(st.session_state.processed_xml)
            
            # Create new front section with Article element
            front = ET.Element("front")
            front.text = "\n  "  # Initial indentation
            
            # Create Article element as child of front
            article = ET.SubElement(front, "Article")
            article.text = "\n    "  # Indent Article content
            
            # Function to copy elements recursively with proper indentation
            def copy_element(source, target, indent_level):
                indent = "  " * indent_level
                for elem in source:
                    new_elem = ET.SubElement(target, elem.tag)
                    if elem.text:
                        new_elem.text = elem.text
                    if elem.attrib:
                        new_elem.attrib.update(elem.attrib)
                    
                    # Set proper indentation
                    new_elem.tail = f"\n{indent}"
                    
                    # Handle children recursively
                    if len(elem) > 0:
                        new_elem.text = f"\n{indent}  "
                        copy_element(elem, new_elem, indent_level + 1)
                        new_elem[-1].tail = f"\n{indent}"
            
            # Process Journal-meta
            journal_meta = processed_root.find("Journal-meta")
            if journal_meta is not None:
                new_journal_meta = ET.SubElement(article, "Journal-meta")
                new_journal_meta.text = "\n      "
                copy_element(journal_meta, new_journal_meta, 3)
                new_journal_meta[-1].tail = "\n    "
                new_journal_meta.tail = "\n    "
            
            # Process article-meta
            article_meta = processed_root.find("article-meta")
            if article_meta is not None:
                new_article_meta = ET.SubElement(article, "article-meta")
                new_article_meta.text = "\n      "
                copy_element(article_meta, new_article_meta, 3)
                new_article_meta[-1].tail = "\n    "
                new_article_meta.tail = "\n  "
            
            # Final formatting adjustments
            article.tail = "\n"
            
            # Convert to string
            xml_str = ET.tostring(front, encoding='utf-8').decode()
            
            # Read template content
            with open(temp_template, "r", encoding="utf-8") as f:
                template_content = f.read()
            
            # Find and replace front section
            front_start = template_content.find("<front>")
            front_end = template_content.find("</front>")
            
            if front_start == -1 or front_end == -1:
                st.error("Template does not contain <front> tags")
                return
            
            # Build final content
            combined_content = (
                template_content[:front_start] +
                xml_str +
                template_content[front_end + len("</front>"):]
            )
            
            st.session_state.final_combined_xml = combined_content
            st.success("XML successfully combined with template!")
            
            # Preview
            with st.expander("Preview Combined XML Output"):
                st.code(combined_content, language="xml")
                
    except Exception as e:
        st.error(f"Error combining with template: {str(e)}")
    finally:
        if os.path.exists(temp_template):
            os.remove(temp_template)
            
# === Main App ===
def main():
    st.title("Journal Article XML Generator")
    st.markdown('<div style="font-size:18px;margin-bottom:10px; font-weight:600">This tool creates JATS XML by merging metadata from the article PDF and web input with back-section content from Vertopal.</div>', unsafe_allow_html=True)
    
    # Add vertical space
    st.write("")
    
    # Generate unique keys based on reset counter
    reset_key = st.session_state.reset_counter
    
    # Create a form container for input fields
    with st.form("input_form"):
        # PDF File Upload 
        st.markdown('<div style="font-size:25px; font-weight:600; margin-bottom:10px;">Upload PDF File</div>', unsafe_allow_html=True)
        pdf_file = st.file_uploader(
            " ",
            type=['pdf'], 
            help="Upload the article PDF file",
            key=f"pdf_uploader_{reset_key}",
            label_visibility="collapsed"
        )
        
        # XML File Upload 
        st.markdown('<div style="font-size:25px; font-weight:600; margin-bottom:10px;">Upload Input XML File</div>', unsafe_allow_html=True)
        input_xml = st.file_uploader(
            " ",
            type=['xml'], 
            help="Upload the original XML metadata file",
            key=f"xml_uploader_{reset_key}",
            label_visibility="collapsed"
        )
        
        # Article URL
        st.markdown('<div style="font-size:25px; font-weight:600; margin-bottom:-30px;">Article URL</div>', unsafe_allow_html=True)
        article_url = st.text_input(
            label=" ",
            help="Enter the URL of the article webpage", 
            key=f"article_url_{reset_key}",
            value=""
        )

        st.markdown('<div style="font-size:25px; font-weight:600; margin-bottom:-30px;">PDF Link</div>', unsafe_allow_html=True)
        pdf_link = st.text_input(
            label=" ", 
            help="Enter the direct URL to the PDF file", 
            key=f"pdf_link_{reset_key}",
            value=""
        )
        
        # Add vertical space
        st.write("")
        
        # Create columns for buttons
        col1, col2 = st.columns([1, 4])
        
        with col1:
            reset_button = st.form_submit_button("Reset", type="secondary")
        
        with col2:
            submit_button = st.form_submit_button("Generate XML", type="primary")

        # Handle reset
        if reset_button:
            clear_form()
            st.rerun()
            
        # Handle form submission
        if submit_button:
            if not all([pdf_file, input_xml, article_url]):
                st.warning("Please provide all required files and URLs")
            else:
                process_files(pdf_file, input_xml, article_url, pdf_link)
    
    # Show template combination section after initial processing
    if st.session_state.show_combine_section:
        st.markdown("---")
        st.markdown('<div style="font-size:25px; font-weight:600; margin-bottom:10px;">Combine with Template XML</div>', unsafe_allow_html=True)
        
        with st.form("template_form"):
            template_file = st.file_uploader(
                "Upload Template XML",
                type=['xml'],
                help="Upload the template XML file to combine with (must contain <front> section)",
                key=f"template_uploader_{reset_key}"
            )
            
            combine_button = st.form_submit_button("Combine with Template")
            
            if combine_button:
                if template_file is None:
                    st.warning("Please upload a template XML file")
                else:
                    combine_with_template(template_file)
    
    # Show download buttons
    if st.session_state.processed_xml:
        st.download_button(
            label="Download Processed XML",
            data=st.session_state.processed_xml,
            file_name=st.session_state.filename,
            mime="application/xml",
            key="processed_download"
        )
    
    if st.session_state.final_combined_xml:
        st.download_button(
            label="Download Combined XML",
            data=st.session_state.final_combined_xml,
            file_name=st.session_state.filename,
            mime="application/xml",
            key="combined_download"
        )
    
    # Show success message after reset if needed
    if st.session_state.show_success:
        st.success("All inputs have been cleared!")
        st.session_state.show_success = False


if __name__ == "__main__":
    main()
