from flask import Flask, jsonify, request
import requests
from flask_cors import CORS, cross_origin
from api.helpers import parse_affiliation, reconstruct_abstract, format_publication
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('oross_api')

app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*"}})
CORS(app)

USER_AGENT = "MyScript (your-email@example.com)"


@app.route("/")
def index():
    logger.info("Request to index endpoint")
    return "Hello form OROSS"


@app.route("/works", methods=["GET"])
def get_works():
    """
    Endpoint to retrieve publications from the University of Johannesburg with pagination.
    A query parameter 'page' can be provided by the frontend to load different pages.
    """
    start_time = time.time()
    # Get the page number from the query parameters; default to 1 if not provided.
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=10, type=int)
    
    logger.info(f"Request to get_works endpoint - page: {page}, per_page: {per_page}")

    url = "https://api.openalex.org/works"
    params = {
        "page": page,
        "filter": "authorships.institutions.lineage:i24027795",
        "sort": "publication_year:desc",
        "per_page": per_page,
    }

    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        meta = {
            "count": data.get("meta", {}).get("count"),
            "db_response_time_ms": data.get("meta", {}).get("db_response_time_ms"),
            "page": data.get("meta", {}).get("page"),
            "per_page": data.get("meta", {}).get("per_page"),
            "total_pages": data.get("meta", {}).get("count", 0) // per_page
            + (1 if data.get("meta", {}).get("count", 0) % per_page > 0 else 0),
        }
        results = []
        for result in data.get("results", []):
            # Use the format_publication helper function
            formatted_result = format_publication(result)
            results.append(formatted_result)

        elapsed_time = time.time() - start_time
        logger.info(f"get_works completed successfully - returned {len(results)} results in {elapsed_time:.2f}s")
        return jsonify({"meta": meta, "results": results})
    else:
        logger.error(f"Error in get_works: {response.status_code} - {response.text}")
        return jsonify({"error": f"Error: {response.status_code}"})


# Route to get the names of the others
@app.route("/authors", methods=["GET"])
def get_authors():
    """
    Retrieves authors from OpenAlex whose last known institution is the University of Johannesburg.
    The institution is identified by its OpenAlex ID: https://openalex.org/I24027795.
    """
    start_time = time.time()
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=1, type=int)

    logger.info(f"Request to get_authors endpoint - page: {page}, per_page: {per_page}")

    url = "https://api.openalex.org/authors"
    params = {
        "filter": "last_known_institutions.id:https://openalex.org/I24027795",
        "page": page,
        "per_page": per_page,
    }
    headers = {"User-Agent": "MyScript (your-email@example.com)"}
    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        authors_list = []
        for author in data.get("results", []):
            authors_list.append(
                {
                    "id": author.get("id"),
                    "name": author.get("display_name"),
                    "orcid": author.get("orcid"),
                    "works_count": author.get("works_count"),
                    "cited_by_count": author.get("cited_by_count"),
                    "last_known_institutions": author.get(
                        "last_known_institutions", []
                    ),
                }
            )
        elapsed_time = time.time() - start_time
        logger.info(f"get_authors completed successfully - returned {len(authors_list)} authors in {elapsed_time:.2f}s")
        return jsonify(authors_list)
    else:
        logger.error(f"Error in get_authors: {response.status_code} - {response.text}")
        print("Error:", response.status_code, response.text)
        return []


###NEW THINGS


@app.route("/test", methods=["GET"])
@cross_origin()
def test():
    logger.info("Request to test endpoint")
    return jsonify({"message": "Test successful"})


