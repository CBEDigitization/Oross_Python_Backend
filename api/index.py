from flask import Flask, jsonify, request
import requests
from flask_cors import CORS, cross_origin

app = Flask(__name__)
#CORS(app, resources={r"/*": {"origins": "*"}})
CORS(app)

USER_AGENT = "MyScript (your-email@example.com)"

def parse_affiliation(raw_str):
    """
    A simple parser that splits the raw affiliation string by commas.
    It then tries to identify the department, university, faculty, and county.
    Note: This is heuristic and may need adjustments for different affiliation formats.
    """
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
    Reconstructs the abstract paragraph from the inverted index representation.
    It creates a list of words in the correct order based on their positions.
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


@app.route("/")
def index():
    return "Hello form OROSS"
@app.route("/works", methods=["GET"])
def get_publications():
    """
    Endpoint to retrieve publications from the University of Johannesburg with pagination.
    A query parameter 'page' can be provided by the frontend to load different pages.
    """
    # Get the page number from the query parameters; default to 1 if not provided.
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=10, type=int)
    
    url = "https://api.openalex.org/works"
    params = {
        "page": page,
        "filter": "authorships.institutions.lineage:i24027795",
        "sort": "publication_year:desc",
        "per_page": per_page
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        meta = { 
                "count": data.get("meta", {}).get("count"),
                "db_response_time_ms": data.get("meta", {}).get("db_response_time_ms"),
                "page": data.get("meta", {}).get("page"),
                "per_page": data.get("meta", {}).get("per_page"),
                "total_pages": data.get("meta", {}).get("count", 0) // per_page + (1 if data.get("meta", {}).get("count", 0) % per_page > 0 else 0)
            }
        results = []
        for result in data.get("results", []):
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
           
            results.append({
                "id": result.get("id"),
                "title": result.get("title"),
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
                "abstract": abstract
            })
        return jsonify({
            "meta": meta,
            "results": results
        })
    else:
        return jsonify({"error": f"Error: {response.status_code}"})
    

#Route to get the names of the others
@app.route("/authors", methods=["GET"])
def get_authors():
    """
    Retrieves authors from OpenAlex whose last known institution is the University of Johannesburg.
    The institution is identified by its OpenAlex ID: https://openalex.org/I24027795.
    """

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=1, type=int)

    url = "https://api.openalex.org/authors"
    params = {
        "filter": "last_known_institutions.id:https://openalex.org/I24027795",
        "page": page,
        "per_page": per_page
    }
    headers = {
        "User-Agent": "MyScript (your-email@example.com)"
    }
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        authors_list = []
        for author in data.get("results", []):
            authors_list.append({
                "id": author.get("id"),
                "name": author.get("display_name"),
                "orcid": author.get("orcid"),
                "works_count": author.get("works_count"),
                "cited_by_count": author.get("cited_by_count"),
                "last_known_institutions": author.get("last_known_institutions", [])
            })
        return jsonify(authors_list)
    else:
        print("Error:", response.status_code, response.text)
        return []
    

## WORK BY AUTHORS

#http://localhost:5000/works_by_author?author=John%20Doe
# @app.route("/works_by_author", methods=["GET"])
# def works_by_author():
#     """
#     Fetches works associated with an author from OpenAlex based on an author name provided
#     as a query parameter. Example usage: /works_by_author?author=John%20Doe
#     The results are sorted by publication year in descending order.
#     """
#     # Get the author name from query parameters.
#     author_name = request.args.get("author")
#     if not author_name:
#         return jsonify({"error": "Please provide an author name using the 'author' query parameter."}), 400

#     # Step 1: Search for the author using the OpenAlex authors endpoint.
#     search_url = "https://api.openalex.org/autocomplete/authors"
#     search_params = {
#         "search": author_name,
#         "per_page": 1  # Retrieve only the top result.
#     }
#     USER_AGENT = "MyScript (your-email@example.com)"
#     headers = {"User-Agent": USER_AGENT}
#     author_response = requests.get(search_url, params=search_params, headers=headers)
    
#     if author_response.status_code != 200:
#         return jsonify({
#             "error": "Error fetching author information.",
#             "status_code": author_response.status_code,
#             "message": author_response.text
#         }), author_response.status_code

#     author_data = author_response.json()
#     if not author_data.get("results"):
#         return jsonify({"error": "No author found with that name."}), 404

#     # Retrieve the first matching author.
#     author = author_data["results"][0]
#     author_id = author.get("id")
    
#     # Step 2: Use the author ID to fetch works from the OpenAlex works endpoint.
#     works_url = "https://api.openalex.org/autocomplete/works"
#     works_params = {
#         "filter": f"authorships.author.id:{author_id}",
#         "sort": "publication_year:desc",  # Sort results from most recent to oldest.
#         "per_page": 10  # Adjust per_page as needed.
#     }
#     works_response = requests.get(works_url, params=works_params, headers=headers)
#     if works_response.status_code != 200:
#         return jsonify({
#             "error": "Error fetching works.",
#             "status_code": works_response.status_code,
#             "message": works_response.text
#         }), works_response.status_code

