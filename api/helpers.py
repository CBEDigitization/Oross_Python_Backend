"""
Helper functions for the OROSS API.
This module contains utility functions for processing and formatting data from the OpenAlex API.
"""
from bs4 import BeautifulSoup

import re

def convert_mathml_to_plain(text):
    # Wrap the text in a root element if it is not already a complete XML document
    wrapped_text = f"<root>{text}</root>"
    soup = BeautifulSoup(wrapped_text, "lxml-xml")
    
    # Extract text from the parsed XML
    plain_text = soup.get_text(separator=" ", strip=True)
    
    # Optional: Additional cleanup if necessary (e.g., removing extra spaces)
    plain_text = " ".join(plain_text.split())
    
    return plain_text

def replace_mathml(match):
    """Helper function to convert a MathML segment to plain text."""
    mathml = match.group(0)
    try:
        # Parse the MathML snippet using the lxml XML parser
        soup = BeautifulSoup(mathml, "lxml-xml")
        # Extract text from the MathML tags
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        print("Error parsing MathML:", e)
        # Fallback: return the original mathml if parsing fails
        return mathml

def convert_mathml_and_latex_to_plain(text):
    """
    Converts a string containing MathML and LaTeX into a plain text format.
    It:
      - Finds MathML segments and replaces them with plain text.
      - Removes LaTeX math delimiters ($$ or $).
      - Replaces specific LaTeX commands with plain text equivalents.
    """
    # Replace all MathML segments with plain text using the helper function
    text = re.sub(r"<mml:math[\s\S]*?</mml:math>", replace_mathml, text)

    # Remove LaTeX math delimiters
    text = text.replace('$$', '').replace('$', '')

    # Replace specific LaTeX commands
    text = text.replace(r'\sqrt{s}', '√s')

    # Replace \text{...} with the inner content
    text = re.sub(r'\\text\s*\{([^}]*)\}', r'\1', text)

    # Remove any \hspace commands (and their arguments)
    text = re.sub(r'\\hspace\{[^}]*\}', '', text)

    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def parse_affiliation(raw_str):
    """
    Parse a raw affiliation string into structured components.
    
    Args:
        raw_str (str): The raw affiliation string from OpenAlex.
        
    Returns:
        dict: A dictionary containing parsed components:
            - department: The department name if found
            - university: The university name if found
            - faculty: The faculty name if found
            - county: The county/province/state (usually the last part)
            - full_affiliation: The original raw affiliation string
    
    Note:
        This is a heuristic parser and may need adjustments for different affiliation formats.
    """
    if not raw_str:
        return {}
        
    parts = [p.strip() for p in raw_str.split(",")]
    department = None
    university = None
    faculty = None
    county = None

    for part in parts:
        lower = part.lower()
        if lower.startswith("department"):
            department = part
        if "university" in lower:
            university = part
        if "faculty" in lower:
            faculty = part

    # As a simple heuristic, we take the last part as the county (or province/state)
    if len(parts) >= 2:
        county = parts[-1]

    return {
        "department": department,
        "university": university,
        "faculty": faculty,
        "county": county,
        "full_affiliation": raw_str
    }

def reconstruct_abstract(inverted_index):
    """
    Reconstruct a readable abstract from an inverted index representation.
    
    Args:
        inverted_index (dict): A dictionary where keys are words and values are lists of positions.
        
    Returns:
        str: The reconstructed abstract as a string.
        
    Note:
        OpenAlex stores abstracts as inverted indices for efficiency. This function
        converts that representation back to a readable paragraph.
    """
    if not inverted_index:
        return ""
    
    # Determine the maximum position to allocate the list.
    max_index = max(pos for positions in inverted_index.values() for pos in positions)
    abstract_words = [""] * (max_index + 1)
    
    for word, positions in inverted_index.items():
        for pos in positions:
            abstract_words[pos] = word
    return " ".join(abstract_words)

def format_publication(result):
    """
    Format a publication result from OpenAlex API into a standardized structure.
    
    Args:
        result (dict): The raw publication data from OpenAlex API.
        
    Returns:
        dict: A formatted publication with consistent structure containing:
            - Basic metadata (id, title, year, doi)
            - Authors with parsed affiliations
            - Publication details
            - Open access information
            - Grant information
            - Topic classification
            - Reconstructed abstract
            
    Note:
        This function ensures consistent formatting across different endpoints
        that return publication data.
    """
    if not result:
        return {}
        
    # Build a list of authors with enhanced affiliation details.
    authors = []
    for authorship in result.get("authorships", []):
        author = authorship.get("author", {})
        author_position = authorship.get("author_position")
        raw_affiliations = authorship.get("raw_affiliation_strings", [])
        if raw_affiliations:
            affiliation_data = parse_affiliation(raw_affiliations[0])
        else:
            affiliation_data = {}
        authors.append({
            "name": author.get("display_name"),
            "orcid": author.get("orcid"),
            "author_position": author_position,
            "affiliation": affiliation_data
        })
    
    # Extract additional publication details.
    publication_details = {
        "publication_date": result.get("publication_date"),
        "biblio": result.get("biblio"),
        "landing_page_url": result.get("primary_location", {}).get("landing_page_url"),
        "pdf_url": result.get("primary_location", {}).get("pdf_url")
    }

    # Extract open access details.
    is_open_access = result.get("open_access", {}).get("is_oa")
    open_access_status = result.get("open_access", {}).get("oa_status")
    open_access_url = result.get("open_access", {}).get("oa_url")

    grants = result.get("grants", [])
    grant_funder_name = grants[0].get("funder_display_name") if grants else None
    grant_award_id = grants[0].get("award_id") if grants else None

    # Reconstruct abstract from inverted index.
    abstract = reconstruct_abstract(result.get("abstract_inverted_index"))
    converted_abstract = convert_mathml_to_plain(abstract)

    # Format XML title.
    title = result.get("title")
    converted_title = convert_mathml_to_plain(title)
  

    
    return {
        "id": result.get("id"),
        # "title": result.get("title"),
        "title": converted_title,
        "publication_year": result.get("publication_year"),
        "doi": result.get("doi"),
        "authors": authors,
        "research_type": result.get("type"),
        "type_of_paper_crossref": result.get("type_crossref"),
        "publication_details": publication_details,
        "pdf_url_to_openAlex": result.get("id"),
        "title_as_displayName": result.get("display_name"),
        "is_open_access": is_open_access,
        "open_access_status": open_access_status,
        "open_access_url": open_access_url,
        "article_processing_charge_list": result.get("apc_list"),
        "article_processing_charge_paid": result.get("apc_paid"),
        "topics": result.get("primary_topic", {}).get("display_name"),
        "field": result.get("primary_topic", {}).get("field", {}).get("display_name"),
        "subfield": result.get("primary_topic", {}).get("subfield", {}).get("display_name"),
        "domain": result.get("primary_topic", {}).get("domain", {}).get("display_name"),
        "sustainable_development_goals": result.get("sustainable_development_goals", []),
        "grant_funder_name": grant_funder_name,
        "grant_award_id": grant_award_id,
        "abstract": converted_abstract
    } 