@app.route("/autocomplete_author", methods=["GET"])
def autocomplete_author():
    """
    Returns autocomplete suggestions for authors based on partial input.
    Example usage: /autocomplete_author?author=John
    """
    start_time = time.time()
    partial_name = request.args.get("author")
    
    logger.info(f"Request to autocomplete_author endpoint - query: {partial_name}")
    
    if not partial_name:
        logger.warning("autocomplete_author called without author parameter")
        return (
            jsonify(
                {
                    "error": "Please provide an author name using the 'author' query parameter."
                }
            ),
            400,
        )

    search_url = "https://api.openalex.org/autocomplete/authors"
    search_params = {
        "search": partial_name,
    }
    USER_AGENT = "MyScript (your-email@example.com)"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(search_url, params=search_params, headers=headers)
    if response.status_code != 200:
        logger.error(f"Error in autocomplete_author: {response.status_code} - {response.text}")
        return (
            jsonify(
                {
                    "error": "Error fetching autocomplete suggestions.",
                    "status_code": response.status_code,
                    "message": response.text,
                }
            ),
            response.status_code,
        )

    elapsed_time = time.time() - start_time
    logger.info(f"autocomplete_author completed successfully in {elapsed_time:.2f}s")
    return jsonify(response.json())


####SECOND PART
@app.route("/author/works", methods=["GET"])
def works_by_author():
    """
    Fetches works associated with an author using the selected author ID.
    Example usage: /author/works?author_id=AUTH_ID
    """
    start_time = time.time()
    author_id = request.args.get("author_id")
    
    logger.info(f"Request to works_by_author endpoint - author_id: {author_id}")
    
    if not author_id:
        logger.warning("works_by_author called without author_id parameter")
        return (
            jsonify(
                {
                    "error": "Please provide an author id using the 'author_id' query parameter."
                }
            ),
            400,
        )

    works_url = "https://api.openalex.org/works"
    works_params = {
        "filter": f"authorships.author.id:{author_id}",
        "sort": "publication_year:desc",  # Most recent works first.
        "per_page": 10,  # Adjust per_page as needed.
    }
    USER_AGENT = "MyScript (your-email@example.com)"
    headers = {"User-Agent": USER_AGENT}
    works_response = requests.get(works_url, params=works_params, headers=headers)
    if works_response.status_code != 200:
        logger.error(f"Error in works_by_author: {works_response.status_code} - {works_response.text}")
        return (
            jsonify(
                {
                    "error": "Error fetching works.",
                    "status_code": works_response.status_code,
                    "message": works_response.text,
                }
            ),
            works_response.status_code,
        )

    works_data = works_response.json()
    works_list = []
    for work in works_data.get("results", []):
        works_list.append(
            {
                "id": work.get("id"),
                "title": work.get("title"),
                "publication_year": work.get("publication_year"),
                "doi": work.get("doi"),
                "publication_date": work.get("publication_date"),
                # Add additional fields if desired.
            }
        )

    elapsed_time = time.time() - start_time
    logger.info(f"works_by_author completed successfully - returned {len(works_list)} works in {elapsed_time:.2f}s")
    return jsonify({"author_id": author_id, "works": works_list})


########TITLE SEARCH######


@app.route("/autocomplete_work", methods=["GET"])
def autocomplete_work():
    """
    Uses the OpenAlex autocomplete endpoint for works to return suggestions
    based on a partial title provided via the 'title' query parameter.
    """
    start_time = time.time()
    title_query = request.args.get("title")
    
    logger.info(f"Request to autocomplete_work endpoint - query: {title_query}")
    
    if not title_query:
        logger.warning("autocomplete_work called without title parameter")
        return (
            jsonify(
                {
                    "error": "Please provide a work title using the 'title' query parameter."
                }
            ),
            400,
        )

    search_url = "https://api.openalex.org/autocomplete/works"
    # Note: Do not include invalid parameters like per_page.
    search_params = {
        "search": title_query  # Use the 'search' parameter for partial title matching.
    }
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(search_url, params=search_params, headers=headers)
    if response.status_code != 200:
        logger.error(f"Error in autocomplete_work: {response.status_code} - {response.text}")
        return (
            jsonify(
                {
                    "error": "Error fetching autocomplete suggestions for works.",
                    "status_code": response.status_code,
                    "message": response.text,
                }
            ),
            response.status_code,
        )

    elapsed_time = time.time() - start_time
    logger.info(f"autocomplete_work completed successfully in {elapsed_time:.2f}s")
    return jsonify(response.json())