#     works_data = works_response.json()
#     works_list = []
#     for work in works_data.get("results", []):
#         works_list.append({
#             "id": work.get("id"),
#             "title": work.get("title"),
#             "publication_year": work.get("publication_year"),
#             "doi": work.get("doi"),
#             "publication_date": work.get("publication_date")
#             # Add additional fields if desired.
#         })

#     return jsonify({
#         "author": {
#             "id": author_id,
#             "name": author.get("display_name")
#         },
#         "works": works_list
#     })


###NEW THINGS

@app.route("/test", methods=["GET"])
@cross_origin()
def test():
    return jsonify({"message": "Test successful"})

@app.route("/autocomplete_author", methods=["GET"])
def autocomplete_author():
    """
    Returns autocomplete suggestions for authors based on partial input.
    Example usage: /autocomplete_author?author=John
    """
    partial_name = request.args.get("author")
    if not partial_name:
        return jsonify({"error": "Please provide an author name using the 'author' query parameter."}), 400

    search_url = "https://api.openalex.org/autocomplete/authors"
    search_params = {
        "search": partial_name,
    }
    USER_AGENT = "MyScript (your-email@example.com)"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(search_url, params=search_params, headers=headers)
    if response.status_code != 200:
        return jsonify({
            "error": "Error fetching autocomplete suggestions.",
            "status_code": response.status_code,
            "message": response.text
        }), response.status_code

    return jsonify(response.json())


####SECOND PART
@app.route("/works_by_author", methods=["GET"])
def works_by_author():
    """
    Fetches works associated with an author using the selected author ID.
    Example usage: /works_by_author?author_id=AUTH_ID
    """
    author_id = request.args.get("author_id")
    if not author_id:
        return jsonify({"error": "Please provide an author id using the 'author_id' query parameter."}), 400

    works_url = "https://api.openalex.org/works"
    works_params = {
        "filter": f"authorships.author.id:{author_id}",
        "sort": "publication_year:desc",  # Most recent works first.
        "per_page": 10  # Adjust per_page as needed.
    }
    USER_AGENT = "MyScript (your-email@example.com)"
    headers = {"User-Agent": USER_AGENT}
    works_response = requests.get(works_url, params=works_params, headers=headers)
    if works_response.status_code != 200:
        return jsonify({
            "error": "Error fetching works.",
            "status_code": works_response.status_code,
            "message": works_response.text
        }), works_response.status_code

    works_data = works_response.json()
    works_list = []
    for work in works_data.get("results", []):
        works_list.append({
            "id": work.get("id"),
            "title": work.get("title"),
            "publication_year": work.get("publication_year"),
            "doi": work.get("doi"),
            "publication_date": work.get("publication_date")
            # Add additional fields if desired.
        })

    return jsonify({
        "author_id": author_id,
        "works": works_list
    })





################################


########TITLE SEARCH######

@app.route("/autocomplete_work", methods=["GET"])
def autocomplete_work():
    """
    Uses the OpenAlex autocomplete endpoint for works to return suggestions 
    based on a partial title provided via the 'title' query parameter.
    """
    title_query = request.args.get("title")
    if not title_query:
        return jsonify({"error": "Please provide a work title using the 'title' query parameter."}), 400

    search_url = "https://api.openalex.org/autocomplete/works"
    # Note: Do not include invalid parameters like per_page.
    search_params = {
        "search": title_query  # Use the 'search' parameter for partial title matching.
    }
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(search_url, params=search_params, headers=headers)
    if response.status_code != 200:
        return jsonify({
            "error": "Error fetching autocomplete suggestions for works.",
            "status_code": response.status_code,
            "message": response.text
        }), response.status_code

    return jsonify(response.json())

@app.route("/work_details", methods=["GET"])
def work_details():
    """
    Fetches detailed information for a work from OpenAlex using the work ID
    provided via the 'work_id' query parameter.
    """
    work_id = request.args.get("work_id")
    if not work_id:
        return jsonify({"error": "Please provide a work id using the 'work_id' query parameter."}), 400

    # Build the URL for retrieving work details.
    work_url = f"https://api.openalex.org/works/{work_id}"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(work_url, headers=headers)
    if response.status_code != 200:
        return jsonify({
            "error": "Error fetching work details.",
            "status_code": response.status_code,
            "message": response.text
        }), response.status_code

    return jsonify(response.json())


###########################








@app.route("/search_by_title", methods=["GET"])
def search_by_title():
    """
    Searches works from OpenAlex by title.
    Expects query parameters:
      - title: The title (or part of it) to search for.
      - page: (optional) Page number for pagination (default is 1).
      - per_page: (optional) Number of results per page (default is 10).
    """
    title = request.args.get("title", "", type=str)
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=10, type=int)
    
    url = "https://api.openalex.org/works"
    params = {
        "search": title,
        "page": page,
        "per_page": per_page
    }
    headers = {
        "User-Agent": "MyScript (your-email@example.com)"
    }
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        works_list = []
        for work in data.get("results", []):
            works_list.append({
                "id": work.get("id"),
                "title": work.get("display_name") or work.get("title"),
                "doi": work.get("doi"),
                "publication_year": work.get("publication_year")
            })
        return jsonify(works_list)
    else:
        print("Error:", response.status_code, response.text)
        return jsonify([]), response.status_code


if __name__ == "__main__":
    app.run(debug=True)
