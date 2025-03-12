from flask import Flask, jsonify, request
import requests
from flask_cors import CORS, cross_origin
from api.helpers import parse_affiliation, reconstruct_abstract, format_publication

app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*"}})
CORS(app)

USER_AGENT = "MyScript (your-email@example.com)"


@app.route("/")
def index():
    return "Hello form OROSS"


@app.route("/works", methods=["GET"])
def get_works():
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

        return jsonify({"meta": meta, "results": results})
    else:
        return jsonify({"error": f"Error: {response.status_code}"})


# Route to get the names of the others
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
        return jsonify(authors_list)
    else:
        print("Error:", response.status_code, response.text)
        return []


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

    return jsonify({"author_id": author_id, "works": works_list})


########TITLE SEARCH######


@app.route("/autocomplete_work", methods=["GET"])
def autocomplete_work():
    """
    Uses the OpenAlex autocomplete endpoint for works to return suggestions
    based on a partial title provided via the 'title' query parameter.
    """
    title_query = request.args.get("title")
    if not title_query:
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

    return jsonify(response.json())


@app.route("/work", methods=["GET"])
def get_work():
    """
    Fetches detailed information for a work from OpenAlex using the work ID
    provided via the 'work_id' query parameter.
    Returns the data in the same format as get_publications.
    """
    work_id = request.args.get("work_id")
    if not work_id:
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
    title = request.args.get("title", "", type=str)
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=10, type=int)

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
        return jsonify(works_list)
    else:
        print("Error:", response.status_code, response.text)
        return jsonify([]), response.status_code


if __name__ == "__main__":
    app.run(debug=True)