@app.route("/work", methods=["GET"])
def get_work():
    """
    Fetches detailed information for a work from OpenAlex using the work ID
    provided via the 'work_id' query parameter.
    Returns the data in the same format as get_publications.
    """
    start_time = time.time()
    work_id = request.args.get("work_id")
    
    logger.info(f"Request to get_work endpoint - work_id: {work_id}")
    
    if not work_id:
        logger.warning("get_work called without work_id parameter")
        return (
            jsonify(
                {
                    "error": "Please provide a work id using the 'work_id' query parameter."
                }
            ),
            400,
        )

    # Build the URL for retrieving work details.
    work_url = f"https://api.openalex.org/works/{work_id}"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(work_url, headers=headers)
    if response.status_code != 200:
        logger.error(f"Error in get_work: {response.status_code} - {response.text}")
        return (
            jsonify(
                {
                    "error": "Error fetching work details.",
                    "status_code": response.status_code,
                    "message": response.text,
                }
            ),
            response.status_code,
        )

    # Process the data using the format_publication helper function
    result = response.json()
    formatted_result = format_publication(result)

    elapsed_time = time.time() - start_time
    logger.info(f"get_work completed successfully in {elapsed_time:.2f}s")
    # Return a single item with the same structure as get_publications
    # since we only have one work there is no need to paginate or return the results as an array
    return jsonify(formatted_result)


@app.route("/search_by_title", methods=["GET"])
def search_by_title():
    """
    Searches works from OpenAlex by title.
    Expects query parameters:
      - title: The title (or part of it) to search for.
      - page: (optional) Page number for pagination (default is 1).
      - per_page: (optional) Number of results per page (default is 10).
    """
    start_time = time.time()
    title = request.args.get("title", "", type=str)
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=10, type=int)
    
    logger.info(f"Request to search_by_title endpoint - title: {title}, page: {page}, per_page: {per_page}")

    url = "https://api.openalex.org/works"
    params = {"search": title, "page": page, "per_page": per_page}
    headers = {"User-Agent": "MyScript (your-email@example.com)"}
    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        works_list = []
        for work in data.get("results", []):
            works_list.append(
                {
                    "id": work.get("id"),
                    "title": work.get("display_name") or work.get("title"),
                    "doi": work.get("doi"),
                    "publication_year": work.get("publication_year"),
                }
            )
        elapsed_time = time.time() - start_time
        logger.info(f"search_by_title completed successfully - returned {len(works_list)} results in {elapsed_time:.2f}s")
        return jsonify(works_list)
    else:
        logger.error(f"Error in search_by_title: {response.status_code} - {response.text}")
        print("Error:", response.status_code, response.text)
        return jsonify([]), response.status_code


@app.route("/author", methods=["GET"])
def get_author():
    """
    Fetches detailed information for an author from OpenAlex using the author ID
    provided via the 'author_id' query parameter.
    """
    start_time = time.time()
    author_id = request.args.get("author_id")
    
    logger.info(f"Request to get_author endpoint - author_id: {author_id}")
    
    if not author_id:
        logger.warning("get_author called without author_id parameter")
        return (
            jsonify(
                {
                    "error": "Please provide an author id using the 'author_id' query parameter."
                }
            ),
            400,
        )

    # Build the URL for retrieving author details
    author_url = f"https://api.openalex.org/authors/{author_id}"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(author_url, headers=headers)
    
    if response.status_code != 200:
        logger.error(f"Error in get_author: {response.status_code} - {response.text}")
        return (
            jsonify(
                {
                    "error": "Error fetching author details.",
                    "status_code": response.status_code,
                    "message": response.text,
                }
            ),
            response.status_code,
        )

    # Process the author data
    author_data = response.json()
    
    elapsed_time = time.time() - start_time
    logger.info(f"get_author completed successfully in {elapsed_time:.2f}s")
    return jsonify(author_data)


if __name__ == "__main__":
    app.run(debug=True)
